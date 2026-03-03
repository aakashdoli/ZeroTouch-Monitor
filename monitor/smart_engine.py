import time
import logging
import platform
import subprocess
import psutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

OS = platform.system()   # "Darwin" | "Windows" | "Linux"

# ─── System processes — NEVER kill ───────────────────────────────────────────
SYSTEM_PROTECTED_KEYWORDS = {
    # macOS
    "kernel_task", "launchd", "loginwindow", "windowserver", "coreaudiod",
    "cfprefsd", "diskarbitrationd", "configd", "notifyd", "securityd",
    "trustd", "syspolicyd", "watchdogd", "powerd", "hidd", "bluetoothd",
    "airportd", "mdnsresponder", "opendirectoryd", "sandboxd",
    # Linux
    "init", "kthreadd", "ksoftirqd", "kworker", "systemd", "dbus-daemon",
    "networkmanager", "sshd", "cron", "Xorg", "gnome-shell", "plasmashell",
    "pulseaudio", "pipewire", "wpa_supplicant", "avahi-daemon",
    # Windows
    "system", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "svchost.exe", "explorer.exe", "dwm.exe", "winlogon.exe",
    "taskhost.exe", "spoolsv.exe", "audiodg.exe",
    # ZeroTouch itself
    "streamlit", "zerotouch", "python", "python3", "python.exe",
}

SYSTEM_USERNAMES = {
    # Mac
    "root", "_windowserver", "_spotlight", "_networkd",
    "_mdnsresponder", "daemon", "_coreaudiod",
    # Linux
    "www-data", "nobody", "messagebus", "systemd-network",
    # Windows
    "system", "local service", "network service",
}

USER_INTERACTION_SAFE_WINDOW = 30 * 60   # 30 minutes
CPU_IDLE_THRESHOLD_SECONDS   = 4 * 60   # 4 minutes
CPU_IDLE_PERCENT             = 2.0      # below 2% = idle


@dataclass
class ProcessClassification:
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    status: str
    username: str
    category: str            # active | recently_used | idle_candidate | system | background
    killable: bool
    protect_reason: str
    cpu_idle_seconds: float
    minutes_since_interaction: float


@dataclass
class KillEvent:
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float
    reason: str
    freed_cpu: float
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = False
    message: str = ""


# ─── Platform-specific: Active App Detection ─────────────────────────────────

def get_active_app_name() -> Optional[str]:
    """Get currently focused application name. Cross-platform."""
    try:
        if OS == "Darwin":
            script = '''tell application "System Events"
    set frontApp to first application process whose frontmost is true
    return name of frontApp
end tell'''
            result = subprocess.run(["osascript", "-e", script],
                                    capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                return result.stdout.strip()

        elif OS == "Windows":
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc = psutil.Process(pid.value)
            return proc.name()

        elif OS == "Linux":
            # Try xdotool (most common)
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                return result.stdout.strip()
            # Fallback: wmctrl
            result = subprocess.run(
                ["wmctrl", "-a", ":ACTIVE:"],
                capture_output=True, text=True, timeout=3
            )
    except Exception:
        pass
    return None


def get_recently_used_apps() -> dict:
    """
    Get dict of {app_name_lower: last_used_timestamp} for all recently used apps.
    Cross-platform implementation.
    """
    now = time.time()
    app_times = {}

    try:
        if OS == "Darwin":
            # lsappinfo gives us last activation time for every running app
            result = subprocess.run(["lsappinfo", "list"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                current_app = None
                MAC_EPOCH_OFFSET = 978307200  # Mac absolute time → Unix time
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if '"CFBundleName"' in line or '"bundlename"' in line.lower():
                        parts = line.split('=')
                        if len(parts) >= 2:
                            current_app = parts[-1].strip().strip('"').lower()
                    if current_app and 'lastactivationtime' in line.lower():
                        parts = line.split('=')
                        if len(parts) >= 2:
                            try:
                                ts = float(parts[-1].strip())
                                app_times[current_app] = ts + MAC_EPOCH_OFFSET
                            except ValueError:
                                pass

        elif OS == "Windows":
            # On Windows use psutil to get process create times as proxy
            # Real last-used would need win32 API — use create_time as fallback
            for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                try:
                    name = (proc.info['name'] or "").lower()
                    ct = proc.info['create_time'] or 0
                    # Windows doesn't expose last interaction easily
                    # Use process create time — not perfect but safe
                    app_times[name] = ct
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        elif OS == "Linux":
            # Use /proc/{pid}/stat atime as proxy for recent activity
            import os
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pid = proc.info['pid']
                    name = (proc.info['name'] or "").lower()
                    stat_path = f"/proc/{pid}/stat"
                    if os.path.exists(stat_path):
                        atime = os.path.getatime(stat_path)
                        app_times[name] = atime
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    pass

    except Exception as e:
        logger.debug(f"get_recently_used_apps error: {e}")

    return app_times


def send_notification(title: str, message: str):
    """Send desktop notification. Cross-platform."""
    def _notify():
        try:
            if OS == "Darwin":
                with open("/tmp/ztm_notify.scpt", "w") as f:
                    f.write(f'display notification "{message}" with title "{title}" sound name "Basso"\n')
                subprocess.run(["osascript", "/tmp/ztm_notify.scpt"], timeout=5)

            elif OS == "Windows":
                try:
                    from win10toast import ToastNotifier
                    ToastNotifier().show_toast(title, message, duration=5, threaded=True)
                except ImportError:
                    # Fallback: PowerShell
                    ps_script = (
                        f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms");'
                        f'$n=New-Object System.Windows.Forms.NotifyIcon;'
                        f'$n.Icon=[System.Drawing.SystemIcons]::Information;'
                        f'$n.BalloonTipTitle="{title}";'
                        f'$n.BalloonTipText="{message}";'
                        f'$n.Visible=$True;$n.ShowBalloonTip(5000)'
                    )
                    subprocess.run(["powershell", "-Command", ps_script], timeout=10)

            elif OS == "Linux":
                subprocess.run(["notify-send", title, message], timeout=5)

        except Exception as e:
            logger.debug(f"Notification error: {e}")

    import threading
    threading.Thread(target=_notify, daemon=True).start()


# ─── Smart Engine ─────────────────────────────────────────────────────────────

class SmartProcessEngine:

    def __init__(self):
        self.auto_kill_enabled = True
        self.cpu_high_threshold = 80.0
        self.cpu_critical_threshold = 90.0
        self.sustained_seconds = 30
        self.critical_seconds = 15

        self._cpu_high_since: Optional[float] = None
        self._cpu_critical_since: Optional[float] = None

        # {pid: [(timestamp, cpu_percent), ...]}
        self._proc_cpu_samples: dict[int, list] = {}

        # App interaction cache
        self._app_times: dict = {}
        self._app_times_updated: float = 0

        self.kill_log: list[KillEvent] = []

    def _refresh_app_times(self):
        now = time.time()
        if now - self._app_times_updated >= 10:
            self._app_times = get_recently_used_apps()
            self._app_times_updated = now

    def _last_interaction(self, name: str) -> float:
        """Return last interaction timestamp for a process name. 0 if unknown."""
        self._refresh_app_times()
        name_lower = name.lower()
        # Direct match
        if name_lower in self._app_times:
            return self._app_times[name_lower]
        # Partial match
        for app, ts in self._app_times.items():
            if app in name_lower or name_lower in app:
                return ts
        return 0.0

    def _update_cpu_history(self, pid: int, cpu: float):
        now = time.time()
        samples = self._proc_cpu_samples.get(pid, [])
        samples.append((now, cpu))
        cutoff = now - 600  # keep 10 min
        self._proc_cpu_samples[pid] = [(t, c) for t, c in samples if t >= cutoff]

    def _cpu_idle_seconds(self, pid: int) -> float:
        samples = self._proc_cpu_samples.get(pid, [])
        if not samples:
            return 0.0
        now = time.time()
        # Find last time process had real CPU activity
        for ts, cpu in reversed(samples):
            if cpu >= CPU_IDLE_PERCENT:
                return now - ts
        # All samples were idle — idle since first sample
        return now - samples[0][0]

    def _is_system(self, name: str, username: str) -> bool:
        name_lower = name.lower()
        for kw in SYSTEM_PROTECTED_KEYWORDS:
            if kw.lower() in name_lower:
                return True
        if username.lower() in SYSTEM_USERNAMES:
            return True
        return False

    def classify_processes(self) -> list[ProcessClassification]:
        now = time.time()
        active_app = get_active_app_name()
        results = []

        for proc in psutil.process_iter([
            'pid', 'name', 'cpu_percent', 'memory_percent',
            'memory_info', 'status', 'username'
        ]):
            try:
                info  = proc.info
                pid   = info['pid']
                name  = info['name'] or "unknown"
                cpu   = round(info['cpu_percent'] or 0, 1)
                mem_p = round(info['memory_percent'] or 0, 1)
                mem_m = round((info['memory_info'].rss if info['memory_info'] else 0) / 1024**2, 1)
                status   = info['status'] or "unknown"
                username = info['username'] or "unknown"

                self._update_cpu_history(pid, cpu)
                idle_secs = self._cpu_idle_seconds(pid)
                last_used = self._last_interaction(name)
                mins_since = (now - last_used) / 60 if last_used > 0 else 999

                category     = "background"
                killable     = False
                protect_reason = ""

                # Rule 1: System process → always protect
                if self._is_system(name, username):
                    category = "system"
                    protect_reason = "System process"

                # Rule 2: Currently active app → always protect
                elif active_app and active_app.lower() in name.lower():
                    category = "active"
                    protect_reason = f"Currently active: {active_app}"

                # Rule 3: Used within 30 min → protect
                elif last_used > 0 and mins_since < 30:
                    category = "recently_used"
                    protect_reason = f"Used {mins_since:.0f} min ago"

                # Rule 4: Both signals clear → kill candidate
                elif (idle_secs >= CPU_IDLE_THRESHOLD_SECONDS and
                      mins_since >= 30 and
                      cpu > 0.5):
                    category = "idle_candidate"
                    killable  = True

                # Rule 5: Unknown interaction history + doing CPU work → be safe
                elif last_used == 0 and cpu >= 5.0:
                    category = "background"
                    protect_reason = "Unknown history — being cautious"

                else:
                    category = "background"
                    protect_reason = "Insufficient idle time"

                results.append(ProcessClassification(
                    pid=pid, name=name,
                    cpu_percent=cpu, memory_percent=mem_p, memory_mb=mem_m,
                    status=status, username=username,
                    category=category, killable=killable,
                    protect_reason=protect_reason,
                    cpu_idle_seconds=idle_secs,
                    minutes_since_interaction=mins_since,
                ))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        results.sort(key=lambda p: p.cpu_percent, reverse=True)
        return results

    def get_kill_candidates(self, classified: list, max_candidates: int = 3) -> list:
        return [p for p in classified if p.killable][:max_candidates]

    def smart_kill(self, proc: ProcessClassification) -> KillEvent:
        event = KillEvent(
            pid=proc.pid, name=proc.name,
            cpu_percent=proc.cpu_percent, memory_mb=proc.memory_mb,
            reason=(f"Idle {proc.cpu_idle_seconds/60:.1f}min CPU, "
                    f"not used {proc.minutes_since_interaction:.0f}min"),
            freed_cpu=proc.cpu_percent,
        )
        try:
            p = psutil.Process(proc.pid)
            p.terminate()
            try:
                p.wait(timeout=3)
            except psutil.TimeoutExpired:
                p.kill()
            event.success = True
            event.message = (f"✅ Killed '{proc.name}' (PID {proc.pid}) — "
                             f"freed ~{proc.cpu_percent:.1f}% CPU | "
                             f"idle {proc.cpu_idle_seconds/60:.1f}min, "
                             f"not used {proc.minutes_since_interaction:.0f}min")
            logger.info(event.message)
        except psutil.NoSuchProcess:
            event.success = False
            event.message = f"⚠️ '{proc.name}' already exited"
        except psutil.AccessDenied:
            event.success = False
            event.message = f"❌ Permission denied killing '{proc.name}'"
        except Exception as e:
            event.success = False
            event.message = f"❌ Error: {e}"

        self.kill_log.append(event)
        return event

    def check_and_auto_kill(self, current_cpu: float, classified: list) -> list:
        if not self.auto_kill_enabled:
            return []

        now = time.time()
        events = []

        if current_cpu >= self.cpu_critical_threshold:
            if self._cpu_critical_since is None:
                self._cpu_critical_since = now
            elif now - self._cpu_critical_since >= self.critical_seconds:
                for proc in self.get_kill_candidates(classified, 2):
                    events.append(self.smart_kill(proc))
                self._cpu_critical_since = now
        else:
            self._cpu_critical_since = None

        if current_cpu >= self.cpu_high_threshold:
            if self._cpu_high_since is None:
                self._cpu_high_since = now
            elif now - self._cpu_high_since >= self.sustained_seconds:
                for proc in self.get_kill_candidates(classified, 1):
                    if proc.pid not in [e.pid for e in events]:
                        events.append(self.smart_kill(proc))
                self._cpu_high_since = now
        else:
            self._cpu_high_since = None

        return events

    def get_kill_log(self) -> list:
        return list(reversed(self.kill_log))

    def clear_kill_log(self):
        self.kill_log.clear()