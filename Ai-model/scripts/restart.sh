#!/bin/bash

# Basic restart script for Flask App
# Kills existing process and starts it again

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

echo "--- Restarting Application ---"

cd "$APP_DIR" || exit 1

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Kill existing Flask/app processes
echo "Stopping Flask app..."
pkill -f "app.py" || true
pkill -f "gunicorn.*app" || true
pkill -f "flask_app.py" || true
sleep 2

# Start Flask app
echo "Starting Flask app..."
cd "$APP_DIR"
gunicorn -w 4 -b 0.0.0.0:5000 app:app > /dev/null 2>&1 &

echo "✅ Application restart completed"
