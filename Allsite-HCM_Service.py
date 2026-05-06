import ipaddress
import time
import threading
import concurrent.futures
import os
from queue import Queue, Empty
from datetime import datetime, timezone, timedelta
from flask import Flask, request, send_from_directory
from netmiko import ConnectHandler

# --- CẤU HÌNH THIẾT BỊ & DẢI IP (Giữ nguyên của bạn) ---
DEVICES = {
    'QFXG8': {"device_type": "juniper", "ip": "10.8.8.38", "username": "fastnetmon", "password": "M74NRb57k5vc6U", "read_timeout_override": 50},
    'EXDC4': {"device_type": "juniper", "ip": "10.2.8.1", "username": "fastnetmon", "password": "M74NRb57k5vc6U", "read_timeout_override": 50},
    'QFXDC7': {"device_type": "juniper", "ip": "10.2.8.82", "username": "fastnetmon", "password": "M74NRb57k5vc6U", "read_timeout_override": 50}
}

IP_RANGES = {
    ('45.119.80.0/22', '45.119.84.0/22'): ('10.10.20.2','172.31.255.19'),
    ('103.27.236.0/22','103.87.220.0/22'): ('10.10.10.2','172.31.255.19'),
    ('103.48.84.0/22', '103.48.192.0/22'): ('10.10.30.2','172.31.255.3'),
    ('45.119.212.0/22', '42.96.16.0/22'): ('10.10.40.2','172.31.255.3'),
    ('42.96.20.0/23',): ('10.10.31.2','172.17.11.3'),
    ('103.2.228.0/22',): ('172.31.255.19','172.31.255.19'),
    ('103.2.224.0/22',): ('10.10.33.2','10.10.33.2')
}

app = Flask(__name__)
ip_queue = Queue()

# --- TRACKING TRẠNG THÁI ---
status_lock = threading.Lock()
switch_status = {'QFXG8': 'idle', 'EXDC4': 'idle', 'QFXDC7': 'idle'}
current_batch_ips = []
batch_start_time = None

# --- CÁC HÀM LOGIC ---
def check_ip_in_ranges(ip, ranges):
    ip_obj = ipaddress.ip_address(ip)
    for network in ranges:
        if ip_obj in ipaddress.ip_network(network, strict=False):
            return True
    return False

def get_config_commands(ip, action, next_hop_fpt, next_hop_cmc):
    DC = "BGP-CMC-01" if next_hop_cmc == "172.31.255.3" else "BGP-CMC-02"
    DC_FPT = "BGP-FPT3" if next_hop_fpt == "10.10.33.2" else "BGP-FPT"
    QT = "black-hole-QT2" if next_hop_fpt == "10.10.33.2" else "black-hole-QT"
    cmd_type = "set" if action == "ban" else "delete"
    
    res1 = [f"{cmd_type} routing-instances {DC_FPT} routing-options static route {ip} next-hop {next_hop_fpt}",
            f"{cmd_type} policy-options policy-statement {QT} term 1 from route-filter {ip}/32 exact"]
    res2 = [f"{cmd_type} routing-instances {DC} routing-options static route {ip} next-hop {next_hop_cmc}",
            f"{cmd_type} policy-options policy-statement {QT} term 1 from route-filter {ip}/32 exact"]
    return res1, res2

def apply_config(device_name, commands):
    try:
        with status_lock:
            switch_status[device_name] = f'configuring ({len(commands)} cmds)'
        print(f"[{device_name}] Đã kết nối. Đang nạp {len(commands)} lệnh...")
        
        with ConnectHandler(**DEVICES[device_name]) as net_connect:
            net_connect.config_mode()
            net_connect.send_config_set(commands)
            net_connect.commit()
            net_connect.exit_config_mode()
        
        with status_lock:
            switch_status[device_name] = 'idle'
        print(f"[{device_name}] Commit thành công!")
    except Exception as e:
        with status_lock:
            switch_status[device_name] = f'error: {str(e)[:50]}'
        print(f"[{device_name}] Lỗi: {str(e)}")

# --- WORKER: GOM LÔ & ĐA LUỒNG ---
def process_queue_batch():
    global current_batch_ips, batch_start_time
    while True:
        batch = []
        try:
            # 1. Đứng chờ IP đầu tiên (Event-driven)
            first_item = ip_queue.get(block=True) 
            batch.append(first_item)
            batch_start_time = time.time()
            
            # 2. Ngủ 2s để hốt các IP đến sát nút (Micro-batching)
            time.sleep(2)
            while not ip_queue.empty():
                try: batch.append(ip_queue.get_nowait())
                except Empty: break
            
            # Cập nhật batch IPs
            with status_lock:
                current_batch_ips = [item['ip'] for item in batch]
                    
            print(f"\n--- Bắt đầu xử lý lô gồm {len(batch)} IP ---")
            commands_to_send = {'QFXG8': [], 'EXDC4': [], 'QFXDC7': []}
            
            # 3. Phân loại lệnh vào Dictionary
            for item in batch:
                client_ip, action = item['ip'], item['action']
                for ranges, (next_hop_fpt, next_hop_cmc) in IP_RANGES.items():
                    if check_ip_in_ranges(client_ip, ranges):
                        sw1, sw2 = None, None
                        match next_hop_fpt:
                            case '10.10.20.2'|'10.10.10.2': sw1, sw2 = 'EXDC4', 'QFXG8'
                            case '10.10.30.2'|'10.10.40.2': sw1, sw2 = 'QFXDC7', 'QFXG8'
                            case '10.10.31.2': sw1, sw2 = 'QFXDC7', 'QFXG8'
                            case '10.10.33.2': sw1, sw2 = 'QFXDC7', 'QFXDC7'
                        
                        cfg1, cfg2 = get_config_commands(client_ip, action, next_hop_fpt, next_hop_cmc)
                        commands_to_send[sw1].extend(cfg1)
                        if next_hop_fpt != "10.10.33.2" and sw2:
                            commands_to_send[sw2].extend(cfg2)
                        break
            
            # 4. Thực thi Đa luồng (Multithreading)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                for device_name, cmds in commands_to_send.items():
                    if cmds:
                        unique_cmds = list(set(cmds)) # Lọc trùng
                        futures.append(executor.submit(apply_config, device_name, unique_cmds))
                
                # Chờ tất cả Switch commit xong mới lặp lại (Khóa tự nhiên)
                concurrent.futures.wait(futures)
            
            # Xóa batch hiện tại
            with status_lock:
                current_batch_ips = []
                batch_start_time = None
            print("--- Hoàn tất lô. Quay lại trạng thái chờ ---\n")
                    
        except Exception as e:
            print(f"Lỗi Worker: {str(e)}")
            time.sleep(5)

# --- API NHẬN REQUEST TỪ FASTNETMON ---
@app.route('/fastnetmon_hook', methods=['POST'])
def handle_fastnetmon():
    data = request.json
    ip_queue.put({'ip': data.get('ip'), 'action': data.get('action')})
    return {"status": "queued"}, 200

# --- API KIỂM TRA TRẠNG THÁI ---
@app.route('/status', methods=['GET'])
def get_status():
    with status_lock:
        queue_size = ip_queue.qsize()
        batch_ips = current_batch_ips.copy()
        batch_age = time.time() - batch_start_time if batch_start_time else None
        sw_status = switch_status.copy()
    
    return {
        "timestamp": datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S'),
        "queue": {
            "size": queue_size,
            "status": f"{queue_size} IP đang chờ"
        },
        "current_batch": {
            "ips": batch_ips,
            "count": len(batch_ips),
            "age_seconds": round(batch_age, 2) if batch_age else None
        },
        "switches": sw_status
    }, 200

# --- DASHBOARD WEB ---
@app.route('/')
def dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), 'dashboard.html')
    try:
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Dashboard không tìm thấy</h1><p>Vui lòng đặt dashboard.html cùng thư mục với service</p>", 404

if __name__ == '__main__':
    # Bật Worker chạy ngầm trước khi chạy Server
    threading.Thread(target=process_queue_batch, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
