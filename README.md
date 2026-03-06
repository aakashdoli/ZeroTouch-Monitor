<div align="center">

# ⚡ ZeroTouch-Monitor

### Production-Grade System Monitoring with Intelligent Process Management

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Platform](https://img.shields.io/badge/Platform-Mac%20%7C%20Windows%20%7C%20Linux-lightgrey?style=for-the-badge)](https://github.com/aakashdoli/ZeroTouch-Monitor)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**Monitor every machine in your infrastructure from one dashboard.**  
**Intelligently kill idle CPU hogs without disrupting your active work.**

[Features](#-features) • [Demo](#-demo) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [Multi-Machine](#-multi-machine-setup)

---

![ZeroTouch-Monitor Dashboard](https://raw.githubusercontent.com/aakashdoli/ZeroTouch-Monitor/main/docs/dashboard.png)

</div>

---

## 🚀 The Problem

Every developer has experienced this:
- Your laptop is **burning hot**, fan running at max
- You're in the middle of **important work** in VS Code
- Some background app is **eating 80% of your CPU**
- You have no idea **which app** or **why**

Traditional monitors like Mac Activity Monitor just **show** the problem.  
**ZeroTouch-Monitor solves it — automatically.**

---

## ✨ Features

### 🖥 Real-Time Monitoring
- **CPU** — overall usage, per-core breakdown, frequency, load average
- **Memory** — used/available RAM, swap usage
- **Disk** — partition usage, read/write I/O speeds
- **Network** — bytes sent/received, packet counts, error rates

### 🧠 Smart Process Manager *(The killer feature)*
> Not all process killers are equal. ZeroTouch understands **context**.

| Scenario | What ZeroTouch Does |
|---|---|
| Chrome is your active app | 🛡 **PROTECTED** — never touched |
| VS Code open, you're in Chrome for 5 min | 🛡 **PROTECTED** — used within 30 min |
| Zoom Updater running in background for 2 hours | 🔴 **KILL CANDIDATE** |
| System daemon eating CPU | 🛡 **PROTECTED** — system process |

**Dual-Signal Intelligence:**
- **Signal 1** — User Interaction: Has the user touched this app in the last 30 minutes?
- **Signal 2** — CPU Idle: Has this process had < 2% CPU for 4+ continuous minutes?

Both must be true before any process becomes a kill candidate.

### 🌐 Multi-Machine Monitoring
Monitor your **entire infrastructure** from one central dashboard:
```
[MacBook Pro]  ──→  ZeroTouch Central Server  ←──  [Windows PC]
[Linux Server] ──→         Dashboard          ←──  [Office Mac]
```

### 🔔 Smart Alerts
- Desktop notifications (Mac/Linux/Windows)
- Configurable CPU, Memory, Disk thresholds
- 5-minute cooldown to prevent notification spam

### 🔫 Remote Process Kill
- Kill any process on any connected machine from the central dashboard
- Smart Clean — auto-kill idle CPU hogs remotely with one click

### 🐳 Docker Support
```bash
docker compose up zerotouch-web
```

---

## 📸 Demo

### Single Machine Dashboard
![Single Dashboard](https://raw.githubusercontent.com/aakashdoli/ZeroTouch-Monitor/main/docs/dashboard.png)

### 🔥 Top Processes — Who is eating your CPU?
![Process Manager](https://raw.githubusercontent.com/aakashdoli/ZeroTouch-Monitor/main/docs/process_manager.png)

### 💾 Disk Partitions + CPU Per Core
![Disk and Core](https://raw.githubusercontent.com/aakashdoli/ZeroTouch-Monitor/main/docs/multi_dashboard.png)

### 🌐 Multi-Machine Central Dashboard
![Central Dashboard](https://raw.githubusercontent.com/aakashdoli/ZeroTouch-Monitor/main/docs/central_dashboard.png)

### 🔍 Remote Machine Details + Process Kill
![Machine Details](https://raw.githubusercontent.com/aakashdoli/ZeroTouch-Monitor/main/docs/machine_details.png)

---

## ⚡ Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/aakashdoli/ZeroTouch-Monitor.git
cd ZeroTouch-Monitor
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Web Dashboard
```bash
PYTHONPATH=$(pwd) streamlit run dashboard/web.py
# Open http://localhost:8501
```

### 3. Run Terminal Dashboard
```bash
PYTHONPATH=$(pwd) python main.py
```

---

## 🌐 Multi-Machine Setup

### Step 1 — Start Central Server (on your main machine)
```bash
python server/server.py
# Server running at http://0.0.0.0:8000
```

### Step 2 — Start Central Dashboard
```bash
PYTHONPATH=$(pwd) streamlit run dashboard/multi_dashboard.py --server.port 8502
# Open http://localhost:8502
```

### Step 3 — Connect Any Machine (one command!)
```bash
# Mac / Linux:
curl -sSL http://YOUR_SERVER_IP:8000/install.sh | bash

# Windows:
# Open browser → http://YOUR_SERVER_IP:8000/install.py → save → double-click
```

That's it. The machine appears in your dashboard instantly. ✅

---

## 🏗 Architecture

```
ZeroTouch-Monitor/
│
├── monitor/
│   ├── metrics.py          # psutil-based metrics collector
│   │                       # CPU, Memory, Disk, Network, Top Processes
│   └── smart_engine.py     # Intelligent process classification engine
│                           # Dual-signal: interaction time + CPU idle time
│
├── dashboard/
│   ├── web.py              # Streamlit single-machine dashboard
│   ├── terminal.py         # Rich library terminal dashboard
│   └── multi_dashboard.py  # Multi-machine central dashboard
│
├── server/
│   └── server.py           # FastAPI central server
│                           # Receives metrics from all agents
│
├── agent/
│   └── agent.py            # Lightweight agent (runs on each machine)
│                           # Sends metrics to central server every 2s
│
├── installer/
│   ├── install.sh          # Mac/Linux one-line installer
│   └── install_windows.py  # Windows installer
│
├── alerts/
│   └── alerter.py          # Multi-channel alert system
│
└── config/
    └── config.yaml         # Thresholds and notification config
```

---

## ⚙️ Configuration

Edit `config/config.yaml`:

```yaml
alerts:
  cpu_threshold: 85.0       # Alert when CPU > 85%
  memory_threshold: 85.0    # Alert when Memory > 85%
  disk_threshold: 90.0      # Alert when Disk > 90%

  email:
    enabled: false
    smtp_host: smtp.gmail.com
    username: your@email.com
    password: your_app_password
    recipients: [alert@company.com]

  slack:
    enabled: false
    webhook_url: https://hooks.slack.com/your/webhook
```

---

## 🧠 Smart Kill Logic

```python
# A process becomes a KILL CANDIDATE only when ALL 3 are true:

1. ✅ CPU idle for 4+ continuous minutes (< 2% CPU)
2. ✅ User hasn't interacted with this app in 30+ minutes
3. ✅ Not a system process (kernel, launchd, svchost, etc.)

# Your active work is ALWAYS protected:
- Currently focused app        → 🛡 PROTECTED
- Used within last 30 minutes  → 🛡 PROTECTED
- System/OS process            → 🛡 PROTECTED
```

---

## 🆚 vs Mac Activity Monitor

| Feature | Mac Activity Monitor | ZeroTouch-Monitor |
|---|---|---|
| Real-time CPU/Memory | ✅ | ✅ |
| Per-core breakdown | ✅ | ✅ |
| Kill processes | ✅ Manual only | ✅ Manual + **Auto** |
| Web dashboard | ❌ | ✅ |
| Remote monitoring | ❌ | ✅ |
| Email/Slack alerts | ❌ | ✅ |
| Multi-machine | ❌ | ✅ |
| Windows/Linux support | ❌ | ✅ |
| Smart auto-kill | ❌ | ✅ |
| One-line install | ❌ | ✅ |
| Remote process kill | ❌ | ✅ |

---

## 🛠 Tech Stack

| Component | Technology |
|---|---|
| Metrics Collection | `psutil` |
| Web Dashboard | `Streamlit` + `Plotly` |
| Terminal Dashboard | `Rich` |
| Central Server | `FastAPI` + `uvicorn` |
| Process Intelligence | Custom dual-signal engine |
| Notifications | `osascript` / `notify-send` / PowerShell |
| Containerization | `Docker` + `docker-compose` |

---

## 📦 Requirements

```
Python 3.9+
psutil >= 5.9.0
streamlit >= 1.30.0
plotly >= 5.18.0
fastapi >= 0.104.0
uvicorn >= 0.24.0
rich >= 13.0.0
pyyaml >= 6.0
```

---

## 🗺 Roadmap

- [x] Real-time single machine monitoring
- [x] Smart process manager with intelligent kill
- [x] Multi-machine central server + dashboard
- [x] One-line cross-platform installer
- [x] Remote process kill from central dashboard
- [x] Cross-platform notifications (Mac/Linux/Windows)
- [ ] Historical data storage (SQLite/PostgreSQL)
- [ ] Anomaly detection with ML
- [ ] Mobile-friendly dashboard
- [ ] `pip install zerotouch-monitor`
- [ ] SaaS deployment with auth

---

## 🤝 Contributing

Pull requests are welcome! For major changes, open an issue first.

```bash
git clone https://github.com/aakashdoli/ZeroTouch-Monitor.git
cd ZeroTouch-Monitor
pip install -r requirements.txt
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

<div align="center">

**Built with ❤️ by [Aakash Doli](https://github.com/aakashdoli)**

⭐ Star this repo if you found it useful!

</div>
