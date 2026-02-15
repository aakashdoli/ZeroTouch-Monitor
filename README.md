# 🚀 Automated System Monitor & Dashboard

A "Zero-Touch" monitoring solution built with Python. It runs as a background daemon on macOS, tracking system performance (CPU usage) and sending automated email alerts when anomalies are detected. It includes a real-time web dashboard for visualization.

## 🏗 Architecture
* **Backend:** `master_control.py` - Manages the background service (`launchd`), logs data to CSV, and handles SMTP alerts.
* **Frontend:** `dashboard.py` - A Streamlit web app that visualizes the logs in real-time.
* **Database:** Local CSV storage (Simulating a Time-Series DB).

## ⚙️ Prerequisites
* macOS (Intel or Apple Silicon)
* Python 3.9+

## 📦 Installation
1. Clone the repository:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/Ericsson_System_Monitor.git](https://github.com/YOUR_USERNAME/Ericsson_System_Monitor.git)
   cd ZeroTouch-Monitor

   Create a virtual environment:
   python3 -m venv venv
source venv/bin/activate

Install dependencies:
pip install -r requirements.txt


Configure Credentials
Open master_control.py and update the email settings at the top:
EMAIL_SENDER = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"


2. Start the Background Monitor
This starts the daemon. It will persist even after you close the terminal.
python master_control.py

3. Open the Dashboard
View live metrics in your browser.
streamlit run dashboard.py


4. Stop the Monitor
To stop the background process and emails:
python master_control.py stop
