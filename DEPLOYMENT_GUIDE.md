# PerfectMCP Deployment Guide

## Overview

PerfectMCP is a standalone Model Context Protocol server designed to assist with code development. It integrates with the Augment VSCode plugin to provide:

- **Memory Management**: Persistent code context and session memory
- **Code Improvement**: AI-powered code analysis and suggestions
- **RAG/Documentation**: Retrieval-Augmented Generation for documentation
- **Multi-Protocol Support**: HTTP/REST API, WebSocket, SSH/SFTP

## System Requirements

- **OS**: Ubuntu 24.04 LTS (or compatible)
- **RAM**: Minimum 4GB, Recommended 8GB+
- **Storage**: Minimum 10GB free space
- **Network**: Internet access for package installation

## Installation

### 1. Quick Setup (Automated)

```bash
# Run the installation script
sudo ./scripts/install_dependencies.sh

# Setup databases
sudo ./scripts/setup_databases.sh
```

### 2. Manual Setup

#### System Dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    build-essential redis-server openssh-server curl wget git

# Install MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org
```

#### Python Environment
```bash
cd /opt/PerfectMPC
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Start Services
```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
sudo systemctl start mongod
sudo systemctl enable mongod
```

## Configuration

### Server Configuration (`config/server.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: true

api:
  prefix: "/api"
  version: "v1"

ssh:
  enabled: true
  port: 2222
  auth:
    enabled: false  # No authentication as requested
```

### Database Configuration (`config/database.yaml`)

```yaml
redis:
  host: "localhost"
  port: 6379
  db: 0

mongodb:
  host: "localhost"
  port: 27017
  database: "perfectmpc"
```

## Running the Server

### Development Mode
```bash
# Test the setup
python3 test_setup.py

# Start the server
python3 start_server.py
```

### Production Mode
```bash
# Create systemd service
sudo systemctl start perfectmpc
sudo systemctl enable perfectmpc

# Check status
sudo systemctl status perfectmpc
```

## API Endpoints

### Memory Service
- `POST /api/memory/session` - Create session
- `GET /api/memory/session/{id}` - Get session
- `POST /api/memory/context` - Update context
- `GET /api/memory/context/{id}` - Get context
- `GET /api/memory/history/{id}` - Get history

### Code Improvement Service
- `POST /api/code/analyze` - Analyze code
- `POST /api/code/suggest` - Get suggestions
- `GET /api/code/metrics/{id}` - Get metrics

### RAG/Documentation Service
- `POST /api/docs/search` - Search documents
- `POST /api/docs/upload` - Upload document
- `POST /api/docs/generate` - Generate docs

## SSH Interface

Connect via SSH for command-line access:

```bash
ssh -p 2222 user@server-ip
```

### SSH Commands
```bash
# Server information
mpc
mpc status
mpc version

# Session management
session create [id]
session get
session context "your code context"

# Code analysis
analyze python "def hello(): print('world')"

# Document search
search "python functions"

# Help
help
```

## SFTP Access

Upload files via SFTP:

```bash
sftp -P 2222 user@server-ip
```

Files are stored in `/opt/PerfectMPC/data/sftp/`

## Integration with Augment VSCode Plugin

### HTTP API Integration
The plugin can connect via HTTP to:
- `http://server-ip:8000/api/`

### WebSocket Integration
Real-time communication via:
- `ws://server-ip:8000/ws`

### SSH Integration
Command execution via SSH:
- `ssh://server-ip:2222`

## Monitoring and Maintenance

### Log Files
- Server logs: `/opt/PerfectMPC/logs/server.log`
- System logs: `journalctl -u perfectmpc`

### Database Backup
```bash
# Manual backup
./scripts/backup_databases.sh

# Automated daily backup (already configured)
crontab -l  # Check cron job
```

### Health Checks
```bash
# Check server health
curl http://localhost:8000/health

# Check services
systemctl status perfectmpc
systemctl status redis-server
systemctl status mongod
```

## Troubleshooting

### Common Issues

1. **Port conflicts**
   ```bash
   # Check port usage
   sudo netstat -tlnp | grep :8000
   sudo netstat -tlnp | grep :2222
   ```

2. **Database connection issues**
   ```bash
   # Test Redis
   redis-cli ping
   
   # Test MongoDB
   mongosh --eval "db.adminCommand('ping')"
   ```

3. **Permission issues**
   ```bash
   # Fix permissions
   sudo chown -R mpc:mpc /opt/PerfectMPC
   ```

4. **Service startup issues**
   ```bash
   # Check logs
   journalctl -u perfectmpc -f
   ```

### Performance Tuning

1. **Redis Configuration**
   - Adjust `maxmemory` in `/etc/redis/redis.conf`
   - Configure persistence settings

2. **MongoDB Configuration**
   - Tune connection pool sizes
   - Configure indexes for better performance

3. **Server Resources**
   - Monitor CPU and memory usage
   - Scale vertically or horizontally as needed

## Security Considerations

- **No Authentication**: As requested, authentication is disabled
- **Network Security**: Use firewall rules to restrict access
- **Data Encryption**: Consider TLS/SSL for production
- **Regular Updates**: Keep system and dependencies updated

## Development

### Adding New Features
1. Create service in `src/services/`
2. Add API routes in `src/api/routes.py`
3. Update configuration in `config/`
4. Add tests in `tests/`

### Testing
```bash
# Run setup tests
python3 test_setup.py

# Run unit tests (when available)
pytest tests/
```

## Support

For issues and questions:
1. Check logs in `/opt/PerfectMPC/logs/`
2. Verify service status with `systemctl status`
3. Test database connections
4. Review configuration files

## Version Information

- **Version**: 1.0.0
- **Build**: Development
- **Python**: 3.12+
- **FastAPI**: 0.104+
- **Redis**: 7.0+
- **MongoDB**: 7.0+
