"""
ZeroTouch-Monitor - Terminal Dashboard
Live terminal dashboard powered by Rich library.
"""

import time
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich import box
from monitor.metrics import MetricsCollector, SystemSnapshot


console = Console()


def _color_for(value: float, warn: float = 70, crit: float = 90) -> str:
    if value >= crit:
        return "bold red"
    if value >= warn:
        return "bold yellow"
    return "bold green"


def _make_header(snapshot: SystemSnapshot) -> Panel:
    now = snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    text = Text(justify="center")
    text.append("⚡ ZeroTouch-Monitor ", style="bold cyan")
    text.append(f"| Host: {snapshot.hostname} ", style="white")
    text.append(f"| {now}", style="dim white")
    return Panel(text, style="cyan", padding=(0, 1))


def _make_cpu_panel(snapshot: SystemSnapshot) -> Panel:
    cpu = snapshot.cpu
    table = Table(box=box.SIMPLE, expand=True, show_header=False)
    table.add_column("Metric", style="dim")
    table.add_column("Value")

    color = _color_for(cpu.percent)
    table.add_row("Overall", Text(f"{cpu.percent:.1f}%", style=color))
    table.add_row("Frequency", f"{cpu.frequency_mhz:.0f} MHz")
    table.add_row("Load Avg (1m/5m/15m)",
                  f"{cpu.load_avg_1m:.2f} / {cpu.load_avg_5m:.2f} / {cpu.load_avg_15m:.2f}")

    core_text = Text()
    for i, c in enumerate(cpu.per_core):
        core_text.append(f"C{i}:{c:.0f}% ", style=_color_for(c))
    table.add_row("Per Core", core_text)

    return Panel(table, title="[bold cyan]🖥  CPU[/bold cyan]", border_style="cyan")


def _make_memory_panel(snapshot: SystemSnapshot) -> Panel:
    mem = snapshot.memory
    table = Table(box=box.SIMPLE, expand=True, show_header=False)
    table.add_column("Metric", style="dim")
    table.add_column("Value")

    color = _color_for(mem.percent)
    table.add_row("Usage", Text(f"{mem.percent:.1f}%  ({mem.used_gb:.1f} / {mem.total_gb:.1f} GB)", style=color))
    table.add_row("Available", f"{mem.available_gb:.1f} GB")
    table.add_row("Swap", Text(f"{mem.swap_percent:.1f}%  ({mem.swap_used_gb:.1f} / {mem.swap_total_gb:.1f} GB)",
                               style=_color_for(mem.swap_percent)))

    return Panel(table, title="[bold magenta]🧠 Memory[/bold magenta]", border_style="magenta")


def _make_disk_panel(snapshot: SystemSnapshot) -> Panel:
    disk = snapshot.disk
    table = Table(box=box.SIMPLE, expand=True, show_header=True)
    table.add_column("Mount", style="dim")
    table.add_column("FS", style="dim")
    table.add_column("Total", justify="right")
    table.add_column("Used", justify="right")
    table.add_column("Free", justify="right")
    table.add_column("Usage %", justify="right")

    for p in disk.partitions:
        color = _color_for(p["percent"])
        table.add_row(
            p["mountpoint"], p["fstype"],
            f"{p['total_gb']:.1f} GB",
            f"{p['used_gb']:.1f} GB",
            f"{p['free_gb']:.1f} GB",
            Text(f"{p['percent']:.1f}%", style=color),
        )

    table.add_row("", "", "", "", "", "")
    table.add_row("[dim]I/O Read[/dim]", "", "", f"{disk.read_mb:.2f} MB", "", "")
    table.add_row("[dim]I/O Write[/dim]", "", "", f"{disk.write_mb:.2f} MB", "", "")

    return Panel(table, title="[bold yellow]💾 Disk[/bold yellow]", border_style="yellow")


def _make_network_panel(snapshot: SystemSnapshot) -> Panel:
    net = snapshot.network
    table = Table(box=box.SIMPLE, expand=True, show_header=False)
    table.add_column("Metric", style="dim")
    table.add_column("Value")

    table.add_row("Sent (this interval)", f"{net.bytes_sent_mb:.4f} MB")
    table.add_row("Received (this interval)", f"{net.bytes_recv_mb:.4f} MB")
    table.add_row("Total Packets Sent", f"{net.packets_sent:,}")
    table.add_row("Total Packets Recv", f"{net.packets_recv:,}")
    table.add_row("Errors In / Out",
                  Text(f"{net.errors_in} / {net.errors_out}",
                       style="bold red" if (net.errors_in + net.errors_out) > 0 else "green"))

    return Panel(table, title="[bold blue]🌐 Network I/O[/bold blue]", border_style="blue")


def _make_layout(snapshot: SystemSnapshot) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="top", ratio=2),
        Layout(name="bottom", ratio=3),
    )
    layout["top"].split_row(
        Layout(name="cpu"),
        Layout(name="memory"),
    )
    layout["header"].update(_make_header(snapshot))
    layout["top"]["cpu"].update(_make_cpu_panel(snapshot))
    layout["top"]["memory"].update(_make_memory_panel(snapshot))
    layout["bottom"].split_row(
        Layout(name="disk", ratio=2),
        Layout(name="network"),
    )
    layout["bottom"]["disk"].update(_make_disk_panel(snapshot))
    layout["bottom"]["network"].update(_make_network_panel(snapshot))
    return layout


def run_terminal_dashboard(interval: int = 2, alert_manager=None):
    """Run the live terminal dashboard."""
    collector = MetricsCollector()
    console.print("[bold cyan]Starting ZeroTouch-Monitor...[/bold cyan]")
    time.sleep(1)

    with Live(console=console, refresh_per_second=1, screen=True) as live:
        while True:
            try:
                snapshot = collector.snapshot()
                if alert_manager:
                    alert_manager.evaluate(snapshot)
                live.update(_make_layout(snapshot))
                time.sleep(interval)
            except KeyboardInterrupt:
                break

    console.print("\n[bold green]ZeroTouch-Monitor stopped.[/bold green]")