"""
ZeroTouch-Monitor — Windows Agent Installer
Run: python install_windows.py
"""

import os
import sys
import json
import urllib.request
import subprocess
import shutil
import winreg
from pathlib import Path

SERVER_URL  = "__SERVER_URL__"
API_KEY     = "zerotouch-default-key"
INSTALL_DIR = Path(os.environ.get("APPDATA", "C:/ZeroTouch")) / "ZeroTouch-Monitor"


def info(msg):    print(f"  > {msg}")
def success(msg): print(f"  ✓ {msg}")
def error(msg):
    print(f"  ✗ {msg}")
    input("Press Enter to exit...")
    sys.exit(1)


def get_machine_name():
    import socket
    return os.environ.get("COMPUTERNAME", socket.gethostname())


def install_deps():
    info("Installing psutil...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "psutil", "--quiet"],
                            capture_output=True)
    if result.returncode == 0:
        success("psutil installed")
    else:
        print(f"  Warning: {result.stderr.decode()}")


def download_files(server_url: str):
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    monitor = INSTALL_DIR / "monitor"
    monitor.mkdir(exist_ok=True)

    files = {
        f"{server_url}/download/agent.py":        INSTALL_DIR / "agent.py",
        f"{server_url}/download/metrics.py":       monitor / "metrics.py",
        f"{server_url}/download/smart_engine.py":  monitor / "smart_engine.py",
    }
    for url, dest in files.items():
        try:
            urllib.request.urlretrieve(url, dest)
            success(f"Downloaded {dest.name}")
        except Exception as e:
            error(f"Failed to download {url}: {e}")

    (monitor / "__init__.py").touch()


def add_to_startup(bat_path: Path):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ZeroTouchMonitor", 0, winreg.REG_SZ, str(bat_path))
        winreg.CloseKey(key)
        success("Added to Windows startup")
    except Exception as e:
        print(f"  Warning: Could not add to startup: {e}")


def create_launcher(server_url: str, machine_name: str) -> Path:
    bat = INSTALL_DIR / "start_agent.bat"
    bat.write_text(
        f'@echo off\nset PYTHONPATH={INSTALL_DIR}\ncd /d "{INSTALL_DIR}"\n'
        f'"{sys.executable}" agent.py --server "{server_url}" --name "{machine_name}" --api-key "{API_KEY}"\n'
    )
    return bat


def main():
    print()
    print("  ZeroTouch-Monitor — Windows Installer")
    print("  ────────────────────────────────────────")

    server_url = SERVER_URL
    if "__SERVER_URL__" in server_url:
        server_url = input("  Server URL (e.g. http://192.168.1.45:8000): ").strip()
        if not server_url:
            error("Server URL required")

    default_name = get_machine_name()
    machine_name = input(f"  Machine name [{default_name}]: ").strip() or default_name

    print()
    info(f"Installing to {INSTALL_DIR}")
    info(f"Connecting to {server_url}")
    print()

    if sys.version_info < (3, 8):
        error("Python 3.8+ required")
    success(f"Python {sys.version.split()[0]}")

    install_deps()
    download_files(server_url)

    config = {"server_url": server_url, "machine_name": machine_name,
              "api_key": API_KEY, "interval": 2}
    (INSTALL_DIR / "config.json").write_text(json.dumps(config, indent=2))

    bat = create_launcher(server_url, machine_name)
    add_to_startup(bat)

    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop" / "ZeroTouch Monitor.bat"
    try:
        shutil.copy(bat, desktop)
        success("Desktop shortcut created")
    except Exception:
        pass

    env = os.environ.copy()
    env["PYTHONPATH"] = str(INSTALL_DIR)
    proc = subprocess.Popen(
        [sys.executable, str(INSTALL_DIR / "agent.py"),
         "--server", server_url, "--name", machine_name, "--api-key", API_KEY],
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )

    print()
    print(f"  ✓ Agent started! (PID: {proc.pid})")
    print(f"  Machine '{machine_name}' is now visible in the dashboard.")
    print()
    print(f"  To uninstall: delete {INSTALL_DIR}")
    print("               Task Manager → Startup → disable ZeroTouchMonitor")
    print()
    input("  Press Enter to close...")


if __name__ == "__main__":
    main()