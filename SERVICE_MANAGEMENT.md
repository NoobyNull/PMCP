# PerfectMCP Service Management

The PerfectMCP admin server is now configured as a systemd service for easy management.

## Quick Commands

### Basic Service Control
```bash
# Start the service
systemctl start pmpc

# Stop the service
systemctl stop pmpc

# Restart the service (what you requested!)
systemctl restart pmpc

# Check service status
systemctl status pmpc
```

### Service Management Script
Use the convenient wrapper script for enhanced functionality:

```bash
# Check service status and health
./pmpc-service.sh status

# Restart with health check
./pmpc-service.sh restart

# View recent logs
./pmpc-service.sh logs

# Follow live logs
./pmpc-service.sh follow

# Check connectivity and health
./pmpc-service.sh health
```

## Service Features

### Auto-Start on Boot
The service is configured to automatically start when the system boots.

```bash
# Enable auto-start (already enabled)
systemctl enable pmpc

# Disable auto-start
systemctl disable pmpc
```

### Logging
Service logs are managed by systemd and can be viewed with:

```bash
# View recent logs
journalctl -u pmpc

# Follow live logs
journalctl -u pmpc -f

# View logs from last boot
journalctl -u pmpc -b
```

### Auto-Restart
The service is configured to automatically restart if it crashes:
- **Restart Policy**: Always restart on failure
- **Restart Delay**: 10 seconds between restart attempts

### Security Features
The service includes security hardening:
- **NoNewPrivileges**: Prevents privilege escalation
- **ProtectSystem**: Read-only access to system directories
- **ProtectHome**: No access to user home directories
- **PrivateTmp**: Isolated temporary directory

### Resource Limits
- **File Descriptors**: 65,536 (for handling many connections)
- **Processes**: 4,096 (reasonable limit for the application)

## Service Configuration

The service file is located at: `/etc/systemd/system/pmpc.service`

Key configuration:
- **Working Directory**: `/opt/PerfectMPC`
- **Python Environment**: `/opt/PerfectMPC/venv`
- **User**: root (required for system access)
- **Logging**: All output goes to systemd journal

## Troubleshooting

### Service Won't Start
```bash
# Check detailed status
systemctl status pmpc -l

# Check logs for errors
journalctl -u pmpc --no-pager -l

# Verify file permissions
ls -la /opt/PerfectMPC/admin_server.py
ls -la /opt/PerfectMPC/venv/bin/python
```

### Port Already in Use
```bash
# Check what's using port 8080
netstat -tulpn | grep :8080

# Kill conflicting processes
pkill -f "admin_server.py"
systemctl restart pmpc
```

### Database Connection Issues
```bash
# Check if Redis and MongoDB are running
systemctl status redis
systemctl status mongod

# View detailed logs
./pmpc-service.sh logs
```

## Installation/Removal

### Install Service
```bash
sudo ./setup_service.sh
```

### Remove Service
```bash
./pmpc-service.sh uninstall
```

## Access Points

- **Admin Interface**: http://192.168.0.78:8080
- **API Endpoint**: http://192.168.0.78:8080/api
- **WebSocket**: ws://192.168.0.78:8080/ws

## Service Dependencies

The service will start after:
- Network is available
- System has reached multi-user target

Required services (should be running):
- Redis (for caching and sessions)
- MongoDB (for document storage)
- Network connectivity
