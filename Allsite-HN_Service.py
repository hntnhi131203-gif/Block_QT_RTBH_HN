import ipaddress
import time
import threading
import concurrent.futures
import os
import logging
import sqlite3
from queue import Queue, Empty
from datetime import datetime, timezone, timedelta
from flask import Flask, request, send_from_directory
from netmiko import ConnectHandler

# --- HỌC UTC +7 HELPER ---
def get_vietnam_time():
    """Lấy thời gian hiện tại theo múi giờ UTC +7 (Việt Nam)"""
    utc_tz = timezone.utc
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(utc_tz).astimezone(vn_tz)

class VietnamTimeFormatter(logging.Formatter):
    """Custom formatter để logging dùng giờ Việt Nam (UTC +7)"""
    converter = lambda *args: get_vietnam_time().timetuple()

# Cấu hình logging
handler = logging.FileHandler('allsite-hn.log', encoding='utf-8')
formatter = VietnamTimeFormatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Cấu hình stdout console logging (dev use)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
DEVICES = {
    'EXE1': {"device_type": "juniper", "ip": "10.3.8.1", "username": "fastnetmon", "password": "M74NRb57k5vc6U", "read_timeout_override": 50},
    'EXV5': {"device_type": "juniper", "ip": "103.252.2.234", "username": "fastnetmon", "password": "M74NRb57k5vc6U", "read_timeout_override": 50}
}

IP_RANGES = {
    ('103.237.144.0/22',): ('10.10.60.2','172.31.255.201'),
    ('45.118.144.0/22',): ('10.10.50.2','172.31.255.201'),
    ('103.97.132.0/22',): ('10.10.50.2','172.31.255.201'),
    ('103.200.24.0/22',): ('172.31.255.209','10.10.22.2'),
    ('103.89.92.0/22',): ('172.31.255.209','10.10.22.2')
}

app = Flask(__name__)
ip_queue = Queue()
DB_FILE = 'allsite-hn.db'
db_lock = threading.Lock()

# --- TRACKING TRẠNG THÁI ---
status_lock = threading.Lock()
switch_status = {'EXE1': 'idle', 'EXV5': 'idle'}
current_batch_ips = []
batch_start_time = None

# --- DATABASE FUNCTIONS ---
def init_database():
    """Khởi tạo database và các bảng"""
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Bảng ban IPs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_ips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                ban_time TEXT,
                device TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Bảng unban IPs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unbanned_ips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                unban_time TEXT,
                device TEXT,
                status TEXT DEFAULT 'success'
            )
        ''')
        
        # Bảng log chi tiết
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detailed_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                level TEXT,
                message TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

def log_ban_unban(ip, action, device=None):
    """Ghi ban/unban vào database với thời gian UTC +7"""
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        vn_time = get_vietnam_time().strftime('%Y-%m-%d %H:%M:%S')
        
        if action.lower() == 'ban':
            cursor.execute('INSERT INTO banned_ips (ip, ban_time, device) VALUES (?, ?, ?)', (ip, vn_time, device))
        elif action.lower() == 'unban':
            cursor.execute('INSERT INTO unbanned_ips (ip, unban_time, device) VALUES (?, ?, ?)', (ip, vn_time, device))
        
        conn.commit()
        conn.close()

def log_detail(level, message):
    """Ghi log chi tiết vào database với thời gian UTC +7"""
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        vn_time = get_vietnam_time().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO detailed_logs (timestamp, level, message) VALUES (?, ?, ?)', (vn_time, level, message))
        conn.commit()
        conn.close()

# --- CÁC HÀM LOGIC ---
def check_ip_in_ranges(ip, ranges):
    ip_obj = ipaddress.ip_address(ip)
    for network in ranges:
        if ip_obj in ipaddress.ip_network(network, strict=False):
            return True
    return False

def get_config_commands(ip, action, next_hop_fpt, next_hop_cmc):
    DC = "BGP-CMC2" if next_hop_fpt in ("10.10.50.2", "10.10.60.2") else "BGP-CMC"
    DC_FPT = "BGP-FPT-HN-02" if next_hop_fpt in ("172.31.255.209") else "BGP-FPT-HN"
    BH_FPT = "black-hole-QT-02" if next_hop_fpt in ("172.31.255.209") else "black-hole-QT"
    cmd_type = "set" if action == "ban" else "delete"
    
    res1 = [f"{cmd_type} routing-instances {DC_FPT} routing-options static route {ip} next-hop {next_hop_fpt}",
            f"{cmd_type} policy-options policy-statement {BH_FPT} term 1 from route-filter {ip}/32 exact"]
    res2 = [f"{cmd_type} routing-instances {DC} routing-options static route {ip} next-hop {next_hop_cmc}",
            f"{cmd_type} policy-options policy-statement black-hole-QT term 1 from route-filter {ip}/32 exact"]
    return res1, res2

def commit_device(device_name):
    """Commit một thiết bị"""
    try:
        with status_lock:
            switch_status[device_name] = 'final commit'
        with ConnectHandler(**DEVICES[device_name]) as net_connect:
            net_connect.commit()
        with status_lock:
            switch_status[device_name] = 'idle'
        print(f"[{device_name}] Final commit thành công!")
        logger.info(f"Final commit successful on {device_name}")
    except Exception as e:
        with status_lock:
            switch_status[device_name] = f'error: {str(e)[:50]}'
        logger.error(f"Failed to final commit on {device_name}: {str(e)}")
        print(f"[{device_name}] Lỗi final commit: {str(e)}")

def final_commit_all_devices():
    """Commit trên tất cả thiết bị khi queue trống"""
    print("\n[INFO] Queue trống. Thực hiện commit final trên tất cả thiết bị...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        for device_name in DEVICES.keys():
            futures.append(executor.submit(commit_device, device_name))
        concurrent.futures.wait(futures)
    print("[INFO] Commit final hoàn tất\n")

def apply_config(device_name, commands):
    try:
        with status_lock:
            switch_status[device_name] = f'configuring ({len(commands)} cmds)'
        print(f"[{device_name}] Đã kết nối. Đang nạp {len(commands)} lệnh...")
        
        with ConnectHandler(**DEVICES[device_name]) as net_connect:
            net_connect.config_mode()
            net_connect.send_config_set(commands)
            net_connect.send_config_set("commit check")
            net_connect.exit_config_mode()
        
        with status_lock:
            switch_status[device_name] = 'idle'
        print(f"[{device_name}] Commit thành công!")
        log_detail('INFO', f"Config applied successfully on {device_name}")
    except Exception as e:
        with status_lock:
            switch_status[device_name] = f'error: {str(e)[:50]}'
        log_detail('ERROR', f"Failed to apply config on {device_name}: {str(e)}")
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
            commands_to_send = {'EXE1': [], 'EXV5': []}
            
            # 3. Phân loại lệnh vào Dictionary
            for item in batch:
                client_ip, action = item['ip'], item['action']
                for ranges, (next_hop_fpt, next_hop_cmc) in IP_RANGES.items():
                    if check_ip_in_ranges(client_ip, ranges):
                        sw1 = 'EXV5'
                        sw2 = 'EXE1'
                        
                        cfg1, cfg2 = get_config_commands(client_ip, action, next_hop_fpt, next_hop_cmc)
                        commands_to_send[sw2].extend(cfg1)
                       #if next_hop_fpt != "10.10.22.2":
                       #if next_hop_fpt == "1.1.1.1": # Chỉ gửi lệnh cho EXE1 nếu next_hop_fpt là
                        #    commands_to_send[sw1].extend(cfg1)
                        break
            
            # 4. Thực thi Đa luồng (Multithreading)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = []
                for device_name, cmds in commands_to_send.items():
                    if cmds:
                        unique_cmds = list(set(cmds)) # Lọc trùng
                        futures.append(executor.submit(apply_config, device_name, unique_cmds))
                
                # Chờ tất cả Switch commit xong mới lặp lại (Khóa tự nhiên)
                concurrent.futures.wait(futures)
            
            # Ghi database cho từng IP đã xử lý thành công
            for item in batch:
                log_ban_unban(item['ip'], item['action'])
                log_detail('INFO', f"Successfully processed {item['action']} for IP: {item['ip']}")
            
            # Xóa batch hiện tại
            with status_lock:
                current_batch_ips = []
                batch_start_time = None
            print("--- Hoàn tất lô. Quay lại trạng thái chờ ---\n")
            
            # Nếu queue trống, thực hiện final commit trên tất cả thiết bị
            if ip_queue.empty():
                final_commit_all_devices()
                    
        except Exception as e:
            print(f"Lỗi Worker: {str(e)}")
            time.sleep(5)

# --- API NHẬN REQUEST TỪ FASTNETMON ---
@app.route('/fastnetmon_hook', methods=['POST'])
def handle_fastnetmon():
    data = request.json
    if not data:
        return {"error": "No JSON data provided"}, 400
    
    ip = data.get('ip', '').strip()
    action = data.get('action', '').lower()
    
    if not ip or not action:
        return {"error": "Missing 'ip' or 'action' field"}, 400
    
    if action not in ['ban', 'unban']:
        return {"error": "Action must be 'ban' or 'unban'"}, 400
    
    # Validate IP format
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return {"error": f"Invalid IP address: {ip}"}, 400
    
    log_detail('INFO', f"Received {action} request for IP: {ip}")
    ip_queue.put({'ip': ip, 'action': action})
    return {"status": "queued", "ip": ip, "action": action}, 200

# --- API KIỂM TRA TRẠNG THÁI ---
@app.route('/status', methods=['GET'])
def get_status():
    with status_lock:
        queue_size = ip_queue.qsize()
        batch_ips = current_batch_ips.copy()
        batch_age = time.time() - batch_start_time if batch_start_time else None
        sw_status = switch_status.copy()
    
    return {
        "timestamp": get_vietnam_time().strftime('%Y-%m-%d %H:%M:%S'),
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

# --- BAN/UNBAN HISTORY VIEWER ---
@app.route('/ban-history')
def ban_history():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Lấy danh sách IP bị ban
        cursor.execute('SELECT ip, ban_time, device FROM banned_ips WHERE status = "active" ORDER BY ban_time DESC LIMIT 100')
        banned = cursor.fetchall()
        
        # Lấy danh sách IP được unban
        cursor.execute('SELECT ip, unban_time, device FROM unbanned_ips ORDER BY unban_time DESC LIMIT 100')
        unbanned = cursor.fetchall()
        
        conn.close()
    
    banned_html = ''.join([f"<tr><td>{row['ip']}</td><td>{row['ban_time']}</td><td>{row['device'] or 'N/A'}</td></tr>" for row in banned])
    unbanned_html = ''.join([f"<tr><td>{row['ip']}</td><td>{row['unban_time']}</td><td>{row['device'] or 'N/A'}</td></tr>" for row in unbanned])
    
    return f"""
    <html>
    <head>
        <title>Allsite HN - Ban History</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
            h1 {{ color: #3b82f6; }}
            h2 {{ color: #06b6d4; margin-top: 30px; }}
            table {{ width: 100%; border-collapse: collapse; background: #1e293b; margin: 20px 0; }}
            th, td {{ padding: 12px; border: 1px solid #334155; text-align: left; }}
            th {{ background: #334155; font-weight: bold; }}
            tr:hover {{ background: #293548; }}
            a {{ color: #06b6d4; text-decoration: none; }}
            .banned {{ color: #ef4444; }}
            .unbanned {{ color: #10b981; }}
        </style>
    </head>
    <body>
        <h1>🛡️ Allsite HN - Ban/Unban History</h1>
        <p><a href="/">← Quay lại Dashboard</a> | <a href="/logs-detail">📋 Log Chi Tiết</a></p>
        
        <h2 class="banned">❌ IPs Đang Bị Ban ({len(banned)})</h2>
        <table>
            <tr><th>IP Address</th><th>Ban Time</th><th>Device</th></tr>
            {banned_html if banned_html else '<tr><td colspan="3" style="text-align: center;">Không có IP nào bị ban</td></tr>'}
        </table>
        
        <h2 class="unbanned">✅ IPs Được Unban ({len(unbanned)})</h2>
        <table>
            <tr><th>IP Address</th><th>Unban Time</th><th>Device</th></tr>
            {unbanned_html if unbanned_html else '<tr><td colspan="3" style="text-align: center;">Không có IP nào được unban</td></tr>'}
        </table>
    </body>
    </html>
    """

# --- DETAILED LOGS VIEWER ---
@app.route('/logs-detail')
def logs_detail():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT timestamp, level, message FROM detailed_logs ORDER BY timestamp DESC LIMIT 500')
        logs = cursor.fetchall()
        conn.close()
    
    logs_html = ''
    for row in logs:
        color = '#ef4444' if row['level'] == 'ERROR' else '#10b981'
        logs_html += f"<tr><td>{row['timestamp']}</td><td style=\"color: {color}\">{row['level']}</td><td>{row['message']}</td></tr>"
    
    return f"""
    <html>
    <head>
        <title>Allsite HN - Detailed Logs</title>
        <style>
            body {{ font-family: monospace; background: #0f172a; color: #e2e8f0; padding: 20px; }}
            h1 {{ color: #3b82f6; }}
            table {{ width: 100%; border-collapse: collapse; background: #1e293b; margin: 20px 0; font-size: 12px; }}
            th, td {{ padding: 10px; border: 1px solid #334155; text-align: left; }}
            th {{ background: #334155; font-weight: bold; }}
            tr:hover {{ background: #293548; }}
            a {{ color: #06b6d4; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h1>📋 Allsite HN - Detailed Logs</h1>
        <p><a href="/">← Quay lại Dashboard</a> | <a href="/ban-history">Ban/Unban History</a></p>
        
        <table>
            <tr><th>Timestamp</th><th>Level</th><th>Message</th></tr>
            {logs_html if logs_html else '<tr><td colspan="3" style="text-align: center;">Không có log nào</td></tr>'}
        </table>
    </body>
    </html>
    """

if __name__ == '__main__':
    # Khởi tạo database
    init_database()
    # Bật Worker chạy ngầm trước khi chạy Server
    threading.Thread(target=process_queue_batch, daemon=True).start()
    app.run(host='0.0.0.0', port=5001)
