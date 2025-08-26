#!/usr/bin/env python3
"""
Status check script for PerfectMPC
"""

import asyncio
import subprocess
import sys
from pathlib import Path

def run_command(cmd):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_service_status(service_name):
    """Check systemd service status"""
    success, stdout, stderr = run_command(f"systemctl is-active {service_name}")
    return success and "active" in stdout

def check_port(port):
    """Check if a port is listening"""
    success, stdout, stderr = run_command(f"netstat -tlnp | grep :{port}")
    return success and str(port) in stdout

def get_server_ip():
    """Get server IP address"""
    success, stdout, stderr = run_command("hostname -I | awk '{print $1}'")
    return stdout.strip() if success else "unknown"

async def main():
    """Main status check function"""
    print("PerfectMPC System Status Check")
    print("=" * 50)
    
    # Check system services
    print("\n🔧 System Services:")
    services = ["redis-server", "mongod", "ssh"]
    for service in services:
        status = "✓ Running" if check_service_status(service) else "✗ Not running"
        print(f"  {service}: {status}")
    
    # Check ports
    print("\n🌐 Network Ports:")
    ports = [
        (6379, "Redis"),
        (27017, "MongoDB"),
        (22, "SSH"),
        (8000, "HTTP API (if running)"),
        (2222, "MPC SSH (if running)")
    ]
    
    for port, description in ports:
        status = "✓ Listening" if check_port(port) else "✗ Not listening"
        print(f"  {port} ({description}): {status}")
    
    # Check directories
    print("\n📁 Directories:")
    directories = [
        "/opt/PerfectMPC",
        "/opt/PerfectMPC/src",
        "/opt/PerfectMPC/config",
        "/opt/PerfectMPC/logs",
        "/opt/PerfectMPC/data",
        "/opt/PerfectMPC/venv"
    ]
    
    for directory in directories:
        path = Path(directory)
        status = "✓ Exists" if path.exists() else "✗ Missing"
        print(f"  {directory}: {status}")
    
    # Check configuration files
    print("\n⚙️  Configuration Files:")
    config_files = [
        "/opt/PerfectMPC/config/server.yaml",
        "/opt/PerfectMPC/config/database.yaml",
        "/opt/PerfectMPC/requirements.txt"
    ]
    
    for config_file in config_files:
        path = Path(config_file)
        status = "✓ Exists" if path.exists() else "✗ Missing"
        print(f"  {config_file}: {status}")
    
    # Check Python environment
    print("\n🐍 Python Environment:")
    
    # Check virtual environment
    venv_path = Path("/opt/PerfectMPC/venv")
    venv_status = "✓ Exists" if venv_path.exists() else "✗ Missing"
    print(f"  Virtual environment: {venv_status}")
    
    # Check Python packages
    if venv_path.exists():
        python_path = venv_path / "bin" / "python"
        if python_path.exists():
            success, stdout, stderr = run_command(f"{python_path} -c 'import fastapi, redis, pymongo; print(\"OK\")'")
            pkg_status = "✓ Installed" if success else "✗ Missing packages"
            print(f"  Required packages: {pkg_status}")
        else:
            print("  Python interpreter: ✗ Missing")
    
    # Test database connections
    print("\n💾 Database Connections:")
    
    # Test Redis
    success, stdout, stderr = run_command("redis-cli ping")
    redis_status = "✓ Connected" if success and "PONG" in stdout else "✗ Connection failed"
    print(f"  Redis: {redis_status}")
    
    # Test MongoDB
    success, stdout, stderr = run_command("mongosh --eval 'db.adminCommand(\"ping\")' --quiet")
    mongo_status = "✓ Connected" if success else "✗ Connection failed"
    print(f"  MongoDB: {mongo_status}")
    
    # Check if PerfectMPC can be imported
    print("\n🚀 PerfectMPC Application:")
    
    try:
        sys.path.insert(0, "/opt/PerfectMPC/src")
        from utils.config import get_config
        config = get_config()
        print("  ✓ Configuration loading works")
        
        from utils.database import DatabaseManager
        print("  ✓ Database manager import works")
        
        print("  ✓ Core application components available")
        
    except Exception as e:
        print(f"  ✗ Application import failed: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    # Get server IP for LAN access
    server_ip = get_server_ip()

    print("📋 Quick Start Commands:")
    print("  Test setup:     python3 test_setup.py")
    print("  Start server:   python3 start_server.py")
    print("  Check logs:     tail -f logs/server.log")
    print(f"  SSH connect:    ssh -p 2222 user@{server_ip}")
    print(f"  API health:     curl http://{server_ip}:8000/health")

    print(f"\n🌐 LAN Access Information:")
    print(f"  Server IP:      {server_ip}")
    print(f"  HTTP API:       http://{server_ip}:8000")
    print(f"  WebSocket:      ws://{server_ip}:8000/ws")
    print(f"  SSH:            ssh -p 2222 user@{server_ip}")
    print(f"  SFTP:           sftp -P 2222 user@{server_ip}")
    print(f"  Connection Info: cat LAN_CONNECTION_INFO.md")
    
    print("\n📚 Documentation:")
    print("  Deployment:     cat DEPLOYMENT_GUIDE.md")
    print("  README:         cat README.md")
    
    print("\n🔧 Troubleshooting:")
    print("  Service logs:   journalctl -u perfectmpc -f")
    print("  Redis logs:     journalctl -u redis-server -f")
    print("  MongoDB logs:   journalctl -u mongod -f")

if __name__ == "__main__":
    asyncio.run(main())
