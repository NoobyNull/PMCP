#!/bin/bash

# Configure PerfectMPC for LAN Access
# This script configures the server and databases to be accessible from the LAN

set -e

echo "Configuring PerfectMPC for LAN access..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Get server IP address
SERVER_IP=$(hostname -I | awk '{print $1}')
print_status "Detected server IP: $SERVER_IP"

# Configure Redis for LAN access
print_status "Configuring Redis for LAN access..."

# Backup original config if not already backed up
if [ ! -f "/etc/redis/redis.conf.backup" ]; then
    cp /etc/redis/redis.conf /etc/redis/redis.conf.backup
    print_status "Redis config backed up"
fi

# Configure Redis to bind to all interfaces
sed -i 's/bind 127.0.0.1 -::1/bind 0.0.0.0/' /etc/redis/redis.conf
sed -i 's/protected-mode yes/protected-mode no/' /etc/redis/redis.conf

# Add security settings
if ! grep -q "# PerfectMPC LAN Configuration" /etc/redis/redis.conf; then
    cat >> /etc/redis/redis.conf << EOF

# PerfectMPC LAN Configuration
maxclients 100
timeout 300
tcp-keepalive 300
EOF
fi

print_status "Redis configured for LAN access"

# Configure MongoDB for LAN access
print_status "Configuring MongoDB for LAN access..."

# Backup original config if not already backed up
if [ ! -f "/etc/mongod.conf.backup" ]; then
    cp /etc/mongod.conf /etc/mongod.conf.backup
    print_status "MongoDB config backed up"
fi

# Configure MongoDB to bind to all interfaces
sed -i 's/bindIp: 127.0.0.1/bindIp: 0.0.0.0/' /etc/mongod.conf

print_status "MongoDB configured for LAN access"

# Configure SSH for LAN access
print_status "Configuring SSH for LAN access..."

# Ensure SSH is configured to listen on all interfaces
if ! grep -q "ListenAddress 0.0.0.0" /etc/ssh/sshd_config; then
    echo "ListenAddress 0.0.0.0" >> /etc/ssh/sshd_config
fi

# Configure firewall rules (if ufw is installed)
if command -v ufw &> /dev/null; then
    print_status "Configuring firewall rules..."
    
    # Allow SSH
    ufw allow 22/tcp
    
    # Allow PerfectMPC HTTP API
    ufw allow 8000/tcp
    
    # Allow PerfectMPC SSH
    ufw allow 2222/tcp
    
    # Allow Redis (be careful - only for trusted networks)
    print_warning "Opening Redis port 6379 - ensure this is a trusted network!"
    ufw allow 6379/tcp
    
    # Allow MongoDB (be careful - only for trusted networks)
    print_warning "Opening MongoDB port 27017 - ensure this is a trusted network!"
    ufw allow 27017/tcp
    
    print_status "Firewall rules configured"
else
    print_warning "UFW not installed. Please configure firewall manually if needed."
fi

# Restart services
print_status "Restarting services..."
systemctl restart redis-server
systemctl restart mongod
systemctl restart ssh

# Wait for services to start
sleep 5

# Test services
print_status "Testing service accessibility..."

# Test Redis
if redis-cli -h $SERVER_IP ping | grep -q "PONG"; then
    print_status "✓ Redis accessible from LAN"
else
    print_error "✗ Redis not accessible from LAN"
fi

# Test MongoDB
if mongosh --host $SERVER_IP --eval "db.adminCommand('ping')" --quiet | grep -q "ok"; then
    print_status "✓ MongoDB accessible from LAN"
else
    print_error "✗ MongoDB not accessible from LAN"
fi

# Create connection info file
print_status "Creating connection information..."

cat > /opt/PerfectMPC/LAN_CONNECTION_INFO.md << EOF
# PerfectMPC LAN Connection Information

## Server Details
- **Server IP**: $SERVER_IP
- **Hostname**: $(hostname)
- **Configuration Date**: $(date)

## Service Endpoints

### HTTP API
- **URL**: http://$SERVER_IP:8000
- **Health Check**: http://$SERVER_IP:8000/health
- **API Documentation**: http://$SERVER_IP:8000/docs

### WebSocket
- **URL**: ws://$SERVER_IP:8000/ws

### SSH Access
- **Standard SSH**: ssh user@$SERVER_IP
- **MPC SSH**: ssh -p 2222 user@$SERVER_IP

### SFTP Access
- **MPC SFTP**: sftp -P 2222 user@$SERVER_IP

### Database Access (Direct - Use with caution)
- **Redis**: redis-cli -h $SERVER_IP -p 6379
- **MongoDB**: mongosh --host $SERVER_IP --port 27017

## Client Configuration Examples

### Augment VSCode Plugin Configuration
\`\`\`json
{
  "perfectmpc.server.host": "$SERVER_IP",
  "perfectmpc.server.port": 8000,
  "perfectmpc.server.protocol": "http",
  "perfectmpc.ssh.host": "$SERVER_IP",
  "perfectmpc.ssh.port": 2222
}
\`\`\`

### cURL Examples
\`\`\`bash
# Health check
curl http://$SERVER_IP:8000/health

# Create session
curl -X POST http://$SERVER_IP:8000/api/memory/session \\
  -H "Content-Type: application/json" \\
  -d '{"session_id": "test-session"}'

# Analyze code
curl -X POST http://$SERVER_IP:8000/api/code/analyze \\
  -H "Content-Type: application/json" \\
  -d '{
    "session_id": "test-session",
    "code": "def hello(): print(\"world\")",
    "language": "python"
  }'
\`\`\`

### Python Client Example
\`\`\`python
import requests

# Connect to PerfectMPC server
base_url = "http://$SERVER_IP:8000/api"

# Create session
response = requests.post(f"{base_url}/memory/session", 
                        json={"session_id": "my-session"})
print(response.json())

# Analyze code
response = requests.post(f"{base_url}/code/analyze",
                        json={
                            "session_id": "my-session",
                            "code": "def hello(): print('world')",
                            "language": "python"
                        })
print(response.json())
\`\`\`

## Security Notes
- **No Authentication**: Server is configured without authentication as requested
- **Network Security**: Ensure this server is on a trusted network
- **Firewall**: Database ports are open - restrict access if needed
- **Monitoring**: Monitor access logs for security

## Troubleshooting
- **Connection Issues**: Check firewall settings and network connectivity
- **Service Status**: Run \`systemctl status perfectmpc redis-server mongod\`
- **Logs**: Check \`/opt/PerfectMPC/logs/server.log\`
- **Network Test**: Use \`telnet $SERVER_IP 8000\` to test connectivity
EOF

print_status "Connection information saved to /opt/PerfectMPC/LAN_CONNECTION_INFO.md"

# Display summary
print_status "LAN configuration completed!"
echo ""
echo "🌐 Server is now accessible from the LAN:"
echo "   HTTP API: http://$SERVER_IP:8000"
echo "   SSH:      ssh -p 2222 user@$SERVER_IP"
echo "   SFTP:     sftp -P 2222 user@$SERVER_IP"
echo ""
echo "📋 Next steps:"
echo "   1. Start PerfectMPC server: python3 /opt/PerfectMPC/start_server.py"
echo "   2. Test from client: curl http://$SERVER_IP:8000/health"
echo "   3. Configure Augment VSCode plugin with server IP: $SERVER_IP"
echo ""
echo "📄 Connection details saved to: /opt/PerfectMPC/LAN_CONNECTION_INFO.md"
echo ""
print_warning "Security reminder: Server has no authentication - use on trusted networks only!"
