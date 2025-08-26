# PerfectMPC Admin Interface Guide

## Overview

The PerfectMPC Admin Interface is a comprehensive web-based dashboard for managing all aspects of the MPC server. It runs on port 8080 (separate from the main API server on port 8000) and provides full administrative control over the system.

## Quick Start

### Starting the Admin Interface

```bash
# Start the admin interface
python3 start_admin.py

# Or run directly
python3 admin_server.py
```

### Accessing the Interface

- **URL**: `http://192.168.0.78:8080`
- **No Authentication Required**: As specified in requirements
- **Responsive Design**: Works on desktop and mobile devices

## Features Overview

### 🖥️ Server Management Dashboard
- **Start/Stop/Restart** the main MPC server (port 8000)
- **Real-time Status Monitoring** with health metrics
- **System Resource Monitoring** (CPU, Memory, Disk usage)
- **Uptime Tracking** for both admin and main server
- **Live Connection Monitoring** via WebSocket

### 👥 Session Management
- **List All Sessions** (active and historical)
- **Create New Sessions** with custom IDs
- **View Session Details** including context and metadata
- **Delete Sessions** with confirmation
- **Session Analytics** and statistics
- **Context Management** with size tracking

### 📄 RAG Document Management
- **Upload Documents** (PDF, TXT, MD, DOCX, HTML, code files)
- **Browse Document Library** with search and filtering
- **Document Metadata Viewer** showing chunks and indexing info
- **Test RAG Search** functionality with live results
- **Re-index Documents** when needed
- **Bulk Document Operations** (delete multiple)

### 💾 Database Administration

#### Redis Browser
- **Browse Redis Keys** with pattern matching
- **View Key Details** including values and TTL
- **Delete Keys** with confirmation
- **Key Type Detection** (string, hash, list, set, etc.)
- **TTL Management** and expiration tracking

#### MongoDB Browser
- **Browse Collections** with document counts and sizes
- **View Documents** with JSON formatting
- **Collection Statistics** and performance metrics
- **Query Interface** for advanced operations
- **Index Management** and optimization

### 📊 Code Analysis Management
- **View Analysis History** for all sessions
- **Code Quality Metrics** and trends
- **Improvement Suggestions** tracking
- **Language-specific Analytics** 
- **Quality Score Trends** over time

### ⚙️ System Configuration
- **Edit Configuration Files** (server.yaml, database.yaml)
- **Live Configuration Validation**
- **Backup Management** for config changes
- **Service Settings** modification
- **API Rate Limits** and CORS configuration

### 📋 Real-time Log Viewing
- **Live Log Streaming** with auto-refresh
- **Log Level Filtering** (DEBUG, INFO, WARNING, ERROR)
- **Search and Highlight** functionality
- **Download Logs** for offline analysis
- **Log Statistics** and error tracking

### 🔄 Real-time Updates
- **WebSocket Integration** for live updates
- **Server Status Changes** broadcast instantly
- **Session Activity** notifications
- **Document Upload** progress tracking
- **System Metrics** updated every 5 seconds

## Interface Layout

### Navigation Sidebar
- **Dashboard** - Main overview and quick actions
- **Server Management** - Start/stop/restart controls
- **Sessions** - Session management and analytics
- **Documents** - RAG document management
- **Database** - Redis and MongoDB administration
- **Code Analysis** - Code quality and metrics
- **Configuration** - System settings management
- **Logs** - Real-time log viewer

### Main Content Area
- **Responsive Cards** for metrics and statistics
- **Interactive Tables** with sorting and filtering
- **Modal Dialogs** for detailed views and editing
- **Progress Indicators** for long-running operations
- **Alert System** for notifications and feedback

## API Endpoints

### Server Management
- `GET /api/status` - Get server and system status
- `POST /api/server/start` - Start MPC server
- `POST /api/server/stop` - Stop MPC server
- `POST /api/server/restart` - Restart MPC server

### Session Management
- `GET /api/sessions` - List all sessions
- `POST /api/sessions` - Create new session
- `DELETE /api/sessions/{id}` - Delete session

### Document Management
- `GET /api/documents` - List all documents
- `POST /api/documents/upload` - Upload document
- `DELETE /api/documents/{id}` - Delete document

### Database Administration
- `GET /api/database/redis/keys` - Get Redis keys
- `GET /api/database/mongodb/collections` - Get MongoDB collections

### Configuration Management
- `GET /api/config/{type}` - Get configuration file
- `POST /api/config/{type}` - Save configuration file

### Logs and Monitoring
- `GET /api/logs` - Get server logs
- `GET /api/activity/recent` - Get recent activity

## WebSocket Events

### Real-time Updates
- `status_update` - Server and system status changes
- `server_status` - MPC server status changes
- `session_created` - New session notifications
- `session_deleted` - Session deletion notifications
- `document_uploaded` - Document upload notifications
- `config_updated` - Configuration change notifications

## Security Considerations

### No Authentication
- **As Requested**: No authentication required for single-user setup
- **Network Security**: Ensure admin interface is on trusted network
- **Firewall Protection**: Consider restricting access to port 8080

### Data Protection
- **Configuration Backups**: Automatic backup before changes
- **Database Backups**: Integrated backup/restore functionality
- **Audit Trail**: Activity logging for administrative actions

## Troubleshooting

### Common Issues

1. **Admin Interface Won't Start**
   ```bash
   # Check dependencies
   python3 test_admin_interface.py
   
   # Check port availability
   netstat -tlnp | grep :8080
   ```

2. **Can't Connect to MPC Server**
   ```bash
   # Check MPC server status
   curl http://192.168.0.78:8000/health
   
   # Start MPC server from admin interface
   # Or manually: python3 start_server.py
   ```

3. **Database Connection Issues**
   ```bash
   # Check database services
   systemctl status redis-server mongod
   
   # Test connections
   redis-cli ping
   mongosh --eval "db.adminCommand('ping')"
   ```

4. **WebSocket Connection Problems**
   - Check browser console for errors
   - Verify firewall allows WebSocket connections
   - Try refreshing the page

### Performance Optimization

1. **Large Log Files**
   - Use log filtering to reduce load
   - Consider log rotation
   - Limit number of lines displayed

2. **Many Documents**
   - Use pagination for document lists
   - Implement search indexing
   - Regular cleanup of old documents

3. **High Session Count**
   - Archive old sessions
   - Implement session cleanup policies
   - Monitor memory usage

## Development and Customization

### Adding New Features
1. **Backend**: Add routes to `admin_server.py`
2. **Frontend**: Create/modify templates in `admin/templates/`
3. **Styling**: Use Bootstrap classes and custom CSS
4. **JavaScript**: Add functionality to template scripts

### Template Structure
- `base.html` - Main layout and navigation
- `dashboard.html` - Main dashboard
- `sessions.html` - Session management
- `database.html` - Database administration
- `documents.html` - Document management
- `logs.html` - Log viewer

### WebSocket Integration
```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://192.168.0.78:8080/ws');

// Handle messages
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    handleWebSocketMessage(data);
};
```

## Integration with Augment VSCode Plugin

### Configuration
The admin interface provides configuration management for the Augment VSCode plugin:

```json
{
  "perfectmpc.server.host": "192.168.0.78",
  "perfectmpc.server.port": 8000,
  "perfectmpc.admin.host": "192.168.0.78", 
  "perfectmpc.admin.port": 8080
}
```

### Monitoring Integration
- **Session Tracking**: Monitor VSCode plugin sessions
- **Document Sync**: Track documents uploaded from VSCode
- **Code Analysis**: View analysis results from plugin
- **Real-time Status**: Live connection status with plugin

## Backup and Maintenance

### Automated Backups
- **Database Backups**: Scheduled via admin interface
- **Configuration Backups**: Automatic before changes
- **Log Rotation**: Configurable log management

### Maintenance Tasks
- **Session Cleanup**: Remove old inactive sessions
- **Document Cleanup**: Archive or remove old documents
- **Log Management**: Rotate and compress log files
- **Database Optimization**: Index maintenance and cleanup

## Support and Documentation

### Getting Help
1. **Check Logs**: Use the log viewer for error details
2. **System Status**: Monitor dashboard for issues
3. **Test Interface**: Run `python3 test_admin_interface.py`
4. **Database Health**: Check database administration panel

### Additional Resources
- **Main Documentation**: `README.md`
- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **LAN Configuration**: `LAN_CONNECTION_INFO.md`

The PerfectMCP Admin Interface provides comprehensive management capabilities for your MCP server, making it easy to monitor, configure, and maintain your development assistance system.
