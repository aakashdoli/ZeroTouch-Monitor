"""
ZeroTouch-Monitor - Alert System
Handles threshold checks and dispatches Email, Slack, and Desktop notifications.
"""

import smtplib
import json
import logging
import urllib.request
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

import subprocess
import platform

from monitor.metrics import SystemSnapshot

logger = logging.getLogger(__name__)


@dataclass
class AlertThresholds:
    cpu_percent: float = 85.0
    memory_percent: float = 85.0
    disk_percent: float = 90.0
    network_sent_mb: float = 100.0
    network_recv_mb: float = 100.0


@dataclass
class AlertEvent:
    level: str          # "WARNING" or "CRITICAL"
    metric: str
    value: float
    threshold: float
    message: str
    hostname: str
    timestamp: datetime


class EmailAlerter:
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str, recipients: list[str]):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipients = recipients

    def send(self, event: AlertEvent):
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[ZeroTouch-Monitor] {event.level}: {event.metric} Alert on {event.hostname}"
            msg["From"] = self.username
            msg["To"] = ", ".join(self.recipients)

            html = f"""
            <html><body style="font-family:sans-serif;padding:20px;">
            <h2 style="color:{'#e74c3c' if event.level=='CRITICAL' else '#f39c12'}">
                🚨 {event.level} Alert — {event.metric}
            </h2>
            <table style="border-collapse:collapse;width:100%">
                <tr><td style="padding:8px;background:#f8f9fa;font-weight:bold">Host</td>
                    <td style="padding:8px">{event.hostname}</td></tr>
                <tr><td style="padding:8px;background:#f8f9fa;font-weight:bold">Metric</td>
                    <td style="padding:8px">{event.metric}</td></tr>
                <tr><td style="padding:8px;background:#f8f9fa;font-weight:bold">Current Value</td>
                    <td style="padding:8px;color:#e74c3c;font-weight:bold">{event.value:.1f}</td></tr>
                <tr><td style="padding:8px;background:#f8f9fa;font-weight:bold">Threshold</td>
                    <td style="padding:8px">{event.threshold:.1f}</td></tr>
                <tr><td style="padding:8px;background:#f8f9fa;font-weight:bold">Time</td>
                    <td style="padding:8px">{event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>
            <p style="margin-top:20px;color:#666">Sent by ZeroTouch-Monitor</p>
            </body></html>
            """
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.username, self.recipients, msg.as_string())
            logger.info(f"Email alert sent for {event.metric}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")


class SlackAlerter:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, event: AlertEvent):
        try:
            color = "#e74c3c" if event.level == "CRITICAL" else "#f39c12"
            emoji = "🔴" if event.level == "CRITICAL" else "🟡"
            payload = {
                "attachments": [{
                    "color": color,
                    "title": f"{emoji} {event.level}: {event.metric} on {event.hostname}",
                    "fields": [
                        {"title": "Current Value", "value": f"{event.value:.1f}", "short": True},
                        {"title": "Threshold", "value": f"{event.threshold:.1f}", "short": True},
                        {"title": "Host", "value": event.hostname, "short": True},
                        {"title": "Time", "value": event.timestamp.strftime('%H:%M:%S'), "short": True},
                    ],
                    "footer": "ZeroTouch-Monitor",
                }]
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
            logger.info(f"Slack alert sent for {event.metric}")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")


class DesktopAlerter:
    def send(self, event: AlertEvent):
        try:
            title = f"ZeroTouch-Monitor: {event.level}"
            message = f"{event.metric} is at {event.value:.1f}% (threshold: {event.threshold:.1f}%)"
            os_name = platform.system()

            if os_name == "Darwin":  # macOS — use native osascript
                script = f'display notification "{message}" with title "{title}" sound name "Basso"'
                subprocess.run(["osascript", "-e", script], check=True)

            elif os_name == "Linux":
                subprocess.run(["notify-send", title, message], check=True)

            elif os_name == "Windows":
                subprocess.run([
                    "powershell", "-Command",
                    f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms");'
                    f'$n = New-Object System.Windows.Forms.NotifyIcon;'
                    f'$n.Icon = [System.Drawing.SystemIcons]::Information;'
                    f'$n.BalloonTipTitle = "{title}";'
                    f'$n.BalloonTipText = "{message}";'
                    f'$n.Visible = $True;'
                    f'$n.ShowBalloonTip(5000);'
                ], check=True)

            logger.info(f"Desktop notification sent: {event.metric}")
        except Exception as e:
            logger.error(f"Failed to send desktop notification: {e}")


class AlertManager:
    """Evaluates metrics against thresholds and fires alerts."""

    def __init__(
        self,
        thresholds: AlertThresholds,
        email_alerter: Optional[EmailAlerter] = None,
        slack_alerter: Optional[SlackAlerter] = None,
        desktop_alerter: Optional[DesktopAlerter] = None,
    ):
        self.thresholds = thresholds
        self.alerters = []
        if email_alerter:
            self.alerters.append(email_alerter)
        if slack_alerter:
            self.alerters.append(slack_alerter)
        if desktop_alerter:
            self.alerters.append(desktop_alerter)
        self._recent_alerts: dict[str, datetime] = {}
        self.cooldown_seconds = 300  # Don't re-alert same metric within 5 minutes

    def _should_alert(self, metric: str) -> bool:
        if metric not in self._recent_alerts:
            return True
        elapsed = (datetime.now() - self._recent_alerts[metric]).total_seconds()
        return elapsed >= self.cooldown_seconds

    def _fire(self, event: AlertEvent):
        if not self._should_alert(event.metric):
            return
        self._recent_alerts[event.metric] = datetime.now()
        logger.warning(f"ALERT: {event.level} - {event.message}")
        for alerter in self.alerters:
            alerter.send(event)

    def evaluate(self, snapshot: SystemSnapshot) -> list[AlertEvent]:
        events = []

        # CPU
        if snapshot.cpu.percent >= self.thresholds.cpu_percent:
            level = "CRITICAL" if snapshot.cpu.percent >= 95 else "WARNING"
            e = AlertEvent(level, "CPU Usage", snapshot.cpu.percent,
                           self.thresholds.cpu_percent,
                           f"CPU at {snapshot.cpu.percent:.1f}%",
                           snapshot.hostname, snapshot.timestamp)
            events.append(e)
            self._fire(e)

        # Memory
        if snapshot.memory.percent >= self.thresholds.memory_percent:
            level = "CRITICAL" if snapshot.memory.percent >= 95 else "WARNING"
            e = AlertEvent(level, "Memory Usage", snapshot.memory.percent,
                           self.thresholds.memory_percent,
                           f"Memory at {snapshot.memory.percent:.1f}%",
                           snapshot.hostname, snapshot.timestamp)
            events.append(e)
            self._fire(e)

        # Disk
        for part in snapshot.disk.partitions:
            if part["percent"] >= self.thresholds.disk_percent:
                level = "CRITICAL" if part["percent"] >= 95 else "WARNING"
                e = AlertEvent(level, f"Disk ({part['mountpoint']})", part["percent"],
                               self.thresholds.disk_percent,
                               f"Disk {part['mountpoint']} at {part['percent']:.1f}%",
                               snapshot.hostname, snapshot.timestamp)
                events.append(e)
                self._fire(e)

        return events