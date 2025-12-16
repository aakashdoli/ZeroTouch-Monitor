import streamlit as st
import pandas as pd
import time
import os

# --- CONFIGURATION ---
USER_HOME = os.path.expanduser("~")
CSV_PATH = os.path.join(USER_HOME, "Desktop", "system_log_final.csv")

# --- PAGE SETUP ---
st.set_page_config(page_title="System Monitor", page_icon="📈", layout="wide")

st.title("🚀 Live System Performance Monitor")
st.markdown("Watching your Mac's heartbeat in real-time...")

# --- DATA LOADER FUNCTION ---
def load_data():
    if not os.path.exists(CSV_PATH):
        return None
    
    try:
        # Read the CSV
        # We give names ['Time', 'CPU', 'Info'] because the file has no proper header sometimes
        df = pd.read_csv(CSV_PATH, names=['Time', 'CPU', 'Info'])
        
        # Clean up the timestamp
        df['Time'] = pd.to_datetime(df['Time'])
        return df
    except Exception as e:
        return None

# --- MAIN DASHBOARD LAYOUT ---
# Create placeholders for live updates
kpi1, kpi2, kpi3 = st.columns(3)
chart_placeholder = st.empty()
table_placeholder = st.empty()

# --- LIVE UPDATE LOOP ---
# This loop refreshes the dashboard every 2 seconds
while True:
    df = load_data()

    if df is not None and not df.empty:
        # Get the latest data point
        latest = df.iloc[-1]
        
        # 1. Update Top KPIs (Big Numbers)
        with kpi1:
            st.metric("Current CPU Usage", f"{latest['CPU']}%")
        with kpi2:
            st.metric("Top Process", latest['Info'].split('(')[0])
        with kpi3:
            # Calculate average of last 10 readings
            avg_cpu = df.tail(10)['CPU'].mean()
            st.metric("Avg CPU (Last 1 min)", f"{avg_cpu:.1f}%")

        # 2. Update the Chart
        # We only show the last 50 data points to keep the chart clean
        chart_data = df.tail(50).set_index("Time")["CPU"]
        chart_placeholder.line_chart(chart_data)

        # 3. Update the Data Table (Optional: Hidden in an expander)
        with table_placeholder.expander("View Raw Data Logs"):
            st.dataframe(df.tail(10).sort_values(by="Time", ascending=False), use_container_width=True)

    else:
        chart_placeholder.warning("Waiting for data... (Make sure master_control.py is running!)")

    # Wait 2 seconds before refreshing
    time.sleep(2)
    st.rerun()