# 📊 Real-time Monitor - Hướng dẫn sử dụng

## 🌐 **Option 1: Web Dashboard (Recommended)**

### Cách sử dụng:
1. Đảm bảo service đang chạy
2. Mở trình duyệt: **http://127.0.0.1:5000**
3. Xem realtime:
   - 📬 Hàng chờ (Queue size)
   - ⚙️ Batch hiện tại (IP đang xử lý)
   - 🔌 Trạng thái 3 Switch Core

### Tính năng:
✅ **Auto-refresh mỗi 1 giây**
✅ **Giao diện đẹp & trực quan**
✅ **Animation & color-coding**
✅ **Responsive (dùng được trên điện thoại)**
✅ **Không cần cài gì thêm**

### Hình ảnh minh họa:
```
┌──────────────────────────────────────────────────────────────────────┐
│                    🛡️ DDoS Protection Monitor                        │
│                    Allsite HCM Real-time Service Status              │
│                            14:32:15  ●                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────────────┐        ┌─────────────────────────┐     │
│  │  📬 Hàng Chờ            │        │  ⚙️ Batch Hiện Tại      │     │
│  │                         │        │                         │     │
│  │         3 IP            │        │  ✓ 2 IP (0.85s)        │     │
│  │   Đang chờ              │        │  • 45.119.80.5          │     │
│  │                         │        │  • 45.119.80.10         │     │
│  └─────────────────────────┘        └─────────────────────────┘     │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  🔌 Trạng Thái Switch Core                                  │    │
│  │                                                              │    │
│  │  ● QFXG8       ✓ Rảnh                                       │    │
│  │  ● EXDC4       ↻ Đang cấu hình (4 lệnh)                    │    │
│  │  ● QFXDC7      ✓ Rảnh                                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                        │
│              ↻ Tự động cập nhật mỗi 1 giây                          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🖥️ **Option 2: Terminal Monitor**

### Cài đặt:
```bash
pip3 install rich requests
```

### Chạy:
```bash
python3 terminal_monitor.py
```

### Custom host/port:
```bash
python3 terminal_monitor.py --host 192.168.1.100 --port 5001
```

### Giao diện Terminal:
```
┌─────────────────────────────────────────────────────────────────────┐
│                 🛡️ DDoS PROTECTION MONITOR                          │
│                 Allsite HCM Service                                 │
├─────────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────┐  ┌────────────────────────────┐               │
│  │ 📬 Hàng Chờ      │  │ ⚙️ Batch Hiện Tại         │               │
│  │                  │  │                            │               │
│  │        3         │  │ ✓ 2 IP đang xử lý (0.85s) │               │
│  │ 3 IP đang chờ    │  │ ◆ 45.119.80.5             │               │
│  │                  │  │ ◆ 45.119.80.10            │               │
│  └──────────────────┘  └────────────────────────────┘               │
│
│  ┌──────────────────────────────────────────────┐                   │
│  │ 🔌 Switch Core                               │                   │
│  │                                              │                   │
│  │ Switch     │ Trạng Thái                     │                   │
│  │ ───────────┼────────────────────────────────│                   │
│  │ QFXG8      │ ● Rảnh                         │                   │
│  │ EXDC4      │ ● Đang cấu hình (4 lệnh)      │                   │
│  │ QFXDC7     │ ● Rảnh                         │                   │
│  └──────────────────────────────────────────────┘                   │
│
├─────────────────────────────────────────────────────────────────────┤
│  ↻ Tự động cập nhật | Lần cuối: 2026-05-05 14:32:15              │
└─────────────────────────────────────────────────────────────────────┘
```

### Điều khiển:
- **Ctrl+C** - Thoát
- **Tự động refresh mỗi 1 giây**

---

## 📱 **Option 3: CLI Command (Lightweight)**

### Xem 1 lần:
```bash
python3 check_status.py
```

### Watch mode (refresh mỗi 2s):
```bash
python3 check_status.py --watch
```

### Kết hợp với watch:
```bash
watch -n 1 'curl -s http://127.0.0.1:5000/status | jq'
```

---

## 🔄 **So Sánh 3 Phương Thức**

| Tính năng | Web Dashboard | Terminal TUI | CLI |
|-----------|--------------|-------------|-----|
| Giao diện | ✨ Đẹp | 🎨 Đẹp | 📝 Đơn giản |
| Auto-refresh | 1s | 1s | 2s |
| Cần cài gì | Không | `pip install rich` | Chỉ requests |
| SSH vào server | ✗ | ✓ | ✓ |
| Điện thoại | ✓ | ✗ | ✗ |
| Startup nhanh | Cực nhanh | Có chậm hơn | Rất nhanh |

---

## 🎯 **Khuyến Nghị**

### 👨‍💼 **Sysadmin (SSH vào server)**
→ Dùng **Terminal Monitor** (`python3 terminal_monitor.py --watch`)

### 🏢 **Team/Office Monitor**
→ Dùng **Web Dashboard** (để máy chủ chạy, team xem qua browser)

### ⚡ **Quick Check**
→ Dùng **CLI** (`python3 check_status.py`)

---

## 🐛 **Troubleshooting**

### Web Dashboard không load
```bash
# Kiểm tra service
curl http://127.0.0.1:5000/status

# Kiểm tra file dashboard.html tồn tại
ls -la dashboard.html
```

### Terminal Monitor bị lỗi
```bash
# Cài đặt rich
pip3 install rich --upgrade

# Hoặc chạy fallback mode
python3 check_status.py --watch
```

### Port 5000 bị chiếm
```bash
# Sửa trong Allsite-HCM_Service.py
# Thay: app.run(host='127.0.0.1', port=5000)
# Thành: app.run(host='127.0.0.1', port=5001)
```

---

## 📊 **Màu Sắc & Icons Nghĩa**

### Switch Status:
| Icon | Màu | Ý nghĩa |
|------|-----|---------|
| 🟢 ● | Green | Rảnh (idle) |
| 🔄 ● | Orange | Đang cấu hình |
| 🔴 ● | Red | Lỗi |

### Queue:
| Range | Màu | Cảnh báo |
|-------|-----|---------|
| 0-5 | 🟢 | OK |
| 6-50 | 🟡 | Cần chú ý |
| >50 | 🔴 | Cảnh báo |

---

## 🚀 **Tips Pro**

### 1. Monitor 24/7 với Web Dashboard
```bash
# Trên server (background)
tmux new-session -d -s allsite "python3 Allsite-HCM_Service.py"

# Trên máy tính của bạn
# Mở: http://server-ip:5000
```

### 2. Alert khi có lỗi
```bash
#!/bin/bash
while true; do
  STATUS=$(curl -s http://127.0.0.1:5000/status)
  if echo $STATUS | jq '.switches | map(select(contains("error"))) | length' | grep -v 0; then
    echo "⚠️ ALERT: Switch lỗi!" | mail -s "DDoS Service Error" admin@company.com
  fi
  sleep 60
done
```

### 3. Log thống kê
```bash
# Append status vào log mỗi 5 phút
(crontab -l; echo "*/5 * * * * curl -s http://127.0.0.1:5000/status >> /var/log/allsite-monitor.log") | crontab -
```

---

**Chọn một trong ba cách trên tùy theo nhu cầu của bạn!** 🎯

