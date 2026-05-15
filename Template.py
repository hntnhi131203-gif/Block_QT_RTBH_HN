import ipaddress
from netmiko import ConnectHandler
import sys

# Cấu hình thiết bị
DEVICES = {
    'EXE1': {
        "device_type": "juniper",
        "ip": "10.3.8.1",
        "username": "fastnetmon",
        "password": "M74NRb57k5vc6U",
        "read_timeout_override": 50
    },
    'EXV5': {
        "device_type": "juniper",
        "ip": "103.252.2.234",
        "username": "fastnetmon",
        "password": "M74NRb57k5vc6U",
        "read_timeout_override": 50
    },
}

IP_RANGES = {
    # FPT-HN
    '103.237.144.0/22': ('10.10.60.2', '172.31.255.201'),
    '45.118.144.0/22': ('10.10.50.2', '172.31.255.201'),
    '103.97.132.0/22': ('10.10.50.2', '172.31.255.201'),
    # CMC-HN
    '103.200.24.0/22': ('10.10.22.2', '10.10.22.2')
}

def check_ip_in_ranges(ip, ranges):
    ip_obj = ipaddress.ip_address(ip)
    for network in ranges:
        if ip_obj in ipaddress.ip_network(network, strict=False):
            return True
    return False

def get_config_commands(ip, action, next_hop_fpt, next_hop_cmc, sw1):
    DC = "BGP-CMC2" if next_hop_fpt in ("10.10.50.2", "10.10.60.2") else "BGP-CMC"
    DC_FPT = "BGP-FPT-HN"
    cmd_type = "set" if action == "ban" else "delete"
    result1 = []
    result2 = []

#    if ip == "103.200.24.70" or ip == "103.200.24.66":
#       result2 = [
#        f"{cmd_type} routing-instances {DC} routing-options static route {ip} next-hop {next_hop_fpt}",
#        f"{cmd_type} policy-options policy-statement black-hole-ALL term 1 from route-filter {ip}/32 exact"
#       ]
#        return result2

    result1 += [
        f"{cmd_type} routing-instances {DC} routing-options static route {ip} next-hop {next_hop_cmc}",
        f"{cmd_type} policy-options policy-statement black-hole-QT term 1 from route-filter {ip}/32 exact"
    ]
    
    result2 += [
        f"{cmd_type} routing-instances {DC_FPT} routing-options static route {ip} next-hop {next_hop_fpt}",
        f"{cmd_type} policy-options policy-statement black-hole-QT term 1 from route-filter {ip}/32 exact"
    ]
   
    return result1, result2

def apply_config(device, commands, device_name):
    try:
        with ConnectHandler(**DEVICES[device]) as net_connect:
            print(f"Đã kết nối đến {device_name}")
            #print(commands)
            net_connect.config_mode()
            net_connect.send_config_set(commands)
            net_connect.commit()
            net_connect.exit_config_mode()
            net_connect.disconnect()
    except Exception as e:
        print(f"Lỗi khi cấu hình {device_name}: {str(e)}")
    finally:
        print(f"Hoàn tất thực thi ở {device_name}")

def main():
    client_ip = sys.argv[1]
    data_direction = sys.argv[2]
    pps_as_string = int(sys.argv[3])
    action = sys.argv[4]
    print(f"Blocking IP: {client_ip}")

    for network, (next_hop_fpt, next_hop_cmc) in IP_RANGES.items():
        if ipaddress.ip_address(client_ip) in ipaddress.ip_network(network, strict=False):
            sw2 = 'EXE1' if next_hop_fpt in ('10.10.60.2', '10.10.50.2') else 'EXV5'
            sw1 = 'EXV5'
            print(sw1)
            config1,config2 = get_config_commands(client_ip, action, next_hop_fpt, next_hop_cmc, sw1)
            apply_config(sw1, config1, sw1)
            if next_hop_fpt != "10.10.22.2":
                apply_config(sw2, config2, sw2)
            return

    print("IP không thuộc dải FPT-HN và CMC-HN")
    sys.exit(1)

if __name__ == "__main__":
    main()
