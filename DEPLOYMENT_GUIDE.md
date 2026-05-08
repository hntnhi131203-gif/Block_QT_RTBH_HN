# Hướng dẫn triển khai Allsite HCM DDoS Protection System

## 1. Cài đặt Dependencies

```bash
pip3 install flask netmiko requests
```

## 2. Cấu trúc thư mục trên Server

```bash
sudo mkdir -p /opt/allsite-hcm
sudo cp Allsite-HCM_Service.py /opt/allsite-hcm/
sudo cp Allsite-HCM.py /opt/allsite-hcm/
sudo chmod +x /opt/allsite-hcm/Allsite-HCM_Service.py
```

## 3. Cấu hình Systemd Service

```bash
sudo cp allsite-hcm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable allsite-hcm
sudo systemctl start allsite-hcm
```

## 4. Kiểm tra trạng thái Service

```bash
# Xem trạng thái real-time
sudo systemctl status allsite-hcm

# Xem logs chi tiết
sudo journalctl -u allsite-hcm -f

# Restart service (nếu cần)
sudo systemctl restart allsite-hcm
```

## 4.5. Truy cập Dashboard Web

Service chạy Flask server trên port **5000**. Mở browser và truy cập:

- **Dashboard chính**: `http://<server-ip>:5000/`
- **Ban/Unban History**: `http://<server-ip>:5000/ban-history` 
- **Detailed Logs**: `http://<server-ip>:5000/logs-detail`
- **Status API**: `http://<server-ip>:5000/status` (JSON format)

## 5. Cấu hình FastNetMon để gọi script

Trong cấu hình FastNetMon (thường tại `/etc/fastnetmon/fastnetmon.conf`), thêm hoặc sửa:

```
notify_script_path = /opt/allsite-hcm/Allsite-HCM.py
notify_script_format = json
```

Hoặc nếu dùng format script cũ:

```bash
/opt/allsite-hcm/Allsite-HCM.py <IP> <DIRECTION> <PPS> <BAN|UNBAN>
```

## 6. Thử nghiệm API trực tiếp

### Cách 1: Từ Command Line

```bash
# Test gửi request đến Service
curl -X POST http://127.0.0.1:5000/fastnetmon_hook \
  -H "Content-Type: application/json" \
  -d '{"ip": "45.119.80.5", "action": "ban"}'

# Hoặc dùng Python
python3 -c "import requests; requests.post('http://127.0.0.1:5000/fastnetmon_hook', json={'ip': '45.119.80.5', 'action': 'ban'})"
```

### Cách 2: Từ Web Dashboard

1. Mở `http://<server-ip>:5000/`
2. Trong mục **⚡ Thao Tác Ban/Unban** nhập IP
3. Click **🚫 Ban IP** hoặc **✅ Unban IP**
4. Xem kết quả ở **📊 Ban/Unban History**

## 7. Hiểu flow xử lý

### Producer-Consumer (Hàng chờ):
- FastNetMon gọi `Allsite-HCM.py`
- Script lightweight bắn IP vào hàng chờ (Queue) 
- Service chạy ngầm xử lý batch

### Event-Driven (Micro-batching):
- Worker chờ IP đầu tiên (block=True)
- Ngủ 2 giây để hốt thêm IP
- Gom lô tất cả IP thành 1 batch

### Multithreading:
- Chia lệnh config vào 3 Switch Core (QFXG8, EXDC4, QFXDC7)
- Gửi cùng lúc = giảm thời gian chờ

## 8. Troubleshooting

**Lỗi: "SyntaxError: '[' was never closed" (dòng 380)**
- Này là lỗi quote escape khi cập nhật mã
- **Giải pháp**: Cập nhật file `Allsite-HCM_Service.py` từ repo mới nhất
- Hoặc sửa dòng 380 bằng cách tách logic:
```python
logs_html = ''
for row in logs:
    color = '#ef4444' if row['level'] == 'ERROR' else '#10b981'
    logs_html += f"<tr><td>{row['timestamp']}</td><td style=\"color: {color}\">{row['level']}</td><td>{row['message']}</td></tr>"
```

**Lỗi: "Configuration Database Locked"**
- Đã giải quyết bằng batching + queue. Nếu vẫn lỗi, giảm `max_workers` từ 3 xuống 1 trong file Service.

**Lỗi: Connection refused tới Juniper**
- Kiểm tra IP, username, password trong DEVICES dict
- Kiểm tra firewall: `telnet 10.8.8.38 22`

**Hàng chờ bị ngưng**
- Xem logs: `sudo journalctl -u allsite-hcm -n 100`
- Restart service: `sudo systemctl restart allsite-hcm`

**Port 5000 bị chiếm**
- Thay `port=5000` thành port khác (ví dụ 5001) trong `Allsite-HCM_Service.py`

**Dashboard không tải được**
- Kiểm tra service running: `sudo systemctl status allsite-hcm`
- Kiểm tra port: `sudo netstat -tlnp | grep 5000`
- Kiểm tra firewall: `sudo ufw allow 5000/tcp`

## 9. Monitor Performance

Mở terminal khác chạy:

```bash
# Xem số tiến trình Python
watch -n 1 'ps aux | grep Allsite'

# Xem network connections
watch -n 1 'netstat -tlnp | grep 5000'
```

---

**Ghi chú:** System sẽ tự restart nếu service gặp lỗi nhờ `Restart=always` trong systemd config.
