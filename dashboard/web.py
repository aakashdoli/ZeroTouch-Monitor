"""
ZeroTouch-Monitor - Streamlit Web Dashboard
Real-time web dashboard with process manager and kill functionality.
Run with: streamlit run dashboard/web.py
"""

import time
import subprocess
import threading
import streamlit as st
import plotly.graph_objects as go
from collections import deque
from datetime import datetime
from monitor.metrics import MetricsCollector, kill_process


def send_mac_notification(title: str, message: str):
    """Fire Mac notification in a background thread so it never blocks the dashboard."""
    def _notify():
        try:
            script = f'display notification "{message}" with title "{title}" sound name "Basso"'
            subprocess.run(["osascript", "-e", script], timeout=5)
        except Exception:
            pass
    threading.Thread(target=_notify, daemon=True).start()


# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ZeroTouch-Monitor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .alert-box {
        background: #2d1b1b;
        border-left: 4px solid #e74c3c;
        padding: 10px 14px;
        border-radius: 4px;
        margin: 6px 0;
    }
    .kill-success {
        background: #1b2d1b;
        border-left: 4px solid #2ecc71;
        padding: 10px 14px;
        border-radius: 4px;
        margin: 6px 0;
    }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    .stApp { background-color: #0e0e1a; }
</style>
""", unsafe_allow_html=True)

# ─── Session State ────────────────────────────────────────────────────────────
HISTORY_LEN = 60
if "collector" not in st.session_state:
    st.session_state.collector = MetricsCollector()
if "cpu_history" not in st.session_state:
    st.session_state.cpu_history = deque(maxlen=HISTORY_LEN)
    st.session_state.mem_history = deque(maxlen=HISTORY_LEN)
    st.session_state.net_sent_history = deque(maxlen=HISTORY_LEN)
    st.session_state.net_recv_history = deque(maxlen=HISTORY_LEN)
    st.session_state.time_history = deque(maxlen=HISTORY_LEN)
    st.session_state.alerted = {}        # { metric_key: last_alert_timestamp }
    st.session_state.kill_message = None

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.shields.io/badge/ZeroTouch-Monitor-cyan?style=for-the-badge")
    st.markdown("---")
    refresh_interval = st.slider("Refresh Interval (seconds)", 1, 10, 2)
    st.markdown("### Alert Thresholds")
    cpu_threshold = st.slider("CPU Alert %", 50, 99, 85)
    mem_threshold = st.slider("Memory Alert %", 50, 99, 85)
    disk_threshold = st.slider("Disk Alert %", 50, 99, 90)
    st.markdown("---")
    st.markdown("### 🔫 Kill a Process")
    st.caption("Enter PID from the process table below")
    kill_pid = st.number_input("Process PID", min_value=1, step=1, value=None, placeholder="e.g. 1234")
    if st.button("⚠️ Kill Process", type="primary", use_container_width=True):
        if kill_pid:
            success, msg = kill_process(int(kill_pid))
            st.session_state.kill_message = (success, msg)
            send_mac_notification(
                "🔫 ZeroTouch-Monitor: Process Killed" if success else "❌ Kill Failed",
                msg
            )
        else:
            st.session_state.kill_message = (False, "❌ Please enter a PID first.")
    st.markdown("---")
    st.markdown("**ZeroTouch-Monitor v1.0**")
    st.markdown("Automated system monitoring with zero touch.")

# ─── Collect Metrics ─────────────────────────────────────────────────────────
snapshot = st.session_state.collector.snapshot()
now_str = datetime.now().strftime("%H:%M:%S")
now_ts = datetime.now().timestamp()

st.session_state.cpu_history.append(snapshot.cpu.percent)
st.session_state.mem_history.append(snapshot.memory.percent)
st.session_state.net_sent_history.append(snapshot.network.bytes_sent_mb)
st.session_state.net_recv_history.append(snapshot.network.bytes_recv_mb)
st.session_state.time_history.append(now_str)
times = list(st.session_state.time_history)

# ─── Alert Logic with Cooldown ───────────────────────────────────────────────
COOLDOWN = 60   # 1 minute between repeated alerts for same metric

def should_alert(key):
    last = st.session_state.alerted.get(key, 0)
    if now_ts - last >= COOLDOWN:
        st.session_state.alerted[key] = now_ts
        return True
    return False

alerts = []

if snapshot.cpu.percent >= cpu_threshold:
    alerts.append(f"🔴 CPU at **{snapshot.cpu.percent:.1f}%** (threshold: {cpu_threshold}%)")
    if should_alert("cpu"):
        send_mac_notification(
            "⚠️ ZeroTouch-Monitor: CPU Alert",
            f"CPU is at {snapshot.cpu.percent:.1f}% — threshold is {cpu_threshold}%"
        )

if snapshot.memory.percent >= mem_threshold:
    alerts.append(f"🔴 Memory at **{snapshot.memory.percent:.1f}%** (threshold: {mem_threshold}%)")
    if should_alert("memory"):
        send_mac_notification(
            "⚠️ ZeroTouch-Monitor: Memory Alert",
            f"Memory is at {snapshot.memory.percent:.1f}% — threshold is {mem_threshold}%"
        )

for part in snapshot.disk.partitions:
    if part["percent"] >= disk_threshold:
        alerts.append(f"🔴 Disk `{part['mountpoint']}` at **{part['percent']:.1f}%** (threshold: {disk_threshold}%)")
        if should_alert(f"disk_{part['mountpoint']}"):
            send_mac_notification(
                "⚠️ ZeroTouch-Monitor: Disk Alert",
                f"Disk {part['mountpoint']} at {part['percent']:.1f}%"
            )

# ─── Header ──────────────────────────────────────────────────────────────────
col_title, col_host, col_time = st.columns([3, 2, 2])
with col_title:
    st.markdown("## ⚡ ZeroTouch-Monitor")
with col_host:
    st.markdown(f"**🖥 Host:** `{snapshot.hostname}`")
with col_time:
    st.markdown(f"**🕒 Updated:** `{now_str}`")

st.markdown("---")

# ─── Kill / Alert Banners ─────────────────────────────────────────────────────
if st.session_state.kill_message:
    success, msg = st.session_state.kill_message
    css_class = "kill-success" if success else "alert-box"
    st.markdown(f'<div class="{css_class}">{msg}</div>', unsafe_allow_html=True)

if alerts:
    st.error("⚠️ **Active Alerts**")
    for a in alerts:
        st.markdown(f'<div class="alert-box">{a}</div>', unsafe_allow_html=True)

# ─── Metric Cards ────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

def _delta_color(val, threshold):
    return "normal" if val < threshold * 0.7 else ("off" if val < threshold else "inverse")

c1.metric("🖥 CPU", f"{snapshot.cpu.percent:.1f}%", f"{snapshot.cpu.frequency_mhz:.0f} MHz",
          delta_color=_delta_color(snapshot.cpu.percent, cpu_threshold))
c2.metric("🧠 Memory", f"{snapshot.memory.percent:.1f}%",
          f"{snapshot.memory.used_gb:.1f}/{snapshot.memory.total_gb:.1f} GB",
          delta_color=_delta_color(snapshot.memory.percent, mem_threshold))
c3.metric("💾 Disk",
          f"{snapshot.disk.partitions[0]['percent']:.1f}%" if snapshot.disk.partitions else "N/A",
          f"{snapshot.disk.partitions[0]['used_gb']:.1f}/{snapshot.disk.partitions[0]['total_gb']:.1f} GB" if snapshot.disk.partitions else "")
c4.metric("📤 Net Sent", f"{snapshot.network.bytes_sent_mb:.3f} MB/s")
c5.metric("📥 Net Recv", f"{snapshot.network.bytes_recv_mb:.3f} MB/s")

st.markdown("---")

# ─── Charts ──────────────────────────────────────────────────────────────────
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("### 📈 CPU & Memory Over Time")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=list(st.session_state.cpu_history),
                             name="CPU %", line=dict(color="#00d4ff", width=2),
                             fill="tozeroy", fillcolor="rgba(0,212,255,0.1)"))
    fig.add_trace(go.Scatter(x=times, y=list(st.session_state.mem_history),
                             name="Memory %", line=dict(color="#bf5fff", width=2),
                             fill="tozeroy", fillcolor="rgba(191,95,255,0.1)"))
    fig.add_hline(y=cpu_threshold, line_dash="dash", line_color="red", annotation_text="CPU Threshold")
    fig.add_hline(y=mem_threshold, line_dash="dash", line_color="orange", annotation_text="Mem Threshold")
    fig.update_layout(
        paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e",
        font=dict(color="white"), yaxis=dict(range=[0, 100]),
        legend=dict(bgcolor="rgba(0,0,0,0)"), height=280,
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    st.markdown("### 🌐 Network I/O Over Time")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=times, y=list(st.session_state.net_sent_history),
                              name="Sent MB", line=dict(color="#00ff99", width=2)))
    fig2.add_trace(go.Scatter(x=times, y=list(st.session_state.net_recv_history),
                              name="Recv MB", line=dict(color="#ffaa00", width=2)))
    fig2.update_layout(
        paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e",
        font=dict(color="white"), legend=dict(bgcolor="rgba(0,0,0,0)"),
        height=280, margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ─── Top Processes ────────────────────────────────────────────────────────────
st.markdown("### 🔥 Top Processes — Who is eating your CPU?")
st.caption("Copy the PID → paste in sidebar → click Kill Process to free up resources")

procs = snapshot.top_processes
if procs:
    def cpu_badge(val):
        if val >= 50: return f"🔴 {val}%"
        if val >= 20: return f"🟡 {val}%"
        if val > 0:   return f"🟢 {val}%"
        return f"⚪ {val}%"

    def mem_badge(val):
        if val >= 10: return f"🔴 {val}%"
        if val >= 5:  return f"🟡 {val}%"
        return f"🟢 {val}%"

    table_data = {
        "PID":          [p.pid for p in procs],
        "Process Name": [p.name for p in procs],
        "CPU %":        [cpu_badge(p.cpu_percent) for p in procs],
        "Memory %":     [mem_badge(p.memory_percent) for p in procs],
        "Memory (MB)":  [p.memory_mb for p in procs],
        "Status":       [p.status for p in procs],
        "User":         [p.username for p in procs],
    }
    st.dataframe(table_data, use_container_width=True, height=380)
else:
    st.info("No process data available.")

st.markdown("---")

# ─── Disk + CPU Per Core ──────────────────────────────────────────────────────
col_disk, col_cores = st.columns([3, 2])

with col_disk:
    st.markdown("### 💾 Disk Partitions")
    disk_data = {
        "Mount":      [p["mountpoint"] for p in snapshot.disk.partitions],
        "FS Type":    [p["fstype"] for p in snapshot.disk.partitions],
        "Total (GB)": [p["total_gb"] for p in snapshot.disk.partitions],
        "Used (GB)":  [p["used_gb"] for p in snapshot.disk.partitions],
        "Free (GB)":  [p["free_gb"] for p in snapshot.disk.partitions],
        "Usage %":    [p["percent"] for p in snapshot.disk.partitions],
    }
    st.dataframe(disk_data, use_container_width=True)

with col_cores:
    st.markdown("### 🖥 CPU Per Core")
    core_cols = st.columns(4)
    for i, usage in enumerate(snapshot.cpu.per_core):
        color = "🟢" if usage < 70 else ("🟡" if usage < 90 else "🔴")
        core_cols[i % 4].metric(f"{color} Core {i}", f"{usage:.1f}%")

# ─── Auto Refresh ────────────────────────────────────────────────────────────
time.sleep(refresh_interval)
st.rerun()