#!/bin/bash

# Restart script for Flask API and Streamlit App
# This script restarts both services on EC2

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_PATH="${DEPLOY_PATH:-/home/ubuntu/app}"

echo "--- Restarting Application Services ---"
echo "App directory: $APP_DIR"
echo "Deploy path: $DEPLOY_PATH"

cd "$APP_DIR" || exit 1

# Function to restart systemd service
restart_systemd_service() {
    local service_name=$1
    if systemctl list-unit-files | grep -q "$service_name.service"; then
        echo "Restarting systemd service: $service_name"
        sudo systemctl restart "$service_name.service" || true
        sudo systemctl status "$service_name.service" --no-pager -l || true
    else
        echo "⚠️  Service $service_name.service not found in systemd"
    fi
}

# Function to restart process using pkill and start new one
restart_process() {
    local process_name=$1
    local start_command=$2
    
    echo "Stopping existing $process_name processes..."
    pkill -f "$process_name" || true
    sleep 2
    
    echo "Starting $process_name..."
    eval "$start_command" &
    sleep 2
    
    if pgrep -f "$process_name" > /dev/null; then
        echo "✅ $process_name started successfully"
    else
        echo "❌ Failed to start $process_name"
        return 1
    fi
}

# Try systemd services first (preferred method)
if systemctl list-unit-files | grep -q "flask-api.service"; then
    restart_systemd_service "flask-api"
elif systemctl list-unit-files | grep -q "flask.service"; then
    restart_systemd_service "flask"
else
    echo "⚠️  No Flask systemd service found. Attempting process restart..."
    # Activate virtual environment if it exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # Restart Flask using gunicorn
    restart_process "flask_app.py" "cd $APP_DIR && gunicorn -w 4 -b 0.0.0.0:5000 flask_app:app"
fi

# Try systemd services first for Streamlit
if systemctl list-unit-files | grep -q "streamlit-app.service"; then
    restart_systemd_service "streamlit-app"
elif systemctl list-unit-files | grep -q "streamlit.service"; then
    restart_systemd_service "streamlit"
else
    echo "⚠️  No Streamlit systemd service found. Attempting process restart..."
    # Activate virtual environment if it exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # Restart Streamlit
    restart_process "streamlit_app.py" "cd $APP_DIR && streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0"
fi

# Health check
echo ""
echo "--- Health Check ---"
sleep 3

# Check Flask
if curl -s http://localhost:5000/ > /dev/null 2>&1; then
    echo "✅ Flask API is responding"
else
    echo "⚠️  Flask API health check failed"
fi

# Check Streamlit
if curl -s http://localhost:8501/_stcore/health > /dev/null 2>&1; then
    echo "✅ Streamlit app is responding"
else
    echo "⚠️  Streamlit app health check failed"
fi

echo ""
echo "✅ Application restart completed"

