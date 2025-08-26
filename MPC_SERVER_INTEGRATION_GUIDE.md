# PerfectMPC Server Integration Guide

## Adding Your MPC Server to Your Server List

### Current Setup Options

Your PerfectMPC server now supports **two authentication modes**:

#### 1. **No Authentication Mode** (Current Default)
- ✅ **Direct access** without API keys
- ✅ **Single-user setup** as originally requested
- ✅ **Simple integration** for personal use

#### 2. **Multi-User Mode with API Keys** (New Feature)
- ✅ **API key authentication** for secure access
- ✅ **Multi-user support** with role-based permissions
- ✅ **Enterprise-ready** with user management

---

## Integration Methods

### Method 1: Direct Integration (No Auth)

**Server Details:**
```
Server Name: PerfectMCP Development Server
Host: 192.168.0.78
Port: 8000
Protocol: HTTP
Authentication: None
```

**API Endpoints:**
```
Health Check: GET http://192.168.0.78:8000/health
Sessions: POST http://192.168.0.78:8000/api/memory/session
Code Analysis: POST http://192.168.0.78:8000/api/code/analyze
Document Search: POST http://192.168.0.78:8000/api/docs/search
```

**Example Usage:**
```bash
# Test connection
curl http://192.168.0.78:8000/health

# Create session
curl -X POST http://192.168.0.78:8000/api/memory/session \
  -H "Content-Type: application/json" \
  -d '{"session_id": "my-session"}'

# Analyze code
curl -X POST http://192.168.0.78:8000/api/code/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-session",
    "code": "def hello(): print(\"world\")",
    "language": "python"
  }'
```

### Method 2: API Key Integration (Multi-User)

**Step 1: Enable Authentication**

1. **Access Admin Interface**: http://192.168.0.78:8080
2. **Go to Users & API Keys**: Click "Users & API Keys" in navigation
3. **Create Your User Account**:
   - Click "Add User"
   - Enter your details
   - Select role (Admin/User/Read-Only)
   - Check "Create default API key"
4. **Save Your API Key**: Copy the generated API key immediately!

**Step 2: Server Configuration**
```
Server Name: PerfectMPC Development Server (Authenticated)
Host: 192.168.0.78
Port: 8000
Protocol: HTTP
Authentication: Bearer Token (API Key)
API Key: mpc_[your-generated-key]
```

**Step 3: Authenticated Usage**
```bash
# Set your API key
API_KEY="mpc_your_generated_key_here"

# Test authenticated connection
curl -H "Authorization: Bearer $API_KEY" \
  http://192.168.0.78:8000/health

# Create session with authentication
curl -X POST http://192.168.0.78:8000/api/memory/session \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "my-session"}'
```

---

## User Roles & Permissions

### Admin Role
- ✅ **Full access** to all endpoints
- ✅ **User management** capabilities
- ✅ **Server administration** access
- ✅ **All permissions** (*)

### User Role
- ✅ **Session management** (sessions:*)
- ✅ **Document management** (documents:*)
- ✅ **Code analysis** (code:analyze)
- ❌ **No admin access**

### Read-Only Role
- ✅ **View sessions** (sessions:read)
- ✅ **View documents** (documents:read)
- ❌ **No write access**
- ❌ **No admin access**

---

## API Key Management

### Creating API Keys

**Via Admin Interface:**
1. Go to http://192.168.0.78:8080/users
2. Click "Create API Key"
3. Select user and permissions
4. Set expiration (optional)
5. Copy the generated key

**Via API:**
```bash
curl -X POST http://192.168.0.78:8080/api/auth/api-keys \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_id_here",
    "name": "My API Key",
    "permissions": ["sessions:*", "documents:*", "code:analyze"],
    "expires_days": 90
  }'
```

### API Key Security

**Best Practices:**
- ✅ **Store securely** - Never commit to code
- ✅ **Use environment variables** for API keys
- ✅ **Set expiration dates** for temporary access
- ✅ **Revoke unused keys** regularly
- ✅ **Monitor usage** via admin interface

**Environment Setup:**
```bash
# Add to your .bashrc or .env file
export PERFECTMPC_API_KEY="mpc_your_key_here"
export PERFECTMPC_SERVER="http://192.168.0.78:8000"
```

---

## Integration Examples

### Python Client
```python
import requests
import os

class PerfectMPCClient:
    def __init__(self, base_url=None, api_key=None):
        self.base_url = base_url or os.getenv('PERFECTMPC_SERVER', 'http://192.168.0.78:8000')
        self.api_key = api_key or os.getenv('PERFECTMPC_API_KEY')
        self.headers = {}
        
        if self.api_key:
            self.headers['Authorization'] = f'Bearer {self.api_key}'
    
    def create_session(self, session_id):
        response = requests.post(
            f'{self.base_url}/api/memory/session',
            headers=self.headers,
            json={'session_id': session_id}
        )
        return response.json()
    
    def analyze_code(self, session_id, code, language):
        response = requests.post(
            f'{self.base_url}/api/code/analyze',
            headers=self.headers,
            json={
                'session_id': session_id,
                'code': code,
                'language': language
            }
        )
        return response.json()

# Usage
client = PerfectMCPClient()
session = client.create_session('my-session')
result = client.analyze_code('my-session', 'def hello(): pass', 'python')
```

### JavaScript/Node.js Client
```javascript
class PerfectMCPClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl || process.env.PERFECTMCP_SERVER || 'http://192.168.0.78:8000';
        this.apiKey = apiKey || process.env.PERFECTMCP_API_KEY;
        this.headers = {
            'Content-Type': 'application/json'
        };
        
        if (this.apiKey) {
            this.headers['Authorization'] = `Bearer ${this.apiKey}`;
        }
    }
    
    async createSession(sessionId) {
        const response = await fetch(`${this.baseUrl}/api/memory/session`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ session_id: sessionId })
        });
        return response.json();
    }
    
    async analyzeCode(sessionId, code, language) {
        const response = await fetch(`${this.baseUrl}/api/code/analyze`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                session_id: sessionId,
                code: code,
                language: language
            })
        });
        return response.json();
    }
}

// Usage
const client = new PerfectMCPClient();
const session = await client.createSession('my-session');
const result = await client.analyzeCode('my-session', 'def hello(): pass', 'python');
```

---

## Switching Between Modes

### Enable Authentication Mode

1. **Restart with Auth**: Modify server startup to include authentication
2. **Create Admin User**: First user becomes admin automatically
3. **Generate API Keys**: Create keys for all users
4. **Update Clients**: Add API key headers to all requests

### Disable Authentication Mode

1. **Remove Auth Middleware**: Comment out authentication checks
2. **Restart Server**: Server accepts all requests without keys
3. **Update Clients**: Remove API key headers

---

## Monitoring & Administration

### Admin Interface Features

**User Management:**
- ✅ **Create/Edit Users** with role assignment
- ✅ **View User Activity** and login history
- ✅ **Manage User Status** (active/inactive)

**API Key Management:**
- ✅ **Create API Keys** with custom permissions
- ✅ **Set Expiration Dates** for security
- ✅ **Revoke Keys** instantly
- ✅ **Monitor Usage** and last access times

**Security Monitoring:**
- ✅ **Track API Usage** per key
- ✅ **Monitor Failed Attempts** 
- ✅ **View Access Logs** in real-time
- ✅ **Export Security Reports**

### Access URLs

- **Main Server**: http://192.168.0.78:8000
- **Admin Interface**: http://192.168.0.78:8080
- **User Management**: http://192.168.0.78:8080/users
- **API Documentation**: http://192.168.0.78:8000/docs (if enabled)

---

## Next Steps

1. **Choose Your Mode**: Decide between no-auth or multi-user
2. **Create API Keys**: If using auth mode, generate your keys
3. **Update Your Client**: Add authentication headers if needed
4. **Test Integration**: Verify all endpoints work correctly
5. **Monitor Usage**: Use admin interface to track activity

**Your PerfectMCP server is now ready for integration with full user management and API key authentication! 🚀**
