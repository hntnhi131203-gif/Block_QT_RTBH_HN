#!/usr/bin/env python3
"""
Status checker cho Allsite HCM Service
Kiểm tra trạng thái real-time của các Switch và hàng chờ
"""

import requests
import json
import sys
from datetime import datetime

def get_status(host='127.0.0.1', port=5000):
    try:
        url = f'http://{host}:{port}/status'
        response = requests.get(url, timeout=2)
        return response.json()
    except Exception as e:
        print(f"❌ Lỗi kết nối: {str(e)}")
        return None

def print_status(status):
    if not status:
        return
    
    print("\n" + "="*70)
    print(f"📊 ALLSITE HCM SERVICE STATUS - {status['timestamp']}")
    print("="*70)
    
    # Hàng chờ
    queue = status.get('queue', {})
    print(f"\n📬 HÀNG CHỜ: {queue.get('size', 0)} IP")
    print(f"   Status: {queue.get('status', 'N/A')}")
    
    # Batch hiện tại
    batch = status.get('current_batch', {})
    print(f"\n⚙️  BATCH HIỆN TẠI:")
    print(f"   Số IP: {batch.get('count', 0)}")
    if batch.get('ips'):
        for ip in batch['ips']:
            print(f"      • {ip}")
    else:
        print(f"   (không có IP đang xử lý)")
    
    if batch.get('age_seconds'):
        print(f"   Thời gian chạy: {batch['age_seconds']}s")
    
    # Trạng thái Switch
    switches = status.get('switches', {})
    print(f"\n🔌 TRẠNG THÁI SWITCH:")
    for sw_name, sw_state in switches.items():
        status_icon = "🟢" if sw_state == "idle" else "🔄" if "configuring" in sw_state else "🔴"
        print(f"   {status_icon} {sw_name}: {sw_state}")
    
    print("\n" + "="*70 + "\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Check Allsite HCM Service status')
    parser.add_argument('--host', default='127.0.0.1', help='Service host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Service port (default: 5000)')
    parser.add_argument('--watch', action='store_true', help='Watch mode - update every 2 seconds')
    
    args = parser.parse_args()
    
    if args.watch:
        import time
        try:
            while True:
                status = get_status(args.host, args.port)
                print_status(status)
                time.sleep(2)
        except KeyboardInterrupt:
            print("\n👋 Thoát watch mode")
    else:
        status = get_status(args.host, args.port)
        print_status(status)

if __name__ == '__main__':
    main()
