# PerfectMPC LAN Connection Information

## Server Details
- **Server IP**: 192.168.0.78
- **Hostname**: mpc
- **Configuration Date**: Sun Aug 24 03:44:20 PM UTC 2025

## Service Endpoints

### HTTP API
- **URL**: http://192.168.0.78:8000
- **Health Check**: http://192.168.0.78:8000/health
- **API Documentation**: http://192.168.0.78:8000/docs

### WebSocket
- **URL**: ws://192.168.0.78:8000/ws

### SSH Access
- **Standard SSH**: ssh user@192.168.0.78
- **MPC SSH**: ssh -p 2222 user@192.168.0.78

### SFTP Access
- **MPC SFTP**: sftp -P 2222 user@192.168.0.78

### Database Access (Direct - Use with caution)
- **Redis**: redis-cli -h 192.168.0.78 -p 6379
- **MongoDB**: mongosh --host 192.168.0.78 --port 27017

## Client Configuration Examples

### Augment VSCode Plugin Configuration
```json
{
  "perfectmpc.server.host": "192.168.0.78",
  "perfectmpc.server.port": 8000,
  "perfectmpc.server.protocol": "http",
  "perfectmpc.ssh.host": "192.168.0.78",
  "perfectmpc.ssh.port": 2222
}
```

### cURL Examples
```bash
# Health check
curl http://192.168.0.78:8000/health

# Create session
curl -X POST http://192.168.0.78:8000/api/memory/session \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session"}'

# Analyze code
curl -X POST http://192.168.0.78:8000/api/code/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "code": "def hello(): print(\"world\")",
    "language": "python"
  }'
```

### Python Client Example
```python
import requests

# Connect to PerfectMPC server
base_url = "http://192.168.0.78:8000/api"

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
```

## Security Notes
- **No Authentication**: Server is configured without authentication as requested
- **Network Security**: Ensure this server is on a trusted network
- **Firewall**: Database ports are open - restrict access if needed
- **Monitoring**: Monitor access logs for security

## Troubleshooting
- **Connection Issues**: Check firewall settings and network connectivity
- **Service Status**: Run `systemctl status perfectmpc redis-server mongod`
- **Logs**: Check `/opt/PerfectMPC/logs/server.log`
- **Network Test**: Use `telnet 192.168.0.78 8000` to test connectivity
