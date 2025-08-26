#!/bin/bash

# PerfectMPC Dependencies Installation Script

set -e

echo "Installing PerfectMPC dependencies..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root"
   exit 1
fi

# Update system packages
print_status "Updating system packages..."
apt update

# Install system dependencies
print_status "Installing system dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    redis-server \
    openssh-server \
    curl \
    wget \
    git \
    htop \
    nano \
    vim

# Install MongoDB if not already installed
if ! command -v mongod &> /dev/null; then
    print_status "Installing MongoDB..."
    
    # Add MongoDB GPG key
    wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | apt-key add -
    
    # Add MongoDB repository
    echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    
    # Update and install
    apt update
    apt install -y mongodb-org
else
    print_status "MongoDB already installed"
fi

# Start and enable services
print_status "Starting and enabling services..."
systemctl start redis-server
systemctl enable redis-server
systemctl start mongod
systemctl enable mongod

# Create Python virtual environment
print_status "Creating Python virtual environment..."
cd /opt/PerfectMPC

if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment and install Python packages
print_status "Installing Python packages..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install packages from requirements.txt
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_status "Python packages installed successfully"
else
    print_error "requirements.txt not found"
    exit 1
fi

# Create necessary directories
print_status "Creating directories..."
mkdir -p /opt/PerfectMCP/data/{chromadb,sftp,uploads}
mkdir -p /opt/PerfectMCP/logs
mkdir -p /opt/PerfectMCP/backups/{mongodb,redis,chromadb}

# Set permissions
print_status "Setting permissions..."
chown -R mcp:mcp /opt/PerfectMCP 2>/dev/null || true
chmod +x /opt/PerfectMCP/scripts/*.sh

# Create systemd service file
print_status "Creating systemd service..."
cat > /etc/systemd/system/perfectmcp.service << EOF
[Unit]
Description=PerfectMCP Server
After=network.target redis-server.service mongod.service
Requires=redis-server.service mongod.service

[Service]
Type=simple
User=mpc
Group=mpc
WorkingDirectory=/opt/PerfectMPC
Environment=PATH=/opt/PerfectMPC/venv/bin
ExecStart=/opt/PerfectMPC/venv/bin/python src/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

print_status "Installation completed successfully!"
print_status "You can now start the service with: systemctl start perfectmpc"
print_status "To enable auto-start: systemctl enable perfectmpc"

# Check service status
print_status "Checking service status..."
systemctl status redis-server --no-pager
systemctl status mongod --no-pager

print_status "Installation script finished!"
