#!/bin/bash
# ZeroTouch-Monitor — one-line agent installer for Mac/Linux
# Usage: curl -sSL http://SERVER_IP:8000/install.sh | bash

set -e

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[zerotouch]${RESET} $1"; }
success() { echo -e "${GREEN}[zerotouch] ✓ $1${RESET}"; }
warn()    { echo -e "${YELLOW}[zerotouch] ! $1${RESET}"; }
error()   { echo -e "${RED}[zerotouch] ✗ $1${RESET}"; exit 1; }

SERVER_URL="__SERVER_URL__"
MACHINE_NAME="${HOSTNAME:-$(hostname)}"
API_KEY="zerotouch-default-key"
INSTALL_DIR="$HOME/.zerotouch"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --name)    MACHINE_NAME="$2"; shift 2 ;;
        --server)  SERVER_URL="$2"; shift 2 ;;
        --api-key) API_KEY="$2"; shift 2 ;;
        *) shift ;;
    esac
done

echo ""
echo "  ZeroTouch-Monitor Agent Installer"
echo "  ──────────────────────────────────"
echo "  machine : $MACHINE_NAME"
echo "  server  : $SERVER_URL"
echo ""

OS="$(uname -s)"
[[ "$OS" == "Darwin" ]] && OS_NAME="macOS" || OS_NAME="Linux"
success "OS: $OS_NAME"

# Python check
PYTHON=""
for cmd in python3 python3.11 python3.10 python3.9 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$($cmd -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        [[ "$VER" == "3" ]] && PYTHON="$cmd" && break
    fi
done
[[ -z "$PYTHON" ]] && error "Python 3 not found. Install from https://python.org"
success "Python: $($PYTHON --version)"

# pip check
$PYTHON -m pip --version &>/dev/null || curl -sSL https://bootstrap.pypa.io/get-pip.py | $PYTHON

# Install dir
mkdir -p "$INSTALL_DIR/monitor"

# Download files
download() {
    local url="$1" dest="$2"
    curl -sSL "$url" -o "$dest" || wget -q "$url" -O "$dest" || error "Failed: $url"
}

info "Downloading agent files..."
download "$SERVER_URL/download/agent.py"        "$INSTALL_DIR/agent.py"
download "$SERVER_URL/download/metrics.py"       "$INSTALL_DIR/monitor/metrics.py"
download "$SERVER_URL/download/smart_engine.py"  "$INSTALL_DIR/monitor/smart_engine.py"
touch "$INSTALL_DIR/monitor/__init__.py"
success "Files downloaded"

# Dependencies
info "Installing psutil..."
$PYTHON -m pip install psutil --quiet --break-system-packages 2>/dev/null || \
$PYTHON -m pip install psutil --quiet
success "Dependencies installed"

# Config
cat > "$INSTALL_DIR/config.json" << CONF
{"server_url":"$SERVER_URL","machine_name":"$MACHINE_NAME","api_key":"$API_KEY","interval":2}
CONF

# Launcher
cat > "$INSTALL_DIR/start.sh" << LAUNCH
#!/bin/bash
PYTHONPATH="$INSTALL_DIR" $PYTHON "$INSTALL_DIR/agent.py" \
    --server "$SERVER_URL" --name "$MACHINE_NAME" --api-key "$API_KEY"
LAUNCH
chmod +x "$INSTALL_DIR/start.sh"

# Auto-start
if [[ "$OS_NAME" == "macOS" ]]; then
    PLIST="$HOME/Library/LaunchAgents/com.zerotouch.agent.plist"
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key><string>com.zerotouch.agent</string>
    <key>ProgramArguments</key><array>
        <string>$PYTHON</string><string>$INSTALL_DIR/agent.py</string>
        <string>--server</string><string>$SERVER_URL</string>
        <string>--name</string><string>$MACHINE_NAME</string>
    </array>
    <key>EnvironmentVariables</key><dict><key>PYTHONPATH</key><string>$INSTALL_DIR</string></dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$INSTALL_DIR/agent.log</string>
    <key>StandardErrorPath</key><string>$INSTALL_DIR/error.log</string>
</dict></plist>
PLIST
    launchctl load "$PLIST" 2>/dev/null || true
    success "Auto-start configured (LaunchAgent)"
else
    SYSTEMD="$HOME/.config/systemd/user"
    mkdir -p "$SYSTEMD"
    cat > "$SYSTEMD/zerotouch-agent.service" << SVC
[Unit]
Description=ZeroTouch-Monitor Agent
After=network.target
[Service]
ExecStart=$PYTHON $INSTALL_DIR/agent.py --server $SERVER_URL --name $MACHINE_NAME
Environment=PYTHONPATH=$INSTALL_DIR
Restart=always
[Install]
WantedBy=default.target
SVC
    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user enable zerotouch-agent 2>/dev/null || true
    systemctl --user start zerotouch-agent 2>/dev/null || true
    success "Auto-start configured (systemd)"
fi

# Start agent
info "Starting agent..."
PYTHONPATH="$INSTALL_DIR" $PYTHON "$INSTALL_DIR/agent.py" \
    --server "$SERVER_URL" --name "$MACHINE_NAME" --api-key "$API_KEY" &

AGENT_PID=$!
sleep 2

if kill -0 $AGENT_PID 2>/dev/null; then
    echo ""
    echo -e "${GREEN}  ✓ Agent running! (PID: $AGENT_PID)${RESET}"
    echo "  Your machine is now visible in the dashboard."
    echo ""
else
    error "Agent failed to start. Check $INSTALL_DIR/error.log"
fi

echo "  To stop:     kill $AGENT_PID"
echo "  To uninstall: rm -rf $INSTALL_DIR"
[[ "$OS_NAME" == "macOS" ]] && echo "               launchctl unload ~/Library/LaunchAgents/com.zerotouch.agent.plist"
echo ""