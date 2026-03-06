import argparse
import json
import time
import logging
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Request, Header
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import PlainTextResponse
    import uvicorn
except ImportError:
    print("Run: pip install fastapi uvicorn")
    exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

API_KEY = "zerotouch-default-key"
BASE_DIR = Path(__file__).parent.parent

app = FastAPI(title="ZeroTouch-Monitor", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

machines: dict = {}
metrics_store: dict = defaultdict(lambda: deque(maxlen=300))
command_queue: dict = defaultdict(list)
alerts_log: deque = deque(maxlen=500)

CPU_ALERT  = 85.0
MEM_ALERT  = 85.0
DISK_ALERT = 90.0


def verify_key(key: str):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/", response_class=PlainTextResponse)
async def root(request: Request):
    host = request.headers.get("host", "localhost:8000")
    return f"""
ZeroTouch-Monitor Central Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Add a Mac/Linux machine:
  curl -sSL http://{host}/install.sh | bash

Add a Windows machine:
  Open http://{host}/install.py → save → run

Docs: http://{host}/docs
"""


@app.get("/install.sh", response_class=PlainTextResponse)
async def serve_install_sh(request: Request):
    path = BASE_DIR / "installer" / "install.sh"
    if not path.exists():
        raise HTTPException(status_code=404, detail="install.sh not found")
    host = request.headers.get("host", "localhost:8000")
    return PlainTextResponse(
        path.read_text().replace("__SERVER_URL__", f"http://{host}"),
        media_type="text/plain"
    )


@app.get("/install.py", response_class=PlainTextResponse)
async def serve_install_py(request: Request):
    path = BASE_DIR / "installer" / "install_windows.py"
    if not path.exists():
        raise HTTPException(status_code=404, detail="install_windows.py not found")
    host = request.headers.get("host", "localhost:8000")
    return PlainTextResponse(
        path.read_text().replace("__SERVER_URL__", f"http://{host}"),
        media_type="text/plain"
    )


@app.get("/download/{filename}", response_class=PlainTextResponse)
async def download_file(filename: str):
    allowed = {
        "agent.py":        BASE_DIR / "agent" / "agent.py",
        "metrics.py":      BASE_DIR / "monitor" / "metrics.py",
        "smart_engine.py": BASE_DIR / "monitor" / "smart_engine.py",
    }
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Not found")
    path = allowed[filename]
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} missing on server")
    return PlainTextResponse(path.read_text(), media_type="text/plain")


@app.get("/health")
async def health():
    return {"status": "ok", "machines": len(machines), "time": time.time()}


@app.post("/api/machines/register")
async def register(request: Request, x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key or "")
    data = await request.json()
    mid = data.get("machine_id")
    if not mid:
        raise HTTPException(status_code=400, detail="machine_id required")
    machines[mid] = {**data, "last_seen": time.time(), "status": "online"}
    logger.info(f"Registered: {data.get('machine_name')} ({mid})")
    return {"status": "registered", "machine_id": mid}


@app.post("/api/metrics")
async def receive_metrics(request: Request, x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key or "")
    data = await request.json()
    mid = data.get("machine_id")
    if not mid:
        raise HTTPException(status_code=400, detail="machine_id required")
    if mid in machines:
        machines[mid]["last_seen"] = time.time()
        machines[mid]["status"] = "online"
    data["received_at"] = time.time()
    metrics_store[mid].append(data)
    _check_alerts(mid, data)
    return {"status": "ok"}


@app.get("/api/machines")
async def get_machines():
    now = time.time()
    result = []
    for mid, info in machines.items():
        if now - info.get("last_seen", 0) > 10:
            info["status"] = "offline"
        history = list(metrics_store.get(mid, []))
        latest = history[-1] if history else {}
        result.append({**info, "latest_metrics": latest})
    return result


@app.get("/api/machines/{machine_id}/metrics")
async def get_metrics(machine_id: str, limit: int = 60):
    return list(metrics_store.get(machine_id, []))[-limit:]


@app.get("/api/alerts")
async def get_alerts(limit: int = 50):
    return list(alerts_log)[-limit:]


@app.get("/api/summary")
async def get_summary():
    now = time.time()
    total = len(machines)
    online = sum(1 for m in machines.values() if now - m.get("last_seen", 0) <= 10)
    active_alerts = []
    for mid, info in machines.items():
        history = list(metrics_store.get(mid, []))
        if history:
            latest = history[-1]
            cpu = latest.get("cpu", {}).get("percent", 0)
            mem = latest.get("memory", {}).get("percent", 0)
            if cpu > 80:
                active_alerts.append(f"{info['machine_name']}: CPU {cpu:.0f}%")
            if mem > 85:
                active_alerts.append(f"{info['machine_name']}: Memory {mem:.0f}%")
    return {"total_machines": total, "online": online, "offline": total - online,
            "active_alerts": active_alerts, "timestamp": now}


@app.post("/api/commands/send")
async def send_command(request: Request):
    data = await request.json()
    mid = data.get("machine_id")
    if not mid:
        raise HTTPException(status_code=400, detail="machine_id required")
    cmd = {
        "id": f"cmd_{int(time.time()*1000)}",
        "action": data.get("action"),
        "pid": data.get("pid"),
        "created_at": time.time(),
    }
    command_queue[mid].append(cmd)
    return {"status": "queued", "command_id": cmd["id"]}


@app.get("/api/commands/{machine_id}")
async def get_commands(machine_id: str, x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key or "")
    return command_queue.pop(machine_id, [])


@app.post("/api/commands/result")
async def command_result(request: Request, x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key or "")
    data = await request.json()
    logger.info(f"Command result: {data.get('message')}")
    return {"status": "ok"}


def _check_alerts(machine_id: str, data: dict):
    name = machines.get(machine_id, {}).get("machine_name", machine_id)
    ts = datetime.now().strftime("%H:%M:%S")
    cpu = data.get("cpu", {}).get("percent", 0)
    mem = data.get("memory", {}).get("percent", 0)
    if cpu >= CPU_ALERT:
        alerts_log.append({"time": ts, "machine": name, "machine_id": machine_id,
                           "level": "CRITICAL" if cpu >= 95 else "WARNING",
                           "metric": "CPU", "value": cpu,
                           "message": f"{name}: CPU at {cpu:.1f}%"})
    if mem >= MEM_ALERT:
        alerts_log.append({"time": ts, "machine": name, "machine_id": machine_id,
                           "level": "WARNING", "metric": "Memory", "value": mem,
                           "message": f"{name}: Memory at {mem:.1f}%"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroTouch-Monitor Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--api-key", default="zerotouch-default-key")
    args = parser.parse_args()
    API_KEY = args.api_key

    print(f"\nZeroTouch-Monitor Server running on port {args.port}")
    print(f"Add a machine: curl -sSL http://YOUR_IP:{args.port}/install.sh | bash\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")