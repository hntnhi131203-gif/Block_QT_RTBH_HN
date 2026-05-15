import sys
import requests

def main():
    if len(sys.argv) < 5:
        print("Sử dụng: python3 Allsite-HN.py <IP> <direction> <pps> <ban/unban>")
        sys.exit(1)

    client_ip = sys.argv[1]
    action = sys.argv[4]

    # Bắn data vào service đang chạy ngầm
    data = {"ip": client_ip, "action": action}
    try:
        # Timeout 2s để FastNetMon không bao giờ bị nghẽn
        response = requests.post("http://127.0.0.1:5001/fastnetmon_hook", json=data, timeout=2)
        print(f"Đã gửi {client_ip} ({action}) vào hàng chờ. Trạng thái: {response.status_code}")
    except Exception as e:
        print(f"Lỗi kết nối đến Hàng chờ: {str(e)}")

if __name__ == "__main__":
    main()
