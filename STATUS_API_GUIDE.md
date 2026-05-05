# Hướng dẫn Sử dụng API Status

## Tính năng mới

Service hiện nay có thêm API endpoint `/status` để xem trạng thái real-time:
- ✅ Số IP đang chờ trong hàng chờ
- ✅ IP nào đang được xử lý trong batch hiện tại
- ✅ Trạng thái của từng Switch Core (idle / configuring / error)

---

## Cách sử dụng

### 1. Gọi API trực tiếp (curl)

```bash
# Lấy status một lần
curl http://127.0.0.1:5000/status

# Gọi liên tục (check mỗi 1s)
watch -n 1 'curl -s http://127.0.0.1:5000/status | jq'
```

### 2. Dùng Python script helper

#### Kiểm tra status một lần:
```bash
python3 check_status.py
```

Kết quả ví dụ:
```
======================================================================
📊 ALLSITE HCM SERVICE STATUS - 2026-05-05 14:32:15
======================================================================

📬 HÀNG CHỜ: 3 IP
   Status: 3 IP đang chờ

⚙️  BATCH HIỆN TẠI:
   Số IP: 0
   (không có IP đang xử lý)

🔌 TRẠNG THÁI SWITCH:
   🟢 QFXG8: idle
   🟢 EXDC4: idle
   🟢 QFXDC7: idle

======================================================================
```

#### Watch mode (tự động refresh mỗi 2s):
```bash
python3 check_status.py --watch
```

#### Custom host/port:
```bash
python3 check_status.py --host 192.168.1.100 --port 5001
```

### 3. Từ Python code

```python
import requests

response = requests.get('http://127.0.0.1:5000/status')
status = response.json()

print(f"IP trong hàng chờ: {status['queue']['size']}")
print(f"IP đang xử lý: {status['current_batch']['ips']}")
print(f"Trạng thái QFXG8: {status['switches']['QFXG8']}")
```

### 4. Từ bash/shell script

```bash
#!/bin/bash
STATUS=$(curl -s http://127.0.0.1:5000/status)
QUEUE_SIZE=$(echo $STATUS | jq '.queue.size')
echo "IP đang chờ: $QUEUE_SIZE"
```

---

## Giải thích trạng thái Switch

| Trạng thái | Ý nghĩa |
|-----------|---------|
| `idle` | 🟢 Switch rảnh rỗi, sẵn sàng nhận config |
| `configuring (N cmds)` | 🔄 Đang gửi N lệnh, chưa commit xong |
| `error: ...` | 🔴 Gặp lỗi khi connect hoặc commit |

---

## Monitoring Advanced

### Sử dụng jq để filter output

```bash
# Chỉ xem hàng chờ
curl -s http://127.0.0.1:5000/status | jq '.queue'

# Chỉ xem trạng thái switch
curl -s http://127.0.0.1:5000/status | jq '.switches'

# Kiểm tra nếu có lỗi nào
curl -s http://127.0.0.1:5000/status | jq '.switches | map(select(contains("error")))'
```

### Logging tự động

```bash
# Log trạng thái mỗi 30s vào file
while true; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $(curl -s http://127.0.0.1:5000/status | jq -c .)" >> service.log
  sleep 30
done
```

### Alert khi có lỗi

```bash
#!/bin/bash
while true; do
  STATUS=$(curl -s http://127.0.0.1:5000/status)
  ERRORS=$(echo $STATUS | jq '.switches | map(select(contains("error")))')
  
  if [ "$ERRORS" != "{}" ]; then
    echo "⚠️ ALERT: Switch gặp lỗi!"
    echo $STATUS | jq '.switches'
    # Gửi alert (email, Slack, etc.)
  fi
  
  sleep 10
done
```

---

## Troubleshooting

**Q: API không phản hồi**
```bash
# Kiểm tra service có chạy không
ps aux | grep Allsite-HCM_Service.py

# Kiểm tra port 5000
netstat -tlnp | grep 5000
```

**Q: Status luôn hiển thị idle**
- Bình thường - service đang chờ IP từ FastNetMon
- Khi có tấn công, sẽ thấy IP xuất hiện

**Q: Switch báo error**
- Kiểm tra logs: `sudo journalctl -u allsite-hcm -n 50`
- Kiểm tra kết nối Juniper: `telnet 10.8.8.38 22`

---

## Response JSON Format

```json
{
  "timestamp": "2026-05-05 14:32:15",
  "queue": {
    "size": 3,
    "status": "3 IP đang chờ"
  },
  "current_batch": {
    "ips": ["45.119.80.5", "45.119.80.10"],
    "count": 2,
    "age_seconds": 0.85
  },
  "switches": {
    "QFXG8": "idle",
    "EXDC4": "configuring (4 cmds)",
    "QFXDC7": "idle"
  }
}
```

---

## Best Practices

1. **Kiểm tra định kỳ** - Setup cron job check status mỗi 5 phút
2. **Monitor queue size** - Alert nếu queue > 100 IPs (có thể là lỗi service)
3. **Log errors** - Lưu lại lỗi để debug sau
4. **Test trước khi deploy** - Gửi test IP để xác nhận hoạt động

