"""
ZeroTouch-Monitor - Core Metrics Collector
Collects CPU, Memory, Disk, Network I/O, and Top Processes metrics using psutil.
"""

import psutil
import time
import os
import signal
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CPUMetrics:
    percent: float
    per_core: list
    frequency_mhz: float
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MemoryMetrics:
    total_gb: float
    used_gb: float
    available_gb: float
    percent: float
    swap_total_gb: float
    swap_used_gb: float
    swap_percent: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DiskMetrics:
    partitions: list
    read_mb: float
    write_mb: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NetworkMetrics:
    bytes_sent_mb: float
    bytes_recv_mb: float
    packets_sent: int
    packets_recv: int
    errors_in: int
    errors_out: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    status: str
    username: str


@dataclass
class SystemSnapshot:
    cpu: CPUMetrics
    memory: MemoryMetrics
    disk: DiskMetrics
    network: NetworkMetrics
    top_processes: list        # list of ProcessInfo sorted by CPU
    hostname: str
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """Collects all system metrics in a single snapshot."""

    def __init__(self):
        self._prev_net_io = psutil.net_io_counters()
        self._prev_disk_io = psutil.disk_io_counters()
        self._prev_time = time.time()

    def collect_cpu(self) -> CPUMetrics:
        load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0)
        freq = psutil.cpu_freq()
        return CPUMetrics(
            percent=psutil.cpu_percent(interval=0.5),
            per_core=psutil.cpu_percent(percpu=True, interval=0),
            frequency_mhz=freq.current if freq else 0.0,
            load_avg_1m=load[0],
            load_avg_5m=load[1],
            load_avg_15m=load[2],
        )

    def collect_memory(self) -> MemoryMetrics:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        gb = 1024 ** 3
        return MemoryMetrics(
            total_gb=round(mem.total / gb, 2),
            used_gb=round(mem.used / gb, 2),
            available_gb=round(mem.available / gb, 2),
            percent=mem.percent,
            swap_total_gb=round(swap.total / gb, 2),
            swap_used_gb=round(swap.used / gb, 2),
            swap_percent=swap.percent,
        )

    def collect_disk(self) -> DiskMetrics:
        partitions = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / 1024**3, 2),
                    "used_gb": round(usage.used / 1024**3, 2),
                    "free_gb": round(usage.free / 1024**3, 2),
                    "percent": usage.percent,
                })
            except PermissionError:
                continue

        disk_io = psutil.disk_io_counters()
        mb = 1024 ** 2
        read_mb = round((disk_io.read_bytes - self._prev_disk_io.read_bytes) / mb, 2) if self._prev_disk_io else 0
        write_mb = round((disk_io.write_bytes - self._prev_disk_io.write_bytes) / mb, 2) if self._prev_disk_io else 0
        self._prev_disk_io = disk_io
        return DiskMetrics(partitions=partitions, read_mb=max(read_mb, 0), write_mb=max(write_mb, 0))

    def collect_network(self) -> NetworkMetrics:
        net = psutil.net_io_counters()
        mb = 1024 ** 2
        sent = round((net.bytes_sent - self._prev_net_io.bytes_sent) / mb, 4)
        recv = round((net.bytes_recv - self._prev_net_io.bytes_recv) / mb, 4)
        self._prev_net_io = net
        return NetworkMetrics(
            bytes_sent_mb=max(sent, 0),
            bytes_recv_mb=max(recv, 0),
            packets_sent=net.packets_sent,
            packets_recv=net.packets_recv,
            errors_in=net.errin,
            errors_out=net.errout,
        )

    def collect_top_processes(self, limit: int = 10) -> list:
        """Get top processes sorted by CPU usage."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'status', 'username']):
            try:
                info = proc.info
                if info['cpu_percent'] is None:
                    continue
                processes.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'] or "unknown",
                    cpu_percent=round(info['cpu_percent'], 1),
                    memory_percent=round(info['memory_percent'] or 0, 1),
                    memory_mb=round((info['memory_info'].rss if info['memory_info'] else 0) / 1024**2, 1),
                    status=info['status'] or "unknown",
                    username=info['username'] or "unknown",
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU descending, then memory
        processes.sort(key=lambda p: (p.cpu_percent, p.memory_percent), reverse=True)
        return processes[:limit]

    def snapshot(self) -> SystemSnapshot:
        """Collect all metrics and return a full system snapshot."""
        import socket
        return SystemSnapshot(
            cpu=self.collect_cpu(),
            memory=self.collect_memory(),
            disk=self.collect_disk(),
            network=self.collect_network(),
            top_processes=self.collect_top_processes(),
            hostname=socket.gethostname(),
        )


def kill_process(pid: int) -> tuple:
    """
    Kill a process by PID.
    Returns (success: bool, message: str)
    """
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()          # Graceful SIGTERM first
        try:
            proc.wait(timeout=3)  # Wait up to 3 seconds
        except psutil.TimeoutExpired:
            proc.kill()           # Force SIGKILL if still alive
        return True, f"✅ Process '{name}' (PID {pid}) terminated successfully."
    except psutil.NoSuchProcess:
        return False, f"❌ Process with PID {pid} not found."
    except psutil.AccessDenied:
        return False, f"❌ Permission denied — cannot kill PID {pid}. Try running with sudo."
    except Exception as e:
        return False, f"❌ Error killing PID {pid}: {e}"