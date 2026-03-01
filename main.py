"""
ZeroTouch-Monitor - Main Entry Point
Usage:
    python main.py              # Terminal dashboard (default)
    python main.py --mode web   # Print instructions to run web dashboard
    python main.py --mode both  # Start terminal dashboard (run web separately)
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config.config_loader import load_config
from monitor.logger import setup_logger
from monitor.metrics import MetricsCollector
from alerts.alerter import (
    AlertThresholds, AlertManager,
    EmailAlerter, SlackAlerter, DesktopAlerter
)


def build_alert_manager(cfg) -> AlertManager:
    thresholds = AlertThresholds(
        cpu_percent=cfg.alerts.cpu_threshold,
        memory_percent=cfg.alerts.memory_threshold,
        disk_percent=cfg.alerts.disk_threshold,
    )

    email_alerter = None
    if cfg.alerts.email.enabled and cfg.alerts.email.username:
        email_alerter = EmailAlerter(
            smtp_host=cfg.alerts.email.smtp_host,
            smtp_port=cfg.alerts.email.smtp_port,
            username=cfg.alerts.email.username,
            password=cfg.alerts.email.password,
            recipients=cfg.alerts.email.recipients,
        )

    slack_alerter = None
    if cfg.alerts.slack.enabled and cfg.alerts.slack.webhook_url:
        slack_alerter = SlackAlerter(cfg.alerts.slack.webhook_url)

    desktop_alerter = DesktopAlerter() if cfg.alerts.desktop_enabled else None

    manager = AlertManager(
        thresholds=thresholds,
        email_alerter=email_alerter,
        slack_alerter=slack_alerter,
        desktop_alerter=desktop_alerter,
    )
    manager.cooldown_seconds = cfg.alerts.cooldown_seconds
    return manager


def main():
    parser = argparse.ArgumentParser(
        description="⚡ ZeroTouch-Monitor — Automated Python System Monitor"
    )
    parser.add_argument(
        "--mode", choices=["terminal", "web", "both"], default="terminal",
        help="Dashboard mode: terminal (default), web (Streamlit), or both"
    )
    parser.add_argument("--config", default="config/config.yaml", help="Path to config file")
    parser.add_argument("--interval", type=int, default=None, help="Refresh interval in seconds")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.interval:
        cfg.interval_seconds = args.interval

    logger = setup_logger(cfg.log_dir)
    logger.info("ZeroTouch-Monitor starting...")

    alert_manager = build_alert_manager(cfg)

    if args.mode == "web":
        print("\n🌐 To run the web dashboard, execute:")
        print("   streamlit run dashboard/web.py\n")
        return

    if args.mode == "both":
        import subprocess, threading
        def run_web():
            subprocess.run(["streamlit", "run", "dashboard/web.py", "--server.headless", "true"])
        t = threading.Thread(target=run_web, daemon=True)
        t.start()
        print("🌐 Web dashboard starting at http://localhost:8501")
        print("⚡ Terminal dashboard launching...\n")

    # Run terminal dashboard
    from dashboard.terminal import run_terminal_dashboard
    run_terminal_dashboard(interval=cfg.interval_seconds, alert_manager=alert_manager)


if __name__ == "__main__":
    main()