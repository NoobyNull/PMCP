# Augment MCP Server Setup Guide

## 🎯 Correct MCP Configuration for Augment

Augment expects MCP server configuration in a specific JSON format. Here's the correct configuration:

### ✅ Correct MCP Server Configuration

```json
{
  "servers": [
    {
      "type": "http",
      "url": "http://192.168.0.78:8000",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE",
        "Content-Type": "application/json"
      }
    }
  ]
}
```

### ❌ Incorrect Format (VSCode Settings)

```json
{
  "augment.server.url": "http://192.168.0.78:8080/api/tools",
  "augment.server.apiKey": "mpc_...",
  "augment.server.timeout": 30000,
  "augment.features.codeAnalysis": true
}
```

## 🔧 Setup Steps

### 1. Generate API Key
1. Go to http://192.168.0.78:8080/assistants/augment
2. Click "Generate New API Key"
3. Copy the generated API key (starts with `mpc_`)

### 2. Create MCP Configuration
Replace `YOUR_API_KEY_HERE` with your actual API key:

```json
{
  "servers": [
    {
      "type": "http",
      "url": "http://192.168.0.78:8000",
      "headers": {
        "Authorization": "Bearer mpc_goD4CC_dljMo7JJKjEje1QI0s7QP5ZUh_4lFboiQ0pg",
        "Content-Type": "application/json"
      }
    }
  ]
}
```

### 3. Import into Augment
1. Open Augment
2. Go to MCP Server settings
3. Click "Import MCP Server"
4. Paste the JSON configuration above
5. Click "Import"

## 🌐 Available Endpoints

The MCP server provides access to these PerfectMCP capabilities:

### Core Services
- **Memory Management**: `/api/memory/*`
- **Code Analysis**: `/api/code/*`
- **Document Search**: `/api/docs/*`

### Advanced Services (New!)
- **Context 7**: `/api/context7/*` - 7-layer context management
- **Playwright**: `/api/playwright/*` - Web automation
- **Sequential Thinking**: `/api/thinking/*` - Step-by-step reasoning

### Tools Discovery
- **Available Tools**: `/api/tools` - List all available tools
- **MCP Config**: `/api/mcp/config` - Get MCP configuration

## 🧪 Testing the Configuration

### Test MCP Endpoint
```bash
curl -s http://192.168.0.78:8080/api/mcp/config
```

Expected response:
```json
{
  "servers": [
    {
      "type": "http",
      "url": "http://192.168.0.78:8000",
      "headers": {
        "Content-Type": "application/json"
      }
    }
  ]
}
```

### Test with API Key
```bash
curl -s "http://192.168.0.78:8080/api/mcp/config?api_key=mpc_your_key_here"
```

### Test Main Server
```bash
curl -H "Authorization: Bearer mpc_your_key_here" \
     -H "Content-Type: application/json" \
     http://192.168.0.78:8000/api/tools
```

## 🔍 Troubleshooting

### "Failed to parse MCP servers from JSON"
- **Cause**: Using VSCode settings format instead of MCP format
- **Solution**: Use the `servers` array format shown above

### "Connection refused"
- **Cause**: Server not running or wrong port
- **Solution**: Check that PerfectMPC server is running on port 8000

### "Unauthorized"
- **Cause**: Missing or invalid API key
- **Solution**: Generate new API key and update configuration

### "Invalid JSON"
- **Cause**: Syntax error in JSON configuration
- **Solution**: Validate JSON format, check for missing commas/brackets

## 📋 Quick Reference

### Server Details
- **Main Server**: http://192.168.0.78:8000
- **Admin Interface**: http://192.168.0.78:8080
- **MCP Config Endpoint**: http://192.168.0.78:8080/api/mcp/config

### Authentication
- **Method**: Bearer token in Authorization header
- **Format**: `Authorization: Bearer mpc_your_api_key`
- **Generate**: Admin interface → Assistants → Augment

### Configuration Template
```json
{
  "servers": [
    {
      "type": "http",
      "url": "http://192.168.0.78:8000",
      "headers": {
        "Authorization": "Bearer [REPLACE_WITH_YOUR_API_KEY]",
        "Content-Type": "application/json"
      }
    }
  ]
}
```

## 🎉 Success Indicators

When properly configured, you should see:
- ✅ Augment connects to PerfectMPC server
- ✅ Tools are discovered and available
- ✅ No "Failed to parse" errors
- ✅ API calls work with authentication

## 🚀 Advanced Features

Once connected, you can use:

### Context 7 Service
```bash
# Add context to specific layer
POST /api/context7/add
{
  "session_id": "my-session",
  "content": "Important context",
  "layer": 1,
  "priority": 2
}
```

### Playwright Service
```bash
# Create browser session
POST /api/playwright/session
{
  "session_id": "my-session",
  "browser_type": "chromium",
  "headless": true
}
```

### Sequential Thinking
```bash
# Start thinking chain
POST /api/thinking/chain
{
  "session_id": "my-session",
  "problem": "How to optimize this code?",
  "reasoning_type": "systematic"
}
```

---

**🎯 Use the MCP server configuration format above for successful Augment integration!**
