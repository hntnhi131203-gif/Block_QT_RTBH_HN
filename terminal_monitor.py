#!/usr/bin/env python3
"""
Terminal UI Monitor cho Allsite HCM Service
Dùng rich library để hiển thị realtime trong terminal
"""

import requests
import time
import sys
from datetime import datetime
from threading import Thread

try:
    from rich.console import Console
    from rich.table import Table
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.live import Live
    from rich.align import Align
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("❌ Cần cài đặt: pip install rich")
    print("   Hoặc chạy: check_status.py (fallback mode)")
    sys.exit(1)

console = Console()

class ServiceMonitor:
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        self.url = f'http://{host}:{port}/status'
        self.status = None
        self.error = None
        
    def fetch(self):
        try:
            response = requests.get(self.url, timeout=2)
            self.status = response.json()
            self.error = None
        except Exception as e:
            self.error = str(e)
            self.status = None
    
    def get_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=6),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        layout["header"].update(self._get_header())
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        if self.error:
            layout["body"]["left"].update(self._get_error())
            layout["body"]["right"].update(self._get_error())
        else:
            layout["body"]["left"].split_column(
                Layout(name="queue"),
                Layout(name="batch")
            )
            layout["body"]["left"]["queue"].update(self._get_queue())
            layout["body"]["left"]["batch"].update(self._get_batch())
            layout["body"]["right"].update(self._get_switches())
        
        layout["footer"].update(self._get_footer())
        
        return layout
    
    def _get_header(self):
        return Panel(
            Align.center("[bold cyan]🛡️  DDoS PROTECTION MONITOR[/bold cyan]"),
            title="[bold]Allsite HCM Service[/bold]",
            style="blue",
            box=box.HEAVY
        )
    
    def _get_queue(self):
        if not self.status:
            return Panel("Đang kết nối...", title="📬 Hàng Chờ", style="yellow")
        
        queue = self.status.get('queue', {})
        size = queue.get('size', 0)
        
        # Màu sắc tùy theo size
        if size == 0:
            color = "green"
            icon = "✓"
        elif size < 10:
            color = "yellow"
            icon = "⚠"
        elif size < 50:
            color = "yellow"
            icon = "⚠"
        else:
            color = "red"
            icon = "✗"
        
        content = f"[{color}]{icon} {size} IP đang chờ xử lý[/{color}]"
        return Panel(
            Align.center(f"[bold {color}]{size}[/bold {color}]", vertical="middle"),
            title=f"📬 Hàng Chờ",
            border_style=color,
            style=f"{color} on black"
        )
    
    def _get_batch(self):
        if not self.status:
            return Panel("Đang kết nối...", title="⚙️  Batch", style="yellow")
        
        batch = self.status.get('current_batch', {})
        ips = batch.get('ips', [])
        count = batch.get('count', 0)
        age = batch.get('age_seconds', 0)
        
        if count == 0:
            content = "[dim]Không có IP đang xử lý[/dim]"
        else:
            content = f"[bold green]✓ {count} IP đang xử lý ({age}s)[/bold green]\n\n"
            for ip in ips:
                content += f"  [cyan]◆[/cyan] {ip}\n"
        
        return Panel(
            content,
            title="⚙️  Batch Hiện Tại",
            border_style="green" if count > 0 else "dim"
        )
    
    def _get_switches(self):
        if not self.status:
            return Panel("Đang kết nối...", title="🔌 Switches", style="yellow")
        
        switches = self.status.get('switches', {})
        
        table = Table(show_header=True, header_style="bold", box=box.MINIMAL)
        table.add_column("Switch", style="cyan", width=12)
        table.add_column("Trạng Thái", style="white")
        
        for name, status in switches.items():
            if status == "idle":
                badge = "[green]●[/green]"
                text = f"{badge} Rảnh"
                style = "green"
            elif "configuring" in status:
                badge = "[yellow]●[/yellow]"
                text = f"{badge} {status}"
                style = "yellow"
            elif "error" in status:
                badge = "[red]●[/red]"
                text = f"{badge} {status}"
                style = "red"
            else:
                badge = "[dim]●[/dim]"
                text = f"{badge} {status}"
                style = "dim"
            
            table.add_row(name, text, style=style)
        
        return Panel(
            table,
            title="🔌 Switch Core",
            border_style="cyan"
        )
    
    def _get_error(self):
        return Panel(
            f"[red]❌ Lỗi: {self.error}[/red]",
            title="⚠️ Error",
            style="red on black",
            border_style="red"
        )
    
    def _get_footer(self):
        if self.status:
            timestamp = self.status.get('timestamp', '--:--:--')
            refresh_text = f"[green]↻[/green] Tự động cập nhật | [cyan]Lần cuối: {timestamp}[/cyan]"
        else:
            refresh_text = "[red]✗[/red] Không thể kết nối"
        
        return Panel(
            Align.center(refresh_text),
            style="dim"
        )

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Terminal Monitor cho Allsite HCM Service')
    parser.add_argument('--host', default='127.0.0.1', help='Service host')
    parser.add_argument('--port', type=int, default=5000, help='Service port')
    args = parser.parse_args()
    
    monitor = ServiceMonitor(args.host, args.port)
    
    # Update liên tục mỗi 1 giây
    with Live(console=console, refresh_per_second=1) as live:
        try:
            while True:
                monitor.fetch()
                live.update(monitor.get_layout())
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]👋 Thoát monitor[/yellow]")
            sys.exit(0)

if __name__ == '__main__':
    main()
