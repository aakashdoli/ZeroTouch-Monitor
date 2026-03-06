import argparse
import json
import os
import platform
import socket
import sys
import time
import urllib.request
import urllib.error
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from monitor.metrics import MetricsCollector
from monitor.smart_engine import SmartProcessEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ZeroTouchAgent:

    def __init__(self, server_url: str, machine_name: str, interval: int = 2, api_key: str = ""):
        self.server_url = server_url.rstrip("/")
        self.machine_name = machine_name
        self.interval = interval
        self.api_key = api_key
        self.machine_id = self._get_machine_id()
        self.collector = MetricsCollector()
        self.engine = SmartProcessEngine()
        self._registered = False

    def _get_machine_id(self) -> str:
        hostname = socket.gethostname()
        system = platform.system()
        return f"{hostname}-{system}".lower().replace(" ", "-")

    def _post(self, endpoint: str, data: dict) -> bool:
        try:
            url = f"{self.server_url}{endpoint}"
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self.api_key,
                    "X-Machine-ID": self.machine_id,
                }
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except urllib.error.URLError as e:
            logger.warning(f"Server unreachable: {e}")
            return False
        except Exception as e:
            logger.error(f"POST failed: {e}")
            return False

    def register(self) -> bool:
        data = {
            "machine_id": self.machine_id,
            "machine_name": self.machine_name,
            "hostname": socket.gethostname(),
            "os": platform.system(),
            "os_version": platform.version(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "registered_at": time.time(),
        }
        ok = self._post("/api/machines/register", data)
        if ok:
            logger.info(f"Registered as '{self.machine_name}' ({self.machine_id})")
        else:
            logger.error("Registration failed - will retry")
        return ok

    def collect_and_send(self):
        try:
            snap = self.collector.snapshot()
            classified = self.engine.classify_processes()

            top_procs = []
            for p in classified[:15]:
                top_procs.append({
                    "pid": p.pid,
                    "name": p.name,
                    "cpu_percent": p.cpu_percent,
                    "memory_percent": p.memory_percent,
                    "memory_mb": p.memory_mb,
                    "status": p.status,
                    "category": p.category,
                    "killable": p.killable,
                    "protect_reason": p.protect_reason,
                    "cpu_idle_seconds": p.cpu_idle_seconds,
                    "minutes_since_interaction": p.minutes_since_interaction,
                })

            payload = {
                "machine_id": self.machine_id,
                "machine_name": self.machine_name,
                "timestamp": time.time(),
                "cpu": {
                    "percent": snap.cpu.percent,
                    "per_core": snap.cpu.per_core,
                    "frequency_mhz": snap.cpu.frequency_mhz,
                    "load_avg_1m": snap.cpu.load_avg_1m,
                    "load_avg_5m": snap.cpu.load_avg_5m,
                    "load_avg_15m": snap.cpu.load_avg_15m,
                },
                "memory": {
                    "percent": snap.memory.percent,
                    "used_gb": snap.memory.used_gb,
                    "total_gb": snap.memory.total_gb,
                    "available_gb": snap.memory.available_gb,
                    "swap_percent": snap.memory.swap_percent,
                },
                "disk": {
                    "partitions": snap.disk.partitions,
                    "read_mb": snap.disk.read_mb,
                    "write_mb": snap.disk.write_mb,
                },
                "network": {
                    "bytes_sent_mb": snap.network.bytes_sent_mb,
                    "bytes_recv_mb": snap.network.bytes_recv_mb,
                    "packets_sent": snap.network.packets_sent,
                    "packets_recv": snap.network.packets_recv,
                    "errors_in": snap.network.errors_in,
                    "errors_out": snap.network.errors_out,
                },
                "top_processes": top_procs,
                "os": platform.system(),
                "hostname": snap.hostname,
            }

            self._post("/api/metrics", payload)

        except Exception as e:
            logger.error(f"Metrics error: {e}")

    def handle_commands(self):
        try:
            url = f"{self.server_url}/api/commands/{self.machine_id}"
            req = urllib.request.Request(url, headers={
                "X-API-Key": self.api_key,
                "X-Machine-ID": self.machine_id,
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    commands = json.loads(resp.read().decode())
                    for cmd in commands:
                        self._execute_command(cmd)
        except Exception:
            pass

    def _execute_command(self, cmd: dict):
        action = cmd.get("action")

        if action == "kill_process":
            pid = cmd.get("pid")
            if pid:
                import psutil
                try:
                    proc = psutil.Process(pid)
                    name = proc.name()
                    proc.terminate()
                    logger.info(f"Killed '{name}' (PID {pid}) via remote command")
                    self._post("/api/commands/result", {
                        "command_id": cmd.get("id"),
                        "machine_id": self.machine_id,
                        "success": True,
                        "message": f"Killed {name} (PID {pid})"
                    })
                except Exception as e:
                    self._post("/api/commands/result", {
                        "command_id": cmd.get("id"),
                        "machine_id": self.machine_id,
                        "success": False,
                        "message": str(e)
                    })

        elif action == "smart_clean":
            classified = self.engine.classify_processes()
            candidates = self.engine.get_kill_candidates(classified, 3)
            results = [self.engine.smart_kill(p) for p in candidates]
            logger.info(f"Smart clean: killed {len(results)} idle processes")

    def run(self):
        logger.info(f"ZeroTouch Agent starting — {self.machine_name} → {self.server_url}")

        while not self._registered:
            if self.register():
                self._registered = True
            else:
                time.sleep(5)

        tick = 0
        while True:
            try:
                self.collect_and_send()
                if tick % 5 == 0:
                    self.handle_commands()
                tick += 1
                time.sleep(self.interval)
            except KeyboardInterrupt:
                logger.info("Agent stopped.")
                break
            except Exception as e:
                logger.error(f"Agent error: {e}")
                time.sleep(self.interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroTouch-Monitor Agent")
    parser.add_argument("--server", required=True, help="e.g. http://192.168.1.10:8000")
    parser.add_argument("--name", default=socket.gethostname())
    parser.add_argument("--interval", type=int, default=2)
    parser.add_argument("--api-key", default="zerotouch-default-key")
    args = parser.parse_args()

    agent = ZeroTouchAgent(
        server_url=args.server,
        machine_name=args.name,
        interval=args.interval,
        api_key=args.api_key,
    )
    agent.run()