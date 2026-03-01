# ⚡ ZeroTouch-Monitor

> **Automated Python System Monitor with Real-Time Alerts and Dual Dashboard**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red?logo=streamlit)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](Dockerfile)
[![Maintenance](https://img.shields.io/badge/Maintained-Yes-green.svg)](https://github.com/aakashdoli/ZeroTouch-Monitor)

ZeroTouch-Monitor is a **production-grade, zero-configuration system monitoring tool** built in Python. It tracks CPU, Memory, Disk, and Network I/O in real-time and fires instant alerts via Email, Slack, and Desktop notifications — all from a beautiful terminal or web dashboard.

---

## 🖥 Dashboard Preview

### Terminal Dashboard (Rich)
```
┌────────────────────────────────────────────────────────────────┐
│         ⚡ ZeroTouch-Monitor | Host: myserver | 14:23:01       │
├───────────────────────────────┬────────────────────────────────┤
│  🖥  CPU                      │  🧠  Memory                    │
│  Overall       87.3%  🔴      │  Usage  62.1%  (9.9/16.0 GB)  │
│  Frequency     3600 MHz       │  Available     6.1 GB          │
│  Load Avg      1.2/0.9/0.8    │  Swap   0.0%   (0.0/2.0 GB)   │
│  Per Core  C0:90% C1:84% ...  │                                │
├───────────────────────────────┴────────────────────────────────┤
│  💾  Disk                                                       │
│  /         ext4   50GB used / 100GB total   50.0%  🟢          │
│  /home      ext4  120GB used / 500GB total  24.0%  🟢          │
├────────────────────────────────────────────────────────────────┤
│  🌐  Network I/O                                                │
│  Sent: 0.0023 MB  |  Recv: 0.0145 MB  |  Errors: 0            │
└────────────────────────────────────────────────────────────────┘
```

### Web Dashboard (Streamlit)
- 📊 Live line charts for CPU, Memory, Network over time
- 🔴 Alert banners when thresholds are breached
- 💾 Disk partition table
- 🖥 Per-core CPU meters
- ⚙️ Configurable thresholds via sidebar sliders

---

## ✨ Features

| Feature | Details |
|---|---|
| **Metrics** | CPU %, per-core, frequency, load avg · Memory, swap · Disk partitions, I/O · Network sent/recv/errors |
| **Alerts** | Email (SMTP/Gmail) · Slack (Webhook) · Desktop notifications |
| **Alert Cooldown** | Configurable cooldown to prevent alert flooding (default: 5 min) |
| **Terminal Dashboard** | Live Rich-powered terminal UI, color-coded by severity |
| **Web Dashboard** | Streamlit + Plotly with auto-refresh and live charts |
| **Config** | YAML file OR environment variables — no code changes needed |
| **Docker** | Single-command deployment with Docker Compose |
| **Logging** | Daily rotating log files in `logs/` directory |

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/aakashdoli/ZeroTouch-Monitor.git
cd ZeroTouch-Monitor
pip install -r requirements.txt
```

### 2. Run Terminal Dashboard
```bash
python main.py
```

### 3. Run Web Dashboard
```bash
streamlit run dashboard/web.py
# Open http://localhost:8501
```

### 4. Run Both Simultaneously
```bash
python main.py --mode both
```

---

## ⚙️ Configuration

Edit `config/config.yaml`:

```yaml
interval_seconds: 2     # How often to refresh metrics

alerts:
  cpu_threshold: 85.0   # Alert when CPU > 85%
  memory_threshold: 85.0
  disk_threshold: 90.0
  cooldown_seconds: 300 # Minimum 5 min between same alerts
  desktop_enabled: true

  email:
    enabled: true
    smtp_host: smtp.gmail.com
    smtp_port: 587
    username: your_email@gmail.com
    password: your_app_password   # Gmail App Password
    recipients:
      - you@example.com

  slack:
    enabled: true
    webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Environment Variables (for Docker/CI)
```bash
export EMAIL_USERNAME=your@gmail.com
export EMAIL_PASSWORD=your_app_password
export EMAIL_RECIPIENTS=alert@company.com
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

---

## 🐳 Docker Deployment

### Web Dashboard Only
```bash
docker compose up zerotouch-web
# Open http://localhost:8501
```

### With Custom Config
```bash
# Create .env file with your secrets
echo "SLACK_WEBHOOK_URL=https://hooks.slack.com/..." > .env
docker compose up
```

---

## 📁 Project Structure

```
ZeroTouch-Monitor/
├── main.py                    # Entry point & CLI
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── monitor/
│   ├── metrics.py             # Core metrics collection (psutil)
│   └── logger.py             # Logging setup
│
├── alerts/
│   └── alerter.py            # Email, Slack, Desktop alerters + AlertManager
│
├── dashboard/
│   ├── terminal.py           # Rich terminal live dashboard
│   └── web.py                # Streamlit web dashboard
│
├── config/
│   ├── config.yaml           # Default configuration
│   └── config_loader.py      # Config loader (YAML + env vars)
│
└── logs/                     # Auto-created daily log files
```

---

## 🛠 CLI Reference

```bash
python main.py [OPTIONS]

Options:
  --mode      terminal (default) | web | both
  --config    Path to config YAML (default: config/config.yaml)
  --interval  Refresh interval in seconds (overrides config)

Examples:
  python main.py                          # Terminal dashboard
  python main.py --mode both              # Terminal + Web
  python main.py --interval 5             # 5-second refresh
  python main.py --config /etc/ztm.yaml  # Custom config path
```

---

## 📬 Alert Channels Setup

### Gmail Email Alerts
1. Enable 2FA on your Google account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Generate a password for "Mail"
4. Use that password in `config.yaml`

### Slack Alerts
1. Go to [Slack API](https://api.slack.com/apps) → Create New App
2. Enable **Incoming Webhooks**
3. Add webhook to your channel
4. Paste the URL in `config.yaml`

### Desktop Notifications
Automatically works on Windows, macOS, and Linux with the `plyer` package (already in requirements).

---

## 🧰 Tech Stack

| Tool | Purpose |
|---|---|
| `psutil` | Cross-platform system metrics |
| `rich` | Beautiful terminal UI |
| `streamlit` | Web dashboard framework |
| `plotly` | Interactive charts |
| `pyyaml` | Config file parsing |
| `plyer` | Cross-platform desktop notifications |

---

## 🗺 Roadmap

- [ ] Prometheus metrics export endpoint
- [ ] Grafana dashboard integration
- [ ] Historical data with SQLite storage
- [ ] Process-level monitoring (top N processes by CPU/mem)
- [ ] HTTP/API endpoint health checks
- [ ] Multi-host monitoring support

---

## 🤝 Contributing

1. Fork the repo
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m "Add my feature"`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👨‍💻 Author

**Aakash Doli**
- GitHub: [@aakashdoli](https://github.com/aakashdoli)
- LinkedIn: [aakashdoli](https://linkedin.com/in/aakashdoli)

---

> ⭐ If you found this useful, give it a star on GitHub!