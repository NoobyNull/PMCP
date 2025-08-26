#!/bin/bash

# PerfectMCP Service Management Script
# Convenient wrapper for managing the PerfectMCP systemd service

SERVICE_NAME="pmpc"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if service exists
check_service_exists() {
    if ! systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
        print_error "Service ${SERVICE_NAME} is not installed!"
        echo "Run: sudo ./setup_service.sh to install the service"
        exit 1
    fi
}

# Function to show usage
show_usage() {
    echo "PerfectMCP Service Management"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  start      - Start the PerfectMCP service"
    echo "  stop       - Stop the PerfectMCP service"
    echo "  restart    - Restart the PerfectMCP service"
    echo "  status     - Show service status"
    echo "  logs       - Show recent logs"
    echo "  follow     - Follow live logs"
    echo "  enable     - Enable service to start on boot"
    echo "  disable    - Disable service from starting on boot"
    echo "  install    - Install/setup the service (requires sudo)"
    echo "  uninstall  - Remove the service (requires sudo)"
    echo "  health     - Check service health and connectivity"
    echo ""
    echo "Examples:"
    echo "  $0 restart"
    echo "  $0 logs"
    echo "  $0 status"
}

# Function to check service health
check_health() {
    print_status "Checking PerfectMCP service health..."
    
    # Check if service is running
    if systemctl is-active --quiet ${SERVICE_NAME}; then
        print_success "Service is running"
    else
        print_error "Service is not running"
        return 1
    fi
    
    # Check if port 8080 is listening
    if netstat -tuln | grep -q ":8080 "; then
        print_success "Port 8080 is listening"
    else
        print_warning "Port 8080 is not listening"
    fi
    
    # Try to connect to the admin interface
    if curl -s --connect-timeout 5 http://localhost:8080/ > /dev/null; then
        print_success "Admin interface is responding"
        echo "🌐 Admin interface: http://192.168.0.78:8080"
    else
        print_warning "Admin interface is not responding"
    fi
}

# Main script logic
case "${1:-}" in
    start)
        check_service_exists
        print_status "Starting ${SERVICE_NAME} service..."
        sudo systemctl start ${SERVICE_NAME}
        print_success "Service started"
        sleep 2
        check_health
        ;;
    stop)
        check_service_exists
        print_status "Stopping ${SERVICE_NAME} service..."
        sudo systemctl stop ${SERVICE_NAME}
        print_success "Service stopped"
        ;;
    restart)
        check_service_exists
        print_status "Restarting ${SERVICE_NAME} service..."
        sudo systemctl restart ${SERVICE_NAME}
        print_success "Service restarted"
        sleep 3
        check_health
        ;;
    status)
        check_service_exists
        print_status "Service status:"
        systemctl status ${SERVICE_NAME} --no-pager -l
        echo ""
        check_health
        ;;
    logs)
        check_service_exists
        print_status "Recent logs for ${SERVICE_NAME}:"
        journalctl -u ${SERVICE_NAME} --no-pager -l -n 50
        ;;
    follow)
        check_service_exists
        print_status "Following live logs for ${SERVICE_NAME} (Ctrl+C to exit):"
        journalctl -u ${SERVICE_NAME} -f
        ;;
    enable)
        check_service_exists
        print_status "Enabling ${SERVICE_NAME} service to start on boot..."
        sudo systemctl enable ${SERVICE_NAME}
        print_success "Service enabled"
        ;;
    disable)
        check_service_exists
        print_status "Disabling ${SERVICE_NAME} service from starting on boot..."
        sudo systemctl disable ${SERVICE_NAME}
        print_success "Service disabled"
        ;;
    install)
        print_status "Installing PerfectMPC service..."
        sudo "${SCRIPT_DIR}/setup_service.sh"
        ;;
    uninstall)
        if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
            print_status "Uninstalling ${SERVICE_NAME} service..."
            sudo systemctl stop ${SERVICE_NAME} || true
            sudo systemctl disable ${SERVICE_NAME} || true
            sudo rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
            sudo systemctl daemon-reload
            print_success "Service uninstalled"
        else
            print_warning "Service ${SERVICE_NAME} is not installed"
        fi
        ;;
    health)
        check_service_exists
        check_health
        ;;
    "")
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac
