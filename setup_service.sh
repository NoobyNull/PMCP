#!/bin/bash

# PerfectMPC Service Setup Script
# This script sets up the PerfectMPC admin server as a systemd service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="pmpc"
SERVICE_FILE="${SERVICE_NAME}.service"
SYSTEMD_DIR="/etc/systemd/system"

echo "🚀 Setting up PerfectMPC as a systemd service..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Stop any existing admin_server processes
echo "🛑 Stopping any existing admin_server processes..."
pkill -f "python.*admin_server.py" || true
sleep 2

# Copy service file to systemd directory
echo "📋 Installing service file..."
cp "${SCRIPT_DIR}/${SERVICE_FILE}" "${SYSTEMD_DIR}/"
chmod 644 "${SYSTEMD_DIR}/${SERVICE_FILE}"

# Reload systemd daemon
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable the service
echo "✅ Enabling ${SERVICE_NAME} service..."
systemctl enable ${SERVICE_NAME}

# Start the service
echo "🚀 Starting ${SERVICE_NAME} service..."
systemctl start ${SERVICE_NAME}

# Check status
echo "📊 Service status:"
systemctl status ${SERVICE_NAME} --no-pager -l

echo ""
echo "✅ PerfectMPC service setup complete!"
echo ""
echo "📋 Available commands:"
echo "  systemctl start ${SERVICE_NAME}     - Start the service"
echo "  systemctl stop ${SERVICE_NAME}      - Stop the service"
echo "  systemctl restart ${SERVICE_NAME}   - Restart the service"
echo "  systemctl status ${SERVICE_NAME}    - Check service status"
echo "  systemctl logs ${SERVICE_NAME}      - View service logs"
echo "  journalctl -u ${SERVICE_NAME} -f    - Follow live logs"
echo ""
echo "🌐 Admin interface will be available at: http://192.168.0.78:8080"
