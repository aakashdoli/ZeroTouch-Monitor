import sys
import os
import subprocess
import time

# --- CONFIGURATION ---
EMAIL_SENDER = "ENTER_YOUR_EMAIL_HERE"
EMAIL_PASSWORD = "ENTER_YOUR_APP_PASSWORD_HERE"
EMAIL_RECEIVER = EMAIL_SENDER
# ---------------------

# CONSTANTS (DO NOT CHANGE THESE)
SERVICE_NAME = "com.aakash.final_monitor"
PLIST_FILENAME = f"{SERVICE_NAME}.plist"
USER_HOME = os.path.expanduser("~")
SCRIPT_PATH = os.path.join(USER_HOME, "Desktop", "background_monitor.py")
PLIST_PATH = os.path.join(USER_HOME, "Library/LaunchAgents", PLIST_FILENAME)
LOG_FILE = os.path.join(USER_HOME, "Desktop", "system_log_final.csv")
CURRENT_PYTHON = sys.executable

# --- THE MONITOR CODE (Hidden inside) ---
MONITOR_CODE = f"""import psutil, time, csv, os, smtplib
from email.mime.text import MIMEText
from datetime import datetime

USER_HOME = os.path.expanduser("~") 
LOG_FILE = "{LOG_FILE}"
CPU_THRESHOLD = 25.0
ALERT_COOLDOWN = 60

SENDER = "{EMAIL_SENDER}"
PASSWORD = "{EMAIL_PASSWORD}"
RECEIVER = "{EMAIL_RECEIVER}"
last_alert = 0

def send_email(cpu, app):
    global last_alert
    if (time.time() - last_alert) < ALERT_COOLDOWN: return
    try:
        msg = MIMEText(f"Time: {{datetime.now()}}\\nCPU: {{cpu}}%\\nApp: {{app}}")
        msg['Subject'] = f"⚠️ ALERT: CPU {{cpu}}%"
        msg['From'] = SENDER
        msg['To'] = RECEIVER
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(SENDER, PASSWORD)
            s.sendmail(SENDER, RECEIVER, msg.as_string())
        last_alert = time.time()
    except: pass

def monitor():
    try:
        with open(LOG_FILE, 'a', newline='') as f:
            w = csv.writer(f)
            while True:
                cpu = psutil.cpu_percent(interval=5)
                try:
                    procs = [p.info for p in psutil.process_iter(['name', 'cpu_percent']) if p.info['cpu_percent']]
                    top = sorted(procs, key=lambda p: p['cpu_percent'], reverse=True)[0] if procs else {{'name':'?', 'cpu_percent':0}}
                except: top = {{'name':'?', 'cpu_percent':0}}
                
                info = f"{{top['name']}} ({{top['cpu_percent']}}%)"
                if cpu > CPU_THRESHOLD: send_email(cpu, info)
                w.writerow([datetime.now(), cpu, info])
                f.flush()
    except: pass

if __name__ == "__main__":
    monitor()
"""

def clean_cleanup():
    """Forces macOS to forget the old service to prevent Error 5"""
    print("🧹 Cleaning up old processes...")
    # 1. Try to unload standard way
    subprocess.run(f"launchctl unload {PLIST_PATH}", shell=True, stderr=subprocess.DEVNULL)
    # 2. Force remove from memory (The fix for Error 5)
    subprocess.run(f"launchctl remove {SERVICE_NAME}", shell=True, stderr=subprocess.DEVNULL)
    # 3. Delete old plist file
    if os.path.exists(PLIST_PATH):
        os.remove(PLIST_PATH)
    time.sleep(1) # Give macOS a second to breathe

def start_monitor():
    clean_cleanup()
    print("🚀 Starting System Monitor...")
    
    # Write Python Script
    with open(SCRIPT_PATH, "w") as f:
        f.write(MONITOR_CODE)
        
    # Write Launch Agent
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{CURRENT_PYTHON}</string>
        <string>{SCRIPT_PATH}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""
    with open(PLIST_PATH, "w") as f:
        f.write(plist_content)
        
    # Start it
    result = subprocess.run(f"launchctl load {PLIST_PATH}", shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ SUCCESS! Monitor is running in the background.")
        print(f"📝 Logging to: {LOG_FILE}")
    else:
        print(f"❌ Error: {result.stderr}")

def stop_monitor():
    clean_cleanup()
    print("🛑 Monitor STOPPED. No more emails.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_monitor()
    else:
        start_monitor()