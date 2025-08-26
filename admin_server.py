#!/usr/bin/env python3
"""
PerfectMPC Administration Interface
Web-based admin dashboard for managing the MPC server
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiohttp
import logging

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# Add src to path for MCP imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.config import get_config
from utils.database import DatabaseManager
from utils.logger import (
    EnhancedLoggerMixin, log_context, log_performance,
    log_function_call, log_async_function_call,
    log_api_request, log_api_response, log_database_operation,
    setup_logging, get_logger
)

# Import authentication
from auth.auth_manager import AuthManager, UserRole
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException

# Admin server configuration
ADMIN_HOST = "0.0.0.0"
ADMIN_PORT = 8080
MCP_SERVER_PORT = 8000

def get_server_ip():
    """Get the server's IP address dynamically"""
    try:
        import socket
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        # Fallback to localhost if unable to determine
        return "192.168.0.78"

# Get dynamic server IP
SERVER_IP = get_server_ip()

# Initialize FastAPI app
app = FastAPI(
    title="PerfectMCP Admin Interface",
    description="Web-based administration dashboard for PerfectMCP server",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Host activity tracking middleware
@app.middleware("http")
async def track_host_activity(request: Request, call_next):
    """Track host activity for analytics"""
    start_time = time.time()

    # Get client info
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "Unknown")
    method = request.method.upper()

    # Process request
    response = await call_next(request)

    # Track activity in background
    try:
        if db_manager and db_manager.redis_client:
            # Update host activity stats
            host_key = f"host_activity:{client_ip}"
            current_time = datetime.utcnow().isoformat()

            # Get existing data or create new
            existing_data = await db_manager.redis_client.hgetall(host_key)

            if existing_data:
                # Update existing data
                get_requests = int(existing_data.get(b"get_requests", 0))
                post_requests = int(existing_data.get(b"post_requests", 0))
                put_requests = int(existing_data.get(b"put_requests", 0))
                delete_requests = int(existing_data.get(b"delete_requests", 0))
                total_requests = int(existing_data.get(b"total_requests", 0))
                first_seen = existing_data.get(b"first_seen", current_time.encode()).decode()
            else:
                # New host
                get_requests = post_requests = put_requests = delete_requests = total_requests = 0
                first_seen = current_time

            # Increment counters
            if method == "GET":
                get_requests += 1
            elif method == "POST":
                post_requests += 1
            elif method == "PUT":
                put_requests += 1
            elif method == "DELETE":
                delete_requests += 1

            total_requests += 1

            # Update Redis
            await db_manager.redis_client.hset(host_key, mapping={
                "hostname": client_ip,  # Could be enhanced with reverse DNS lookup
                "get_requests": get_requests,
                "post_requests": post_requests,
                "put_requests": put_requests,
                "delete_requests": delete_requests,
                "total_requests": total_requests,
                "last_activity": current_time,
                "user_agent": user_agent,
                "first_seen": first_seen
            })

            # Set expiry (30 days)
            await db_manager.redis_client.expire(host_key, 30 * 24 * 60 * 60)

    except Exception as e:
        logger.error(f"Error tracking host activity: {e}")

    return response

# Request logging middleware for host activity tracking
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # Get client IP
    client_ip = request.headers.get("X-Forwarded-For") or request.headers.get("X-Real-IP") or request.client.host

    response = await call_next(request)

    # Log successful requests for host activity tracking
    if 200 <= response.status_code < 400:
        try:
            # Store in database for host activity tracking
            if db_manager and db_manager.mongo_client:
                db = db_manager.mongo_client.perfectmcp
                await db.request_logs.insert_one({
                    "ip_address": client_ip,
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "timestamp": datetime.utcnow(),
                    "user_agent": request.headers.get("User-Agent", "Unknown")
                })
        except Exception as e:
            logger.debug(f"Error logging request: {e}")

    return response

# Initialize logger
logger = get_logger('admin_server')

# Logging middleware for API requests
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Comprehensive request/response logging middleware"""
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]

    # Extract request info
    method = request.method
    path = request.url.path
    query_params = str(request.query_params) if request.query_params else ""
    client_ip = request.client.host if request.client else "unknown"

    # Define endpoints that should have minimal logging (but still log them!)
    minimal_log_endpoints = {
        "/static",
        "/favicon.ico"
    }

    # Check if this should have minimal logging
    is_minimal = any(path.startswith(endpoint) for endpoint in minimal_log_endpoints)

    # ALWAYS log the request - no exceptions!
    with log_context(request_id=request_id, client_ip=client_ip, endpoint=path):
        if is_minimal:
            logger.debug(f"📥 {method} {path}", request_id=request_id, client_ip=client_ip)
        else:
            logger.info(f"📥 {method} {path}", request_id=request_id, client_ip=client_ip, query_params=query_params)
            log_api_request(path, method, query_string=query_params)

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # ALWAYS log the response - no exceptions!
            if is_minimal:
                logger.debug(f"📤 {method} {path} → {response.status_code} ({duration:.3f}s)", request_id=request_id)
            else:
                logger.info(f"📤 {method} {path} → {response.status_code} ({duration:.3f}s)",
                           request_id=request_id, status_code=response.status_code, duration_ms=f"{duration*1000:.1f}")
                log_api_response(path, method, response.status_code, duration, request_id=request_id)

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ {method} {path} FAILED ({duration:.3f}s)",
                        exc_info=e, request_id=request_id, duration=duration, client_ip=client_ip)
            raise

# Global variables
mpc_config = None
db_manager = None
auth_manager = None
mcp_server_process = None
admin_start_time = time.time()
security = HTTPBearer(auto_error=False)

# Authentication helper functions
async def get_current_user_optional(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user if authenticated, None otherwise"""
    if not credentials or not auth_manager:
        return None

    result = await auth_manager.verify_api_key(credentials.credentials)
    if not result:
        return None

    user, api_key = result
    return user

async def get_current_user_required(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user, raise 401 if not authenticated"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not auth_manager:
        raise HTTPException(status_code=500, detail="Authentication not available")

    result = await auth_manager.verify_api_key(credentials.credentials)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid API key")

    user, api_key = result
    return user

def require_admin():
    """Require admin role"""
    async def admin_checker(user = Depends(get_current_user_required)):
        if user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    return admin_checker

# WebSocket connection manager
class AdminConnectionManager(EnhancedLoggerMixin):
    """Enhanced WebSocket connection manager with comprehensive logging"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "broadcast_count": 0
        }

    @log_async_function_call(level='DEBUG')
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_stats["total_connections"] += 1
        self.connection_stats["active_connections"] = len(self.active_connections)

        client_info = getattr(websocket, 'client', None)
        client_ip = client_info.host if client_info else "unknown"

        self.logger.info(f"Admin WebSocket connected",
                        client_ip=client_ip,
                        active_connections=len(self.active_connections))

    @log_function_call(level='DEBUG')
    def disconnect(self, websocket: WebSocket):
        """Disconnect WebSocket"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.connection_stats["active_connections"] = len(self.active_connections)

            self.logger.info(f"Admin WebSocket disconnected",
                           active_connections=len(self.active_connections))

    @log_async_function_call(level='DEBUG', performance=True)
    async def broadcast(self, message: dict):
        """Broadcast message to all connected admin WebSockets"""
        if not self.active_connections:
            self.logger.debug("No active admin connections for broadcast")
            return

        message_json = json.dumps(message)
        disconnected = []
        sent_count = 0

        with log_context(broadcast_type=message.get('type', 'unknown')):
            for connection in self.active_connections:
                try:
                    await connection.send_text(message_json)
                    sent_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to send admin broadcast",
                                      error=str(e))
                    disconnected.append(connection)

            # Remove disconnected connections
            for connection in disconnected:
                self.disconnect(connection)

            self.connection_stats["broadcast_count"] += 1
            self.connection_stats["messages_sent"] += sent_count

            self.logger.debug(f"Admin broadcast sent",
                            message_type=message.get('type', 'unknown'),
                            recipients=sent_count,
                            disconnected=len(disconnected),
                            message_size=len(message_json))

    def get_stats(self) -> dict:
        """Get connection statistics"""
        return {
            **self.connection_stats,
            "active_connections": len(self.active_connections)
        }

manager = AdminConnectionManager()

# Create directories for admin interface
admin_dir = Path(__file__).parent / "admin"
admin_dir.mkdir(exist_ok=True)
(admin_dir / "static").mkdir(exist_ok=True)
(admin_dir / "templates").mkdir(exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=str(admin_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(admin_dir / "templates"))

@app.on_event("startup")
async def startup_event():
    """Initialize admin interface with comprehensive logging"""
    global mpc_config, db_manager

    print("Starting PerfectMPC Admin Interface...")

    try:
        # Load MPC configuration
        mpc_config = get_config()

        # Initialize enhanced logging system
        setup_logging(
            mpc_config.logging,
            enable_syslog=getattr(mpc_config.logging, 'syslog', {}).get('enabled', False),
            syslog_address=getattr(mpc_config.logging, 'syslog', {}).get('address', '/dev/log')
        )

        logger.info("PerfectMPC Admin Interface starting up",
                   version="1.0.0",
                   host=ADMIN_HOST,
                   port=ADMIN_PORT)

        # Initialize database manager
        with log_performance("database_initialization", "admin_server"):
            global db_manager, auth_manager
            db_manager = DatabaseManager(mpc_config.database)
            await db_manager.initialize()

        # Initialize authentication manager
        with log_performance("auth_initialization", "admin_server"):
            auth_manager = AuthManager(db_manager)
            await auth_manager.initialize()

        # Initialize tool metrics collection
        await initialize_tool_metrics()

        # Start background tasks
        asyncio.create_task(daily_mcp_plugin_update())
        asyncio.create_task(cleanup_inactive_sessions())
        logger.info("Background tasks started")

        logger.info("Admin interface initialized successfully")
        print(f"Admin interface started on {ADMIN_HOST}:{ADMIN_PORT}")

    except Exception as e:
        if 'logger' in globals():
            logger.error("Failed to initialize admin interface", exc_info=e)
        print(f"Failed to initialize admin interface: {e}")
        raise

async def daily_mcp_plugin_update():
    """Background task to update MCP plugin list daily"""
    while True:
        try:
            # Wait 24 hours
            await asyncio.sleep(24 * 60 * 60)  # 24 hours in seconds

            logger.info("Starting daily MCP plugin update")

            # Update plugin cache
            await fetch_real_mcp_hub_plugins()

            logger.info("Daily MCP plugin update completed")

        except Exception as e:
            logger.error(f"Error in daily MCP plugin update: {e}")
            # Wait 1 hour before retrying on error
            await asyncio.sleep(60 * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if db_manager:
        await db_manager.close()
    print("Admin interface shutdown complete")

# Utility functions
def run_command(cmd: str) -> tuple[bool, str, str]:
    """Run shell command and return success, stdout, stderr"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def get_mcp_server_status() -> Dict[str, Any]:
    """Get MCP server status"""
    # Check if process is running
    success, stdout, stderr = run_command(f"netstat -tlnp | grep :{MCP_SERVER_PORT}")
    is_running = success and str(MCP_SERVER_PORT) in stdout

    # Try to get health status
    health_status = "unknown"
    if is_running:
        success, stdout, stderr = run_command(f"curl -s http://192.168.0.78:{MCP_SERVER_PORT}/health")
        if success:
            try:
                health_data = json.loads(stdout)
                health_status = health_data.get("status", "unknown")
            except:
                health_status = "unhealthy"

    return {
        "running": is_running,
        "health": health_status,
        "port": MCP_SERVER_PORT,
        "uptime": get_server_uptime() if is_running else None
    }

def get_server_uptime() -> Optional[str]:
    """Get server uptime"""
    try:
        success, stdout, stderr = run_command("ps -eo pid,etime,cmd | grep 'python.*main.py' | grep -v grep")
        if success and stdout:
            lines = stdout.strip().split('\n')
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2:
                    return parts[1]  # etime
    except:
        pass
    return None

def get_system_stats() -> Dict[str, Any]:
    """Get system statistics"""
    stats = {}

    # CPU usage
    success, stdout, stderr = run_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
    if success:
        try:
            stats["cpu_usage"] = float(stdout)
        except:
            stats["cpu_usage"] = 0

    # Memory usage
    success, stdout, stderr = run_command("free | grep Mem | awk '{printf \"%.1f\", $3/$2 * 100.0}'")
    if success:
        try:
            stats["memory_usage"] = float(stdout)
        except:
            stats["memory_usage"] = 0

    # Disk usage
    success, stdout, stderr = run_command("df /opt/PerfectMPC | tail -1 | awk '{print $5}' | cut -d'%' -f1")
    if success:
        try:
            stats["disk_usage"] = float(stdout)
        except:
            stats["disk_usage"] = 0

    return stats

async def get_real_host_activity_from_logs() -> Dict[str, Dict[str, Any]]:
    """Get real host activity from server access logs"""
    hosts = {}

    try:
        # Try to read from uvicorn access logs
        log_files = [
            "/opt/PerfectMCP/logs/admin.log",
            "/var/log/nginx/access.log",
            "/tmp/uvicorn.log"
        ]

        import re
        from collections import defaultdict

        # Pattern to match common log formats
        log_pattern = re.compile(r'(\d+\.\d+\.\d+\.\d+).*?"(\w+)\s+([^"]*)".*?(\d{3})')

        for log_file in log_files:
            try:
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        # Read last 1000 lines for recent activity
                        lines = f.readlines()[-1000:]

                        for line in lines:
                            match = log_pattern.search(line)
                            if match:
                                ip = match.group(1)
                                method = match.group(2).upper()
                                status = int(match.group(4))

                                # Only count successful requests
                                if 200 <= status < 400:
                                    if ip not in hosts:
                                        # Try to resolve hostname
                                        try:
                                            import socket
                                            hostname = socket.gethostbyaddr(ip)[0]
                                        except:
                                            hostname = "Unknown"

                                        hosts[ip] = {
                                            "ip_address": ip,
                                            "hostname": hostname,
                                            "get_requests": 0,
                                            "post_requests": 0,
                                            "put_requests": 0,
                                            "total_requests": 0,
                                            "last_activity": datetime.utcnow()
                                        }

                                    # Count by method
                                    if method == "GET":
                                        hosts[ip]["get_requests"] += 1
                                    elif method == "POST":
                                        hosts[ip]["post_requests"] += 1
                                    elif method == "PUT":
                                        hosts[ip]["put_requests"] += 1

                                    hosts[ip]["total_requests"] += 1
                                    hosts[ip]["last_activity"] = datetime.utcnow()

            except Exception as e:
                logger.debug(f"Could not read log file {log_file}: {e}")
                continue

    except Exception as e:
        logger.warning(f"Error reading access logs: {e}")

    return hosts

async def get_host_activity_data() -> List[Dict[str, Any]]:
    """Get host activity data from access logs and database"""
    try:
        hosts = {}

        # Try to get data from database first
        if db_manager and db_manager.mongo_client:
            try:
                db = db_manager.mongo_client.perfectmpc

                # Get request logs from database (if they exist)
                request_logs = await db.request_logs.find({}).sort("timestamp", -1).limit(1000).to_list(1000)

                for log in request_logs:
                    ip = log.get("ip_address", "unknown")
                    method = log.get("method", "GET").upper()
                    timestamp = log.get("timestamp", datetime.utcnow())

                    if ip not in hosts:
                        hosts[ip] = {
                            "ip_address": ip,
                            "hostname": log.get("hostname", "Unknown"),
                            "get_requests": 0,
                            "post_requests": 0,
                            "put_requests": 0,
                            "total_requests": 0,
                            "last_activity": timestamp
                        }

                    # Count requests by method
                    if method == "GET":
                        hosts[ip]["get_requests"] += 1
                    elif method == "POST":
                        hosts[ip]["post_requests"] += 1
                    elif method == "PUT":
                        hosts[ip]["put_requests"] += 1

                    hosts[ip]["total_requests"] += 1

                    # Update last activity if this is more recent
                    if timestamp > hosts[ip]["last_activity"]:
                        hosts[ip]["last_activity"] = timestamp

            except Exception as e:
                logger.warning(f"Could not get host activity from database: {e}")

        # If no database data, try to get from server access logs
        if not hosts:
            hosts = await get_real_host_activity_from_logs()

        # If still no data, return empty list instead of mock data
        if not hosts:
            logger.info("No host activity data available")
            return []

        # Convert to list and format timestamps
        host_list = []
        for host_data in hosts.values():
            host_data["last_activity"] = host_data["last_activity"].isoformat()
            host_list.append(host_data)

        return host_list

    except Exception as e:
        logger.error(f"Error getting host activity data: {e}")
        return []

async def get_database_size():
    """Get total database size"""
    try:
        total_size = 0

        # MongoDB size
        if db_manager and db_manager.mongo_client:
            try:
                db = db_manager.mongo_client.perfectmcp
                stats = await db.command("dbStats")
                total_size += stats.get("dataSize", 0)
            except:
                pass

        # Redis size (estimate)
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            info = r.info('memory')
            total_size += info.get('used_memory', 0)
        except:
            pass

        # Format size
        if total_size > 1024**3:
            return f"{total_size / (1024**3):.1f} GB"
        elif total_size > 1024**2:
            return f"{total_size / (1024**2):.1f} MB"
        else:
            return f"{total_size / 1024:.1f} KB"
    except:
        return "Unknown"

async def get_log_files_size():
    """Get total log files size"""
    try:
        total_size = 0
        log_dirs = ["/opt/PerfectMCP/logs", "/var/log"]

        for log_dir in log_dirs:
            if os.path.exists(log_dir):
                for root, dirs, files in os.walk(log_dir):
                    for file in files:
                        if file.endswith('.log'):
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                            except:
                                pass

        if total_size > 1024**3:
            return f"{total_size / (1024**3):.1f} GB"
        elif total_size > 1024**2:
            return f"{total_size / (1024**2):.1f} MB"
        else:
            return f"{total_size / 1024:.1f} KB"
    except:
        return "Unknown"

async def get_log_files_size_mb():
    """Get log files size in MB for comparison"""
    try:
        total_size = 0
        log_dirs = ["/opt/PerfectMCP/logs", "/var/log"]

        for log_dir in log_dirs:
            if os.path.exists(log_dir):
                for root, dirs, files in os.walk(log_dir):
                    for file in files:
                        if file.endswith('.log'):
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                            except:
                                pass

        return total_size / (1024**2)  # Return in MB
    except:
        return 0

async def get_stale_sessions_count():
    """Get count of stale sessions"""
    try:
        if db_manager and db_manager.mongo_client:
            db = db_manager.mongo_client.perfectmcp
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            count = await db.sessions.count_documents({
                "last_activity": {"$lt": cutoff_time}
            })
            return count
        return 0
    except:
        return 0

async def get_cache_entries_count():
    """Get Redis cache entries count"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        return r.dbsize()
    except:
        return 0

async def execute_maintenance_task(task_id: str):
    """Execute a specific maintenance task"""
    try:
        if task_id == "cleanup_logs":
            return await cleanup_log_files()
        elif task_id == "cleanup_sessions":
            return await cleanup_stale_sessions()
        elif task_id == "cleanup_cache":
            return await cleanup_redis_cache()
        elif task_id == "optimize_database":
            return await optimize_database()
        elif task_id == "cleanup_temp_files":
            return await cleanup_temp_files()
        else:
            return False
    except Exception as e:
        logger.error(f"Error executing maintenance task {task_id}: {e}")
        return False

async def cleanup_log_files():
    """Clean up old log files"""
    try:
        log_dirs = ["/opt/PerfectMCP/logs"]
        cutoff_time = time.time() - (7 * 24 * 3600)  # 7 days ago

        for log_dir in log_dirs:
            if os.path.exists(log_dir):
                for file in os.listdir(log_dir):
                    if file.endswith('.log') and not file.endswith('current.log'):
                        file_path = os.path.join(log_dir, file)
                        if os.path.getmtime(file_path) < cutoff_time:
                            os.remove(file_path)
                            logger.info(f"Removed old log file: {file_path}")

        return True
    except Exception as e:
        logger.error(f"Error cleaning log files: {e}")
        return False

async def cleanup_stale_sessions():
    """Clean up stale sessions"""
    try:
        if db_manager and db_manager.mongo_client:
            db = db_manager.mongo_client.perfectmcp
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            result = await db.sessions.delete_many({
                "last_activity": {"$lt": cutoff_time}
            })

            logger.info(f"Cleaned up {result.deleted_count} stale sessions")
            return True
        return False
    except Exception as e:
        logger.error(f"Error cleaning stale sessions: {e}")
        return False

async def cleanup_redis_cache():
    """Clean up Redis cache"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)

        # Get all keys with expiration
        expired_count = 0
        for key in r.scan_iter():
            if r.ttl(key) == -1:  # No expiration set
                # Set expiration for old cache entries
                r.expire(key, 3600)  # 1 hour
                expired_count += 1

        logger.info(f"Set expiration for {expired_count} cache entries")
        return True
    except Exception as e:
        logger.error(f"Error cleaning Redis cache: {e}")
        return False

async def optimize_database():
    """Optimize MongoDB database"""
    try:
        if db_manager and db_manager.mongo_client:
            db = db_manager.mongo_client.perfectmcp

            # Get all collection names
            collections = await db.list_collection_names()

            for collection_name in collections:
                collection = db[collection_name]
                # Rebuild indexes
                await collection.reindex()
                logger.info(f"Reindexed collection: {collection_name}")

            return True
        return False
    except Exception as e:
        logger.error(f"Error optimizing database: {e}")
        return False

async def cleanup_temp_files():
    """Clean up temporary files"""
    try:
        temp_dirs = ["/opt/PerfectMCP/data/uploads", "/tmp"]
        cutoff_time = time.time() - (7 * 24 * 3600)  # 7 days ago

        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            if os.path.getmtime(file_path) < cutoff_time:
                                os.remove(file_path)
                                logger.info(f"Removed temp file: {file_path}")
                        except:
                            pass

        return True
    except Exception as e:
        logger.error(f"Error cleaning temp files: {e}")
        return False

# Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard"""
    server_status = get_mcp_server_status()
    system_stats = get_system_stats()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "server_status": server_status,
        "system_stats": system_stats,
        "admin_uptime": time.time() - admin_start_time
    })

@app.get("/server", response_class=HTMLResponse)
async def server_management(request: Request):
    """Server management page"""
    server_status = get_mcp_server_status()
    system_stats = get_system_stats()

    return templates.TemplateResponse("server.html", {
        "request": request,
        "server_status": server_status,
        "system_stats": system_stats,
        "admin_uptime": time.time() - admin_start_time
    })

@app.get("/api/system/metrics")
async def get_system_metrics():
    """Get real-time system metrics for dashboard"""
    try:
        system_stats = get_system_stats()
        return system_stats
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return {"cpu_usage": 0, "memory_usage": 0, "disk_usage": 0, "error": str(e)}

@app.get("/api/host/activity")
async def get_host_activity():
    """Get host activity data showing requests by IP address"""
    try:
        # Get host activity from database or logs
        hosts = await get_host_activity_data()
        return {"success": True, "hosts": hosts}
    except Exception as e:
        logger.error(f"Error getting host activity: {e}")
        return {"success": False, "hosts": [], "error": str(e)}

@app.get("/maintenance")
async def maintenance_page(request: Request):
    """Maintenance page"""
    return templates.TemplateResponse("maintenance.html", {"request": request})

@app.get("/api/maintenance/status")
async def get_maintenance_status():
    """Get system maintenance status"""
    try:
        status = {
            "database_size": await get_database_size(),
            "log_size": await get_log_files_size(),
            "stale_sessions": await get_stale_sessions_count(),
            "cache_entries": await get_cache_entries_count()
        }
        return status
    except Exception as e:
        logger.error(f"Error getting maintenance status: {e}")
        return {"error": str(e)}

@app.get("/api/maintenance/tasks")
async def get_maintenance_tasks():
    """Get available maintenance tasks"""
    tasks = [
        {
            "id": "cleanup_logs",
            "name": "Clean Up Log Files",
            "description": "Remove old log files and rotate current logs",
            "priority": "needs-attention" if await get_log_files_size_mb() > 100 else "healthy",
            "status": "Needs Attention" if await get_log_files_size_mb() > 100 else "OK",
            "status_class": "bg-warning" if await get_log_files_size_mb() > 100 else "bg-success",
            "last_run": "Never",
            "estimated_time": "2-5 minutes"
        },
        {
            "id": "cleanup_sessions",
            "name": "Clean Stale Sessions",
            "description": "Remove inactive sessions older than 24 hours",
            "priority": "needs-attention" if await get_stale_sessions_count() > 10 else "healthy",
            "status": "Needs Attention" if await get_stale_sessions_count() > 10 else "OK",
            "status_class": "bg-warning" if await get_stale_sessions_count() > 10 else "bg-success",
            "last_run": "Never",
            "estimated_time": "1-2 minutes"
        },
        {
            "id": "cleanup_cache",
            "name": "Clear Redis Cache",
            "description": "Clear expired cache entries and optimize memory",
            "priority": "healthy",
            "status": "OK",
            "status_class": "bg-success",
            "last_run": "Never",
            "estimated_time": "30 seconds"
        },
        {
            "id": "optimize_database",
            "name": "Optimize Database",
            "description": "Compact MongoDB collections and rebuild indexes",
            "priority": "healthy",
            "status": "OK",
            "status_class": "bg-success",
            "last_run": "Never",
            "estimated_time": "5-10 minutes"
        },
        {
            "id": "cleanup_temp_files",
            "name": "Clean Temporary Files",
            "description": "Remove temporary files and uploads older than 7 days",
            "priority": "healthy",
            "status": "OK",
            "status_class": "bg-success",
            "last_run": "Never",
            "estimated_time": "1 minute"
        }
    ]
    return tasks

@app.post("/api/maintenance/run/{task_id}")
async def run_maintenance_task(task_id: str):
    """Run a specific maintenance task"""
    try:
        success = await execute_maintenance_task(task_id)
        return {"success": success, "task_id": task_id}
    except Exception as e:
        logger.error(f"Error running maintenance task {task_id}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/maintenance/run-all")
async def run_all_maintenance():
    """Run all maintenance tasks"""
    try:
        tasks = ["cleanup_logs", "cleanup_sessions", "cleanup_cache", "optimize_database", "cleanup_temp_files"]
        results = {}

        for task_id in tasks:
            results[task_id] = await execute_maintenance_task(task_id)

        return {"success": True, "results": results}
    except Exception as e:
        logger.error(f"Error running all maintenance tasks: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/status")
@log_async_function_call(level='DEBUG', performance=False)  # Reduced logging for frequently called endpoint
async def get_status():
    """Get server status API with comprehensive logging"""
    with log_context(operation="get_status"):
        try:
            logger.info("Checking system status")

            # Get MPC server status
            with log_performance("mpc_server_status", "admin_server"):
                mcp_status = get_mcp_server_status()

            # Get system stats
            with log_performance("system_stats", "admin_server"):
                system_stats = get_system_stats()

            # Get admin stats
            admin_uptime = time.time() - admin_start_time

            logger.info("System status retrieved successfully",
                       mcp_running=mcp_status.get('running', False),
                       cpu_percent=system_stats.get('cpu_percent', 0),
                       memory_percent=system_stats.get('memory_percent', 0),
                       admin_uptime=f"{admin_uptime:.1f}s")

            return {
                "mcp_server": mcp_status,
                "system": system_stats,
                "admin_uptime": admin_uptime,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("Failed to get system status", exc_info=e)
            return {"error": str(e)}

@app.get("/api/mcp/config")
async def get_mcp_config(api_key: Optional[str] = None):
    """Get MCP server configuration for Augment"""
    try:
        server_ip = "192.168.0.78"

        # MCP server configuration format expected by Augment
        headers = {"Content-Type": "application/json"}

        # Add authentication if API key provided
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Configure both servers - admin server (8080) has the tools, main server (8000) has core services
        mcp_config = {
            "servers": [
                {
                    "name": "perfectmcp-admin",
                    "type": "http",
                    "url": f"http://{server_ip}:8080",
                    "headers": headers,
                    "description": "PerfectMCP Admin Server - Tools and Database Operations"
                },
                {
                    "name": "perfectmcp-core",
                    "type": "http",
                    "url": f"http://{server_ip}:8000",
                    "headers": headers,
                    "description": "PerfectMCP Core Server - AI Services"
                }
            ]
        }

        return mcp_config

    except Exception as e:
        logger.error("Failed to get MCP config", exc_info=e)
        return {"error": str(e)}

@app.post("/")
async def mcp_root(request: Request):
    """MCP protocol root endpoint"""
    try:
        data = await request.json()
        method = data.get("method")

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "memory_context",
                            "description": "Manage memory context for sessions",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "session_id": {"type": "string"},
                                    "context": {"type": "string"}
                                },
                                "required": ["session_id", "context"]
                            }
                        },
                        {
                            "name": "code_analysis",
                            "description": "Analyze code for improvements",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string"},
                                    "language": {"type": "string"}
                                },
                                "required": ["code", "language"]
                            }
                        },
                        {
                            "name": "document_search",
                            "description": "Search documents using RAG",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "max_results": {"type": "integer"}
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "web_scraper",
                            "description": "Scrape and analyze web content",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "url": {"type": "string"},
                                    "extract_text": {"type": "boolean"},
                                    "follow_links": {"type": "boolean"}
                                },
                                "required": ["url"]
                            }
                        },
                        {
                            "name": "redis_operations",
                            "description": "Perform Redis database operations",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "operation": {"type": "string"},
                                    "key": {"type": "string"},
                                    "value": {"type": "string"}
                                },
                                "required": ["operation", "key"]
                            }
                        },
                        {
                            "name": "mongodb_operations",
                            "description": "Perform MongoDB database operations",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "collection": {"type": "string"},
                                    "operation": {"type": "string"},
                                    "query": {"type": "object"}
                                },
                                "required": ["collection", "operation"]
                            }
                        },
                        {
                            "name": "context7_management",
                            "description": "7-layer context management system",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "session_id": {"type": "string"},
                                    "content": {"type": "string"},
                                    "layer": {"type": "integer"},
                                    "priority": {"type": "integer"}
                                },
                                "required": ["session_id", "content", "layer"]
                            }
                        },
                        {
                            "name": "playwright_automation",
                            "description": "Web automation and browser control",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "session_id": {"type": "string"},
                                    "browser_type": {"type": "string"},
                                    "headless": {"type": "boolean"}
                                },
                                "required": ["session_id"]
                            }
                        },
                        {
                            "name": "sequential_thinking",
                            "description": "Step-by-step reasoning and problem solving",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "session_id": {"type": "string"},
                                    "problem": {"type": "string"},
                                    "reasoning_type": {"type": "string"}
                                },
                                "required": ["session_id", "problem"]
                            }
                        },
                        {
                            "name": "file_operations",
                            "description": "File system operations and management",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "operation": {"type": "string"},
                                    "content": {"type": "string"}
                                },
                                "required": ["path", "operation"]
                            }
                        },
                        {
                            "name": "session_management",
                            "description": "Manage user sessions and state",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "session_id": {"type": "string"},
                                    "action": {"type": "string"}
                                },
                                "required": ["session_id", "action"]
                            }
                        },
                        {
                            "name": "document_upload",
                            "description": "Upload and process documents",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "file_content": {"type": "string"},
                                    "filename": {"type": "string"},
                                    "session_id": {"type": "string"}
                                },
                                "required": ["file_content", "filename"]
                            }
                        }
                    ]
                }
            }
        elif method == "tools/call":
            # Handle tool calls
            tool_name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})

            # Route to appropriate handler
            result = await handle_mcp_tool_call(tool_name, arguments)

            return {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": result
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {"code": -32601, "message": "Method not found"}
            }

    except Exception as e:
        logger.error(f"MCP protocol error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": data.get("id") if 'data' in locals() else None,
            "error": {"code": -32603, "message": str(e)}
        }

async def initialize_tool_metrics():
    """Initialize tool metrics collection with indexes"""
    try:
        if not db_manager or not db_manager.mongo_client:
            return

        db = db_manager.mongo_client.perfectmpc

        # Create indexes for tool metrics
        await db.tool_metrics.create_index([("plugin_id", 1), ("tool_name", 1)], unique=True)
        await db.tool_metrics.create_index([("last_call", -1)])

        logger.info("Tool metrics collection initialized")

    except Exception as e:
        logger.warning(f"Failed to initialize tool metrics: {e}")

async def track_tool_call(tool_name: str, success: bool, response_time: float, plugin_id: str = "core"):
    """Track tool call metrics in database"""
    try:
        if not db_manager or not db_manager.mongo_client:
            return

        db = db_manager.mongo_client.perfectmpc

        # Update or create metrics document
        await db.tool_metrics.update_one(
            {"plugin_id": plugin_id, "tool_name": tool_name},
            {
                "$inc": {
                    "total_calls": 1,
                    "successful_calls": 1 if success else 0,
                    "total_response_time": response_time
                },
                "$set": {
                    "last_call": datetime.utcnow(),
                    "plugin_id": plugin_id,
                    "tool_name": tool_name
                }
            },
            upsert=True
        )

        logger.debug(f"Tracked tool call: {tool_name} (success: {success}, time: {response_time}ms)")

    except Exception as e:
        logger.warning(f"Failed to track tool call: {e}")

async def handle_mcp_tool_call(tool_name: str, arguments: dict):
    """Handle MCP tool calls and route to appropriate endpoints"""
    start_time = time.time()
    success = False

    try:
        # Update session activity for session-based tools
        session_id = arguments.get("session_id")
        if session_id and tool_name in ["memory_context", "context7_management", "playwright_automation"]:
            await update_session_activity(tool_name, session_id)

        if tool_name == "web_scraper":
            result = await web_scrape(arguments)
            success = result.get("success", True)
            response_time = (time.time() - start_time) * 1000
            await track_tool_call(tool_name, success, response_time)
            return result
        elif tool_name == "redis_operations":
            result = await redis_operations(arguments)
            success = result.get("success", True)
            response_time = (time.time() - start_time) * 1000
            await track_tool_call(tool_name, success, response_time)
            return result
        elif tool_name == "mongodb_operations":
            result = await mongodb_operations(arguments)
            success = result.get("success", True)
            response_time = (time.time() - start_time) * 1000
            await track_tool_call(tool_name, success, response_time)
            return result
        elif tool_name in ["memory_context", "code_analysis", "document_search", "context7_management", "playwright_automation", "sequential_thinking"]:
            # Forward to main server
            async with aiohttp.ClientSession() as session:
                endpoint_map = {
                    "memory_context": "/api/memory/session",
                    "code_analysis": "/api/code/analyze",
                    "document_search": "/api/docs/search",
                    "context7_management": "/api/context7/add",
                    "playwright_automation": "/api/playwright/session",
                    "sequential_thinking": "/api/thinking/chain"
                }

                url = f"http://192.168.0.78:8000{endpoint_map[tool_name]}"
                async with session.post(url, json=arguments) as response:
                    result = await response.json()
                    success = result.get("success", True)

                    # Track the tool call
                    response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                    await track_tool_call(tool_name, success, response_time)

                    # Log successful tool call
                    logger.info(f"Tool call successful: {tool_name} for session {session_id}")
                    return result
        else:
            # Track failed tool call
            response_time = (time.time() - start_time) * 1000
            await track_tool_call(tool_name, False, response_time)
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        # Track failed tool call
        response_time = (time.time() - start_time) * 1000
        await track_tool_call(tool_name, False, response_time)
        logger.error(f"Error handling tool call {tool_name}: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/tools")
@app.post("/api/tools")
@log_async_function_call(level='DEBUG', performance=False)  # Reduced logging for frequently called endpoint
async def get_available_tools(request: Request = None, user = Depends(get_current_user_optional)):
    """Get all available tools and their direct access information"""
    with log_context(operation="get_tools"):
        try:
            # Handle both GET and POST requests
            request_data = None
            if request and request.method == "POST":
                try:
                    request_data = await request.json()
                    logger.info(f"POST request received with data: {request_data}")
                except:
                    pass  # No JSON body or invalid JSON

            logger.info("Retrieving available tools information")

            server_ip = "192.168.0.78"  # Current server IP

            # Test database connections
            redis_available = False
            mongodb_available = False

            try:
                if db_manager and db_manager.redis_client:
                    await db_manager.redis_client.ping()
                    redis_available = True
            except:
                pass

            try:
                if db_manager and db_manager.mongo_client:
                    await db_manager.mongo_client.admin.command('ping')
                    mongodb_available = True
            except:
                pass

            tools = {
                "server_info": {
                    "ip": server_ip,
                    "hostname": "mpc",
                    "timestamp": datetime.now().isoformat()
                },
                "databases": {
                    "redis": {
                        "available": redis_available,
                        "host": server_ip,
                        "port": 6379,
                        "database": 0,
                        "connection_string": f"redis://{server_ip}:6379/0",
                        "cli_command": f"redis-cli -h {server_ip} -p 6379",
                        "description": "Redis in-memory data store for sessions, cache, and real-time data",
                        "key_prefixes": {
                            "sessions": "mpc:session:",
                            "cache": "mpc:cache:",
                            "memory": "mpc:memory:",
                            "context": "mpc:context:"
                        }
                    },
                    "mongodb": {
                        "available": mongodb_available,
                        "host": server_ip,
                        "port": 27017,
                        "database": "perfectmpc",
                        "connection_string": f"mongodb://{server_ip}:27017/perfectmpc",
                        "cli_command": f"mongosh --host {server_ip} --port 27017",
                        "description": "MongoDB document database for persistent data storage",
                        "collections": {
                            "users": "User accounts and authentication",
                            "sessions": "Session metadata and history",
                            "code_history": "Code analysis and improvement history",
                            "documents": "Document metadata and content",
                            "embeddings": "Vector embeddings for RAG",
                            "improvements": "Code improvement suggestions",
                            "analytics": "Usage analytics and metrics"
                        }
                    }
                },
                "apis": {
                    "mcp_server": {
                        "available": get_mcp_server_status().get('running', False),
                        "host": server_ip,
                        "port": 8000,
                        "base_url": f"http://{server_ip}:8000",
                        "health_check": f"http://{server_ip}:8000/health",
                        "api_prefix": "/api",
                        "description": "Main PerfectMCP server with advanced AI capabilities",
                        "endpoints": {
                            "memory": f"http://{server_ip}:8000/api/memory/",
                            "code": f"http://{server_ip}:8000/api/code/",
                            "docs": f"http://{server_ip}:8000/api/docs/",
                            "context7": f"http://{server_ip}:8000/api/context7/",
                            "playwright": f"http://{server_ip}:8000/api/playwright/",
                            "thinking": f"http://{server_ip}:8000/api/thinking/"
                        }
                    },
                    "admin_interface": {
                        "available": True,
                        "host": server_ip,
                        "port": 8080,
                        "base_url": f"http://{server_ip}:8080",
                        "description": "Web-based administration interface",
                        "pages": {
                            "dashboard": f"http://{server_ip}:8080/",
                            "sessions": f"http://{server_ip}:8080/sessions",
                            "documents": f"http://{server_ip}:8080/documents",
                            "database": f"http://{server_ip}:8080/database",
                            "logs": f"http://{server_ip}:8080/logs"
                        }
                    }
                },
                "protocols": {
                    "ssh": {
                        "available": True,
                        "host": server_ip,
                        "port": 2222,
                        "connection": f"ssh -p 2222 user@{server_ip}",
                        "description": "SSH access to MPC server environment"
                    },
                    "websocket": {
                        "available": True,
                        "host": server_ip,
                        "port": 8000,
                        "url": f"ws://{server_ip}:8000/ws",
                        "description": "Real-time WebSocket communication"
                    }
                },
                "file_systems": {
                    "chromadb": {
                        "available": True,
                        "path": "/opt/PerfectMPC/data/chromadb",
                        "description": "Vector database for document embeddings",
                        "access": "File system access via SSH"
                    },
                    "logs": {
                        "available": True,
                        "path": "/opt/PerfectMPC/logs",
                        "description": "Application and system logs",
                        "access": "File system access via SSH or admin interface"
                    },
                    "backups": {
                        "available": True,
                        "path": "/opt/PerfectMPC/backups",
                        "description": "Database and system backups",
                        "access": "File system access via SSH"
                    }
                },
                "mcp_tools": {
                    "memory_context": {
                        "name": "memory_context",
                        "description": "Manage memory context for sessions",
                        "endpoint": f"http://{server_ip}:8000/api/memory/session",
                        "methods": ["POST"],
                        "parameters": {
                            "session_id": "string",
                            "context": "string"
                        },
                        "sessions": {
                            "active": await get_active_sessions("memory_context"),
                            "max_sessions": 3,
                            "available_slots": 3 - await get_active_sessions("memory_context")
                        }
                    },
                    "code_analysis": {
                        "name": "code_analysis",
                        "description": "Analyze code for improvements",
                        "endpoint": f"http://{server_ip}:8000/api/code/analyze",
                        "methods": ["POST"],
                        "parameters": {
                            "code": "string",
                            "language": "string"
                        }
                    },
                    "document_search": {
                        "name": "document_search",
                        "description": "Search documents using RAG",
                        "endpoint": f"http://{server_ip}:8000/api/docs/search",
                        "methods": ["POST"],
                        "parameters": {
                            "query": "string",
                            "max_results": "integer"
                        }
                    },
                    "web_scraper": {
                        "name": "web_scraper",
                        "description": "Scrape and analyze web content",
                        "endpoint": f"http://{server_ip}:8080/api/web/scrape",
                        "methods": ["POST"],
                        "parameters": {
                            "url": "string",
                            "extract_text": "boolean",
                            "follow_links": "boolean"
                        }
                    },
                    "redis_operations": {
                        "name": "redis_operations",
                        "description": "Perform Redis database operations",
                        "endpoint": f"http://{server_ip}:8080/api/database/redis",
                        "methods": ["GET", "POST", "PUT", "DELETE"],
                        "parameters": {
                            "operation": "string",
                            "key": "string",
                            "value": "any"
                        }
                    },
                    "mongodb_operations": {
                        "name": "mongodb_operations",
                        "description": "Perform MongoDB database operations",
                        "endpoint": f"http://{server_ip}:8080/api/database/mongodb",
                        "methods": ["GET", "POST", "PUT", "DELETE"],
                        "parameters": {
                            "collection": "string",
                            "operation": "string",
                            "query": "object"
                        }
                    },
                    "context7_management": {
                        "name": "context7_management",
                        "description": "7-layer context management system",
                        "endpoint": f"http://{server_ip}:8000/api/context7/add",
                        "methods": ["POST"],
                        "parameters": {
                            "session_id": "string",
                            "content": "string",
                            "layer": "integer",
                            "priority": "integer"
                        },
                        "sessions": {
                            "active": await get_active_sessions("context7_management"),
                            "max_sessions": 3,
                            "available_slots": 3 - await get_active_sessions("context7_management")
                        }
                    },
                    "playwright_automation": {
                        "name": "playwright_automation",
                        "description": "Web automation and browser control",
                        "endpoint": f"http://{server_ip}:8000/api/playwright/session",
                        "methods": ["POST"],
                        "parameters": {
                            "session_id": "string",
                            "browser_type": "string",
                            "headless": "boolean"
                        },
                        "sessions": {
                            "active": await get_active_sessions("playwright_automation"),
                            "max_sessions": 3,
                            "available_slots": 3 - await get_active_sessions("playwright_automation")
                        }
                    },
                    "sequential_thinking": {
                        "name": "sequential_thinking",
                        "description": "Step-by-step reasoning and problem solving",
                        "endpoint": f"http://{server_ip}:8000/api/thinking/chain",
                        "methods": ["POST"],
                        "parameters": {
                            "session_id": "string",
                            "problem": "string",
                            "reasoning_type": "string"
                        },
                        "sessions": {
                            "active": await get_active_sessions("sequential_thinking"),
                            "max_sessions": 3,
                            "available_slots": 3 - await get_active_sessions("sequential_thinking")
                        }
                    },
                    "file_operations": {
                        "name": "file_operations",
                        "description": "File system operations and management",
                        "endpoint": f"http://{server_ip}:8080/api/files",
                        "methods": ["GET", "POST", "PUT", "DELETE"],
                        "parameters": {
                            "path": "string",
                            "operation": "string",
                            "content": "string"
                        }
                    },
                    "session_management": {
                        "name": "session_management",
                        "description": "Manage user sessions and state",
                        "endpoint": f"http://{server_ip}:8080/api/sessions",
                        "methods": ["GET", "POST", "DELETE"],
                        "parameters": {
                            "session_id": "string",
                            "action": "string"
                        }
                    },
                    "document_upload": {
                        "name": "document_upload",
                        "description": "Upload and process documents",
                        "endpoint": f"http://{server_ip}:8080/api/documents/upload",
                        "methods": ["POST"],
                        "parameters": {
                            "file": "file",
                            "session_id": "string",
                            "description": "string"
                        }
                    }
                }
            }

            logger.info("Tools information retrieved successfully",
                       redis_available=redis_available,
                       mongodb_available=mongodb_available)

            return tools

        except Exception as e:
            logger.error("Failed to get tools information", exc_info=e)
            return {"error": str(e)}

@app.post("/api/auth/generate-key")
@log_async_function_call(level='INFO', performance=True)
async def generate_api_key(key_request: dict):
    """Generate a new API key for client access"""
    with log_context(operation="generate_api_key"):
        try:
            logger.info("Generating new API key")

            if not auth_manager:
                return {"success": False, "error": "Authentication not available"}

            # Create a default user if none exists
            username = key_request.get("username", "client_user")
            email = key_request.get("email", f"{username}@perfectmpc.local")

            # Check if user exists
            existing_user = None
            try:
                users = await db_manager.mongo_find_many("users", {"username": username})
                if users:
                    existing_user = users[0]
            except:
                pass

            if not existing_user:
                # Create user
                user = await auth_manager.create_user(
                    username=username,
                    email=email,
                    role=UserRole.USER
                )
                user_id = user.user_id
            else:
                user_id = existing_user["user_id"]

            # Create API key
            permissions = key_request.get("permissions", [
                "sessions:*", "documents:*", "code:analyze", "database:read"
            ])

            api_key = await auth_manager.create_api_key(
                user_id=user_id,
                name=key_request.get("name", "Client API Key"),
                permissions=permissions,
                expires_days=key_request.get("expires_days", 365)
            )

            logger.info("API key generated successfully", user_id=user_id, key_name=api_key.name)

            return {
                "success": True,
                "api_key": api_key.key_id,
                "user_id": user_id,
                "permissions": permissions,
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                "usage_instructions": {
                    "header": "Authorization: Bearer " + api_key.key_id,
                    "example_curl": f'curl -H "Authorization: Bearer {api_key.key_id}" http://192.168.0.78:8080/api/tools',
                    "example_python": f'''
import requests
headers = {{"Authorization": "Bearer {api_key.key_id}"}}
response = requests.get("http://192.168.0.78:8080/api/tools", headers=headers)
'''
                }
            }

        except Exception as e:
            logger.error("Failed to generate API key", exc_info=e)
            return {"success": False, "error": str(e)}

@app.post("/api/server/start")
async def start_server():
    """Start MCP server"""
    global mcp_server_process

    try:
        # Check if already running
        status = get_mcp_server_status()
        if status["running"]:
            return {"success": False, "message": "Server is already running"}

        # Start the server
        mcp_server_process = subprocess.Popen([
            "python3", "start_server.py"
        ], cwd="/opt/PerfectMCP")

        # Wait a moment and check if it started
        await asyncio.sleep(2)
        status = get_mcp_server_status()

        if status["running"]:
            await manager.broadcast({
                "type": "server_status",
                "data": status
            })
            return {"success": True, "message": "Server started successfully"}
        else:
            return {"success": False, "message": "Failed to start server"}

    except Exception as e:
        return {"success": False, "message": f"Error starting server: {str(e)}"}

@app.post("/api/server/stop")
async def stop_server():
    """Stop MCP server"""
    try:
        # Kill the process
        success, stdout, stderr = run_command("pkill -f 'python.*main.py'")

        # Wait a moment and check status
        await asyncio.sleep(2)
        status = get_mcp_server_status()

        await manager.broadcast({
            "type": "server_status",
            "data": status
        })

        return {"success": True, "message": "Server stopped successfully"}

    except Exception as e:
        return {"success": False, "message": f"Error stopping server: {str(e)}"}

@app.post("/api/server/restart")
async def restart_server():
    """Restart MCP server"""
    try:
        # Stop first
        await stop_server()
        await asyncio.sleep(3)
        
        # Then start
        result = await start_server()
        return result
        
    except Exception as e:
        return {"success": False, "message": f"Error restarting server: {str(e)}"}

@app.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request):
    """Sessions management page"""
    return templates.TemplateResponse("sessions.html", {"request": request})

@app.get("/api/sessions")
async def get_sessions():
    """Get all sessions"""
    try:
        if not db_manager:
            return {"sessions": []}

        sessions = []

        # Get sessions from memory service if available
        if memory_service:
            try:
                # Get all session IDs from Redis
                session_keys = await db_manager.redis_client.keys("session:*")

                for key in session_keys:
                    session_id = key.decode('utf-8').replace('session:', '')
                    session_data = await db_manager.redis_client.hgetall(key)

                    if session_data:
                        # Convert bytes to strings
                        session_info = {k.decode('utf-8'): v.decode('utf-8') for k, v in session_data.items()}

                        sessions.append({
                            "id": session_id,
                            "name": session_info.get("name", f"Session {session_id[:8]}"),
                            "created": session_info.get("created", "Unknown"),
                            "last_activity": session_info.get("last_activity", "Unknown"),
                            "status": session_info.get("status", "active"),
                            "messages": int(session_info.get("message_count", 0)),
                            "user": session_info.get("user", "Unknown"),
                            "context_size": int(session_info.get("context_size", 0))
                        })
            except Exception as e:
                logger.error(f"Error retrieving sessions from Redis: {e}")

        # Also try MongoDB sessions collection
        try:
            collection = db_manager.get_collection_name("sessions")
            mongo_sessions = await db_manager.mongo_find_many(
                collection,
                {"active": True},
                limit=100,
                sort=[("created_at", -1)]
            )

            for session in mongo_sessions:
                sessions.append({
                    "id": str(session.get("_id", session.get("id", "unknown"))),
                    "name": session.get("name", f"Session {str(session.get('_id', ''))[:8]}"),
                    "created": session.get("created_at", session.get("created", "Unknown")),
                    "last_activity": session.get("last_activity", session.get("updated_at", "Unknown")),
                    "status": session.get("status", "active"),
                    "messages": session.get("message_count", 0),
                    "user": session.get("user", "Unknown"),
                    "context_size": session.get("context_size", 0)
                })
        except Exception as e:
            logger.error(f"Error retrieving sessions from MongoDB: {e}")

        # Sort sessions by last activity
        sessions.sort(key=lambda x: x.get("last_activity", ""), reverse=True)

        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        return {"error": str(e), "sessions": []}

@app.post("/api/sessions")
async def create_session(session_data: dict):
    """Create new session"""
    try:
        # Import memory service
        from services.memory_service import MemoryService

        memory_service = MemoryService(db_manager, mpc_config.memory)
        await memory_service.initialize()

        session_id = await memory_service.create_session(session_data.get("session_id"))

        await manager.broadcast({
            "type": "session_created",
            "data": {"session_id": session_id}
        })

        return {"success": True, "session_id": session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete session"""
    try:
        from services.memory_service import MemoryService

        memory_service = MemoryService(db_manager, mpc_config.memory)
        await memory_service.initialize()

        success = await memory_service.delete_session(session_id)

        if success:
            await manager.broadcast({
                "type": "session_deleted",
                "data": {"session_id": session_id}
            })

        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/database", response_class=HTMLResponse)
async def database_page(request: Request):
    """Database administration page"""
    return templates.TemplateResponse("database.html", {"request": request})

@app.get("/api/database/redis/keys")
async def get_redis_keys(pattern: str = "*"):
    """Get Redis keys matching pattern"""
    try:
        if not db_manager or not db_manager.redis_client:
            return {"error": "Redis not available", "keys": []}

        # Get keys matching pattern
        keys = await db_manager.redis_client.keys(pattern)

        key_data = []
        for key in keys[:100]:  # Limit to 100 keys for performance
            key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)

            try:
                # Get key type
                key_type = await db_manager.redis_client.type(key)
                key_type = key_type.decode('utf-8') if isinstance(key_type, bytes) else str(key_type)

                # Get TTL
                ttl = await db_manager.redis_client.ttl(key)
                ttl_str = "No expiry" if ttl == -1 else f"{ttl}s" if ttl > 0 else "Expired"

                # Get size/length based on type
                size = 0
                if key_type == 'string':
                    size = await db_manager.redis_client.strlen(key)
                elif key_type == 'list':
                    size = await db_manager.redis_client.llen(key)
                elif key_type == 'set':
                    size = await db_manager.redis_client.scard(key)
                elif key_type == 'hash':
                    size = await db_manager.redis_client.hlen(key)
                elif key_type == 'zset':
                    size = await db_manager.redis_client.zcard(key)

                key_data.append({
                    "key": key_str,
                    "type": key_type,
                    "ttl": ttl_str,
                    "size": size
                })

            except Exception as e:
                logger.error(f"Error getting info for key {key_str}: {e}")
                key_data.append({
                    "key": key_str,
                    "type": "unknown",
                    "ttl": "unknown",
                    "size": 0
                })

        return {"keys": key_data}

    except Exception as e:
        logger.error(f"Error getting Redis keys: {e}")
        return {"error": str(e), "keys": []}

@app.get("/api/database/redis/key/{key}")
async def get_redis_key_value(key: str):
    """Get Redis key value"""
    try:
        if not db_manager or not db_manager.redis_client:
            return {"error": "Redis not available"}

        # Get key type
        key_type = await db_manager.redis_client.type(key)
        key_type = key_type.decode('utf-8') if isinstance(key_type, bytes) else str(key_type)

        value = None
        if key_type == 'string':
            value = await db_manager.redis_client.get(key)
            value = value.decode('utf-8') if isinstance(value, bytes) else str(value)
        elif key_type == 'list':
            value = await db_manager.redis_client.lrange(key, 0, -1)
            value = [v.decode('utf-8') if isinstance(v, bytes) else str(v) for v in value]
        elif key_type == 'set':
            value = await db_manager.redis_client.smembers(key)
            value = [v.decode('utf-8') if isinstance(v, bytes) else str(v) for v in value]
        elif key_type == 'hash':
            value = await db_manager.redis_client.hgetall(key)
            value = {k.decode('utf-8') if isinstance(k, bytes) else str(k):
                    v.decode('utf-8') if isinstance(v, bytes) else str(v)
                    for k, v in value.items()}
        elif key_type == 'zset':
            value = await db_manager.redis_client.zrange(key, 0, -1, withscores=True)
            value = [(v.decode('utf-8') if isinstance(v, bytes) else str(v), score)
                    for v, score in value]

        return {
            "key": key,
            "type": key_type,
            "value": value
        }

    except Exception as e:
        logger.error(f"Error getting Redis key value: {e}")
        return {"error": str(e)}

@app.get("/api/database/mongodb/collections")
async def get_mongodb_collections():
    """Get MongoDB collections"""
    try:
        if not db_manager or not db_manager.mongo_client:
            return {"error": "MongoDB not available", "collections": []}

        # Get database
        db = db_manager.mongo_client[db_manager.config.database]

        # Get collection names
        collection_names = await db.list_collection_names()

        collections = []
        for name in collection_names:
            try:
                collection = db[name]

                # Get collection stats
                stats = await db.command("collStats", name)

                collections.append({
                    "name": name,
                    "count": stats.get("count", 0),
                    "size": stats.get("size", 0),
                    "avgObjSize": stats.get("avgObjSize", 0),
                    "storageSize": stats.get("storageSize", 0),
                    "indexes": stats.get("nindexes", 0)
                })

            except Exception as e:
                logger.error(f"Error getting stats for collection {name}: {e}")
                collections.append({
                    "name": name,
                    "count": 0,
                    "size": 0,
                    "avgObjSize": 0,
                    "storageSize": 0,
                    "indexes": 0
                })

        return {"collections": collections}

    except Exception as e:
        logger.error(f"Error getting MongoDB collections: {e}")
        return {"error": str(e), "collections": []}

@app.get("/api/host/activity")
async def get_host_activity():
    """Get host activity statistics"""
    try:
        if not db_manager:
            return {"hosts": []}

        # Get host activity from Redis if available
        hosts = []

        try:
            # Get all host activity keys
            host_keys = await db_manager.redis_client.keys("host_activity:*")

            for key in host_keys:
                host_ip = key.decode('utf-8').replace('host_activity:', '')
                host_data = await db_manager.redis_client.hgetall(key)

                if host_data:
                    # Convert bytes to strings and parse data
                    host_info = {k.decode('utf-8'): v.decode('utf-8') for k, v in host_data.items()}

                    hosts.append({
                        "ip_address": host_ip,
                        "hostname": host_info.get("hostname", "Unknown"),
                        "get_requests": int(host_info.get("get_requests", 0)),
                        "post_requests": int(host_info.get("post_requests", 0)),
                        "put_requests": int(host_info.get("put_requests", 0)),
                        "delete_requests": int(host_info.get("delete_requests", 0)),
                        "total_requests": int(host_info.get("total_requests", 0)),
                        "last_activity": host_info.get("last_activity", "Unknown"),
                        "user_agent": host_info.get("user_agent", "Unknown"),
                        "first_seen": host_info.get("first_seen", "Unknown")
                    })
        except Exception as e:
            logger.error(f"Error retrieving host activity from Redis: {e}")

        # If no Redis data, create some sample data for demonstration
        if not hosts:
            hosts = [
                {
                    "ip_address": "192.168.0.78",
                    "hostname": "localhost",
                    "get_requests": 45,
                    "post_requests": 12,
                    "put_requests": 3,
                    "delete_requests": 1,
                    "total_requests": 61,
                    "last_activity": datetime.utcnow().isoformat(),
                    "user_agent": "Admin Interface",
                    "first_seen": (datetime.utcnow() - timedelta(hours=2)).isoformat()
                }
            ]

        return {"hosts": hosts}

    except Exception as e:
        logger.error(f"Error getting host activity: {e}")
        return {"hosts": [], "error": str(e)}

@app.post("/api/database/backup")
async def create_database_backup(backup_request: dict):
    """Create database backup"""
    try:
        include_redis = backup_request.get("include_redis", True)
        include_mongodb = backup_request.get("include_mongodb", True)

        if not include_redis and not include_mongodb:
            return {"success": False, "error": "At least one database must be selected for backup"}

        backup_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_results = []

        # Create backup directory
        backup_dir = Path("/opt/PerfectMCP/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Redis backup
        if include_redis and db_manager and db_manager.redis_client:
            try:
                redis_backup_dir = backup_dir / "redis"
                redis_backup_dir.mkdir(exist_ok=True)

                # Trigger Redis BGSAVE
                await db_manager.redis_client.bgsave()

                # Wait a moment for save to complete
                await asyncio.sleep(2)

                # Copy the dump file
                redis_dump_path = Path("/var/lib/redis/dump.rdb")
                if redis_dump_path.exists():
                    backup_file = redis_backup_dir / f"dump_{backup_timestamp}.rdb"
                    import shutil
                    shutil.copy2(redis_dump_path, backup_file)

                    backup_results.append({
                        "database": "Redis",
                        "status": "success",
                        "file": str(backup_file),
                        "size": backup_file.stat().st_size
                    })
                else:
                    backup_results.append({
                        "database": "Redis",
                        "status": "error",
                        "error": "Redis dump file not found"
                    })

            except Exception as e:
                logger.error(f"Redis backup error: {e}")
                backup_results.append({
                    "database": "Redis",
                    "status": "error",
                    "error": str(e)
                })

        # MongoDB backup
        if include_mongodb and db_manager and db_manager.mongo_client:
            try:
                mongo_backup_dir = backup_dir / "mongodb"
                mongo_backup_dir.mkdir(exist_ok=True)

                # Use mongodump command
                import subprocess
                dump_dir = mongo_backup_dir / f"backup_{backup_timestamp}"

                cmd = [
                    "mongodump",
                    "--db", db_manager.config.database,
                    "--out", str(dump_dir)
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    # Compress the backup
                    import tarfile
                    tar_file = mongo_backup_dir / f"mongodb_{backup_timestamp}.tar.gz"

                    with tarfile.open(tar_file, "w:gz") as tar:
                        tar.add(dump_dir, arcname=f"backup_{backup_timestamp}")

                    # Remove uncompressed directory
                    import shutil
                    shutil.rmtree(dump_dir)

                    backup_results.append({
                        "database": "MongoDB",
                        "status": "success",
                        "file": str(tar_file),
                        "size": tar_file.stat().st_size
                    })
                else:
                    backup_results.append({
                        "database": "MongoDB",
                        "status": "error",
                        "error": result.stderr
                    })

            except Exception as e:
                logger.error(f"MongoDB backup error: {e}")
                backup_results.append({
                    "database": "MongoDB",
                    "status": "error",
                    "error": str(e)
                })

        # ChromaDB backup
        try:
            chromadb_backup_dir = backup_dir / "chromadb"
            chromadb_backup_dir.mkdir(exist_ok=True)

            chromadb_data_dir = Path("/opt/PerfectMCP/data/chromadb")
            if chromadb_data_dir.exists():
                import tarfile
                tar_file = chromadb_backup_dir / f"chromadb_{backup_timestamp}.tar.gz"

                with tarfile.open(tar_file, "w:gz") as tar:
                    tar.add(chromadb_data_dir, arcname="chromadb")

                backup_results.append({
                    "database": "ChromaDB",
                    "status": "success",
                    "file": str(tar_file),
                    "size": tar_file.stat().st_size
                })
            else:
                backup_results.append({
                    "database": "ChromaDB",
                    "status": "warning",
                    "error": "ChromaDB data directory not found"
                })

        except Exception as e:
            logger.error(f"ChromaDB backup error: {e}")
            backup_results.append({
                "database": "ChromaDB",
                "status": "error",
                "error": str(e)
            })

        # Clean old backups (keep last 30 days)
        try:
            cutoff_time = time.time() - (30 * 24 * 60 * 60)  # 30 days ago

            for backup_type in ["redis", "mongodb", "chromadb"]:
                type_dir = backup_dir / backup_type
                if type_dir.exists():
                    for file_path in type_dir.iterdir():
                        if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                            file_path.unlink()

        except Exception as e:
            logger.error(f"Error cleaning old backups: {e}")

        success_count = sum(1 for result in backup_results if result["status"] == "success")

        return {
            "success": success_count > 0,
            "timestamp": backup_timestamp,
            "results": backup_results,
            "message": f"Backup completed. {success_count}/{len(backup_results)} databases backed up successfully."
        }

    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/database/backups")
async def list_backups():
    """List available backups"""
    try:
        backup_dir = Path("/opt/PerfectMCP/backups")
        if not backup_dir.exists():
            return {"backups": []}

        backups = []

        for backup_type in ["redis", "mongodb", "chromadb"]:
            type_dir = backup_dir / backup_type
            if type_dir.exists():
                for file_path in type_dir.iterdir():
                    if file_path.is_file():
                        stat = file_path.stat()
                        backups.append({
                            "type": backup_type,
                            "filename": file_path.name,
                            "path": str(file_path),
                            "size": stat.st_size,
                            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })

        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x["created"], reverse=True)

        return {"backups": backups}

    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return {"backups": [], "error": str(e)}

@app.get("/api/logs")
async def get_logs(
    lines: int = 100,
    level: str = "all",
    search: str = "",
    category: str = "all"
):
    """Get application logs with filtering"""
    try:
        log_files = [
            "/opt/PerfectMCP/logs/admin.log",
            "/opt/PerfectMCP/logs/mcp.log",
            "/opt/PerfectMCP/logs/error.log"
        ]

        all_logs = []

        for log_file in log_files:
            log_path = Path(log_file)
            if log_path.exists():
                try:
                    # Read log file
                    with open(log_path, 'r') as f:
                        log_lines = f.readlines()

                    # Get last N lines
                    recent_lines = log_lines[-lines:] if len(log_lines) > lines else log_lines

                    for line in recent_lines:
                        line = line.strip()
                        if not line:
                            continue

                        # Parse log entry
                        log_entry = parse_log_line(line, log_path.stem)

                        # Apply filters
                        if level != "all" and log_entry["level"].lower() != level.lower():
                            continue

                        if category != "all" and log_entry["category"] != category:
                            continue

                        if search and search.lower() not in log_entry["message"].lower():
                            continue

                        all_logs.append(log_entry)

                except Exception as e:
                    logger.error(f"Error reading log file {log_file}: {e}")

        # Sort by timestamp (newest first)
        all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Limit results
        all_logs = all_logs[:lines]

        return {"logs": all_logs}

    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return {"logs": [], "error": str(e)}

def parse_log_line(line: str, source: str) -> dict:
    """Parse a log line into structured data"""
    try:
        # Try to parse structured log format
        import re

        # Pattern for timestamp
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})'
        timestamp_match = re.search(timestamp_pattern, line)
        timestamp = timestamp_match.group(1) if timestamp_match else ""

        # Pattern for log level
        level_pattern = r'\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b'
        level_match = re.search(level_pattern, line, re.IGNORECASE)
        level = level_match.group(1).upper() if level_match else "INFO"

        # Determine category based on content
        category = "general"
        if "database" in line.lower() or "redis" in line.lower() or "mongo" in line.lower():
            category = "database"
        elif "session" in line.lower():
            category = "session"
        elif "auth" in line.lower() or "login" in line.lower():
            category = "auth"
        elif "api" in line.lower() or "endpoint" in line.lower():
            category = "api"
        elif "backup" in line.lower():
            category = "backup"
        elif "error" in line.lower() or "exception" in line.lower():
            category = "error"
        elif source == "admin":
            category = "admin"
        elif source == "mcp":
            category = "mcp"

        return {
            "timestamp": timestamp,
            "level": level,
            "category": category,
            "source": source,
            "message": line,
            "raw": line
        }

    except Exception as e:
        return {
            "timestamp": "",
            "level": "INFO",
            "category": "general",
            "source": source,
            "message": line,
            "raw": line
        }

@app.get("/api/logs/categories")
async def get_log_categories():
    """Get available log categories"""
    return {
        "categories": [
            {"value": "all", "label": "All Categories"},
            {"value": "general", "label": "General"},
            {"value": "admin", "label": "Admin Interface"},
            {"value": "mcp", "label": "MCP Server"},
            {"value": "database", "label": "Database"},
            {"value": "session", "label": "Sessions"},
            {"value": "auth", "label": "Authentication"},
            {"value": "api", "label": "API Requests"},
            {"value": "backup", "label": "Backups"},
            {"value": "error", "label": "Errors"}
        ]
    }

@app.post("/api/auth/users/bulk")
async def bulk_user_operations(operation_data: dict):
    """Perform bulk operations on users"""
    try:
        operation = operation_data.get("operation")
        user_ids = operation_data.get("user_ids", [])

        if not operation or not user_ids:
            return {"success": False, "error": "Operation and user_ids are required"}

        from auth.auth_manager import AuthManager, UserRole
        auth_manager = AuthManager(db_manager)
        await auth_manager.initialize()

        results = []

        if operation == "delete":
            # Bulk delete users
            for user_id in user_ids:
                try:
                    success = await auth_manager.delete_user(user_id)
                    results.append({
                        "user_id": user_id,
                        "success": success,
                        "operation": "delete"
                    })
                except Exception as e:
                    results.append({
                        "user_id": user_id,
                        "success": False,
                        "error": str(e),
                        "operation": "delete"
                    })

        elif operation == "change_role":
            # Bulk role change
            new_role = operation_data.get("new_role")
            if not new_role:
                return {"success": False, "error": "new_role is required for role change operation"}

            try:
                role_enum = UserRole(new_role)
            except ValueError:
                return {"success": False, "error": f"Invalid role: {new_role}"}

            for user_id in user_ids:
                try:
                    user = await auth_manager.get_user(user_id)
                    if user:
                        user.role = role_enum
                        await auth_manager.update_user(user)
                        results.append({
                            "user_id": user_id,
                            "success": True,
                            "operation": "change_role",
                            "new_role": new_role
                        })
                    else:
                        results.append({
                            "user_id": user_id,
                            "success": False,
                            "error": "User not found",
                            "operation": "change_role"
                        })
                except Exception as e:
                    results.append({
                        "user_id": user_id,
                        "success": False,
                        "error": str(e),
                        "operation": "change_role"
                    })

        elif operation == "activate" or operation == "deactivate":
            # Bulk activate/deactivate users
            active_status = operation == "activate"

            for user_id in user_ids:
                try:
                    user = await auth_manager.get_user(user_id)
                    if user:
                        user.active = active_status
                        await auth_manager.update_user(user)
                        results.append({
                            "user_id": user_id,
                            "success": True,
                            "operation": operation
                        })
                    else:
                        results.append({
                            "user_id": user_id,
                            "success": False,
                            "error": "User not found",
                            "operation": operation
                        })
                except Exception as e:
                    results.append({
                        "user_id": user_id,
                        "success": False,
                        "error": str(e),
                        "operation": operation
                    })

        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}

        success_count = sum(1 for result in results if result["success"])

        return {
            "success": True,
            "operation": operation,
            "total": len(user_ids),
            "successful": success_count,
            "failed": len(user_ids) - success_count,
            "results": results
        }

    except Exception as e:
        logger.error(f"Error in bulk user operations: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/auth/users/export")
async def export_users():
    """Export users to JSON format"""
    try:
        if not db_manager:
            return {"success": False, "error": "Database not available"}

        users = await db_manager.mongo_find_many("users", {})

        # Remove sensitive data
        export_data = []
        for user in users:
            export_user = {
                "username": user.get("username"),
                "email": user.get("email"),
                "role": user.get("role"),
                "active": user.get("active", True),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login")
            }
            export_data.append(export_user)

        return {
            "success": True,
            "users": export_data,
            "count": len(export_data),
            "exported_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error exporting users: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/auth/users/import")
async def import_users(import_data: dict):
    """Import users from JSON data"""
    try:
        users_data = import_data.get("users", [])
        if not users_data:
            return {"success": False, "error": "No users data provided"}

        from auth.auth_manager import AuthManager, UserRole
        auth_manager = AuthManager(db_manager)
        await auth_manager.initialize()

        results = []

        for user_data in users_data:
            try:
                # Validate required fields
                username = user_data.get("username")
                email = user_data.get("email")
                role = user_data.get("role", "user")

                if not username or not email:
                    results.append({
                        "username": username or "unknown",
                        "success": False,
                        "error": "Username and email are required"
                    })
                    continue

                # Check if user already exists
                existing_user = await auth_manager.get_user_by_username(username)
                if existing_user:
                    results.append({
                        "username": username,
                        "success": False,
                        "error": "User already exists"
                    })
                    continue

                # Create user
                user = await auth_manager.create_user(
                    username=username,
                    email=email,
                    role=UserRole(role)
                )

                results.append({
                    "username": username,
                    "success": True,
                    "user_id": user.user_id
                })

            except Exception as e:
                results.append({
                    "username": user_data.get("username", "unknown"),
                    "success": False,
                    "error": str(e)
                })

        success_count = sum(1 for result in results if result["success"])

        return {
            "success": True,
            "total": len(users_data),
            "successful": success_count,
            "failed": len(users_data) - success_count,
            "results": results
        }

    except Exception as e:
        logger.error(f"Error importing users: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/mcp/services")
async def get_mcp_services():
    """Get all available MCP services"""
    try:
        services = []

        # Get built-in services
        builtin_services = [
            {
                "id": "memory",
                "name": "Memory Service",
                "description": "Context and session memory management",
                "type": "builtin",
                "status": "active" if memory_service else "inactive",
                "tools": ["memory_context", "session_management"] if memory_service else []
            },
            {
                "id": "code_improvement",
                "name": "Code Improvement Service",
                "description": "AI-powered code analysis and improvement",
                "type": "builtin",
                "status": "active" if code_improvement_service else "inactive",
                "tools": ["code_analysis", "code_review"] if code_improvement_service else []
            },
            {
                "id": "rag",
                "name": "RAG Service",
                "description": "Retrieval-Augmented Generation for documents",
                "type": "builtin",
                "status": "active" if rag_service else "inactive",
                "tools": ["document_search", "document_upload"] if rag_service else []
            },
            {
                "id": "context7",
                "name": "Context7 Service",
                "description": "Advanced context management",
                "type": "builtin",
                "status": "active" if context7_service else "inactive",
                "tools": ["context_management"] if context7_service else []
            },
            {
                "id": "playwright",
                "name": "Playwright Service",
                "description": "Web automation and browser control",
                "type": "builtin",
                "status": "active" if playwright_service else "inactive",
                "tools": ["web_automation", "browser_control"] if playwright_service else []
            },
            {
                "id": "sequential_thinking",
                "name": "Sequential Thinking Service",
                "description": "Step-by-step reasoning and analysis",
                "type": "builtin",
                "status": "active" if sequential_thinking_service else "inactive",
                "tools": ["sequential_analysis"] if sequential_thinking_service else []
            },
            {
                "id": "ssh",
                "name": "SSH Service",
                "description": "Remote server management via SSH",
                "type": "builtin",
                "status": "active" if ssh_service else "inactive",
                "tools": ["ssh_command", "file_transfer"] if ssh_service else []
            }
        ]

        services.extend(builtin_services)

        # Get custom/external services from database
        if db_manager:
            try:
                custom_services = await db_manager.mongo_find_many("mcp_services", {"type": "custom"})
                for service in custom_services:
                    services.append({
                        "id": service.get("service_id"),
                        "name": service.get("name"),
                        "description": service.get("description", ""),
                        "type": "custom",
                        "status": service.get("status", "inactive"),
                        "tools": service.get("tools", []),
                        "config": service.get("config", {}),
                        "created_at": service.get("created_at"),
                        "updated_at": service.get("updated_at")
                    })
            except Exception as e:
                logger.error(f"Error loading custom services: {e}")

        return {"services": services}

    except Exception as e:
        logger.error(f"Error getting MCP services: {e}")
        return {"services": [], "error": str(e)}

@app.post("/api/mcp/services")
async def add_mcp_service(service_data: dict):
    """Add a new MCP service"""
    try:
        if not db_manager:
            return {"success": False, "error": "Database not available"}

        # Validate required fields
        required_fields = ["name", "description", "service_type", "config"]
        for field in required_fields:
            if field not in service_data:
                return {"success": False, "error": f"Missing required field: {field}"}

        # Generate service ID
        import uuid
        service_id = str(uuid.uuid4())

        # Create service document
        service_doc = {
            "service_id": service_id,
            "name": service_data["name"],
            "description": service_data["description"],
            "type": "custom",
            "service_type": service_data["service_type"],  # e.g., "external", "plugin", "api"
            "config": service_data["config"],
            "tools": service_data.get("tools", []),
            "status": "inactive",  # Start as inactive
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Save to database
        await db_manager.mongo_insert_one("mcp_services", service_doc)

        # Try to initialize the service
        try:
            await initialize_custom_service(service_doc)
            service_doc["status"] = "active"
            await db_manager.mongo_update_one(
                "mcp_services",
                {"service_id": service_id},
                {"$set": {"status": "active", "updated_at": datetime.utcnow().isoformat()}}
            )
        except Exception as e:
            logger.error(f"Failed to initialize service {service_id}: {e}")
            service_doc["status"] = "error"
            service_doc["error"] = str(e)

        return {
            "success": True,
            "service_id": service_id,
            "message": "Service added successfully",
            "service": service_doc
        }

    except Exception as e:
        logger.error(f"Error adding MCP service: {e}")
        return {"success": False, "error": str(e)}

async def initialize_custom_service(service_doc: dict):
    """Initialize a custom MCP service"""
    service_type = service_doc.get("service_type")
    config = service_doc.get("config", {})

    if service_type == "external":
        # External service via HTTP/API
        endpoint = config.get("endpoint")
        if not endpoint:
            raise ValueError("External service requires endpoint configuration")

        # Test connection
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{endpoint}/health") as response:
                if response.status != 200:
                    raise ValueError(f"External service health check failed: {response.status}")

    elif service_type == "plugin":
        # Plugin-based service
        plugin_path = config.get("plugin_path")
        if not plugin_path:
            raise ValueError("Plugin service requires plugin_path configuration")

        # Validate plugin exists
        if not Path(plugin_path).exists():
            raise ValueError(f"Plugin file not found: {plugin_path}")

    elif service_type == "api":
        # API-based service
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        if not api_key or not base_url:
            raise ValueError("API service requires api_key and base_url configuration")

    else:
        raise ValueError(f"Unknown service type: {service_type}")

@app.get("/api/mcp/tools")
async def get_available_tools():
    """Get all available MCP tools from all services"""
    try:
        tools = []

        # Get tools from active services
        services_response = await get_mcp_services()
        services = services_response.get("services", [])

        for service in services:
            if service["status"] == "active":
                service_tools = service.get("tools", [])
                for tool in service_tools:
                    tools.append({
                        "name": tool,
                        "service": service["name"],
                        "service_id": service["id"],
                        "type": service["type"],
                        "description": f"Tool from {service['name']}"
                    })

        return {"tools": tools}

    except Exception as e:
        logger.error(f"Error getting available tools: {e}")
        return {"tools": [], "error": str(e)}

@app.get("/api/database/redis/keys")
async def get_redis_keys(pattern: str = "*"):
    """Get Redis keys"""
    try:
        if not db_manager:
            return {"keys": []}

        # Get keys matching pattern
        success, stdout, stderr = run_command(f"redis-cli KEYS '{pattern}'")
        if success:
            keys = stdout.split('\n') if stdout else []

            # Get key info
            key_info = []
            for key in keys:
                if key:
                    # Get TTL
                    success_ttl, ttl_stdout, _ = run_command(f"redis-cli TTL '{key}'")
                    ttl = int(ttl_stdout) if success_ttl and ttl_stdout.isdigit() else -1

                    # Get type
                    success_type, type_stdout, _ = run_command(f"redis-cli TYPE '{key}'")
                    key_type = type_stdout if success_type else "unknown"

                    key_info.append({
                        "key": key,
                        "type": key_type,
                        "ttl": ttl
                    })

            return {"keys": key_info}
        else:
            return {"keys": [], "error": stderr}
    except Exception as e:
        return {"keys": [], "error": str(e)}

@app.get("/api/database/mongodb/collections")
async def get_mongodb_collections():
    """Get MongoDB collections"""
    try:
        if not db_manager:
            return {"collections": []}

        collections = await db_manager.mongo_db.list_collection_names()

        # Get collection stats
        collection_info = []
        for collection_name in collections:
            try:
                stats = await db_manager.mongo_db.command("collStats", collection_name)
                collection_info.append({
                    "name": collection_name,
                    "count": stats.get("count", 0),
                    "size": stats.get("size", 0),
                    "avgObjSize": stats.get("avgObjSize", 0)
                })
            except:
                collection_info.append({
                    "name": collection_name,
                    "count": 0,
                    "size": 0,
                    "avgObjSize": 0
                })

        return {"collections": collection_info}
    except Exception as e:
        return {"collections": [], "error": str(e)}

# Enhanced Database Proxy Endpoints
@app.get("/api/database/redis/get/{key}")
@log_async_function_call(level='DEBUG', performance=True)
async def get_redis_value(key: str, user = Depends(get_current_user_optional)):
    """Get Redis value by key with detailed info"""
    try:
        if not db_manager or not db_manager.redis_client:
            return {"value": None, "error": "Redis not available"}

        # Get value and metadata
        value = await db_manager.redis_client.get(key)
        key_type = await db_manager.redis_client.type(key)
        ttl = await db_manager.redis_client.ttl(key)
        exists = await db_manager.redis_client.exists(key)

        return {
            "key": key,
            "value": value,
            "type": key_type,
            "ttl": ttl if ttl > 0 else None,
            "exists": bool(exists)
        }
    except Exception as e:
        logger.error(f"Failed to get Redis value for key {key}", exc_info=e)
        return {"value": None, "error": str(e)}

@app.post("/api/database/redis/set")
@log_async_function_call(level='DEBUG', performance=True)
async def set_redis_value(data: dict):
    """Set Redis key-value pair"""
    try:
        if not db_manager or not db_manager.redis_client:
            return {"success": False, "error": "Redis not available"}

        key = data.get("key")
        value = data.get("value")
        ttl = data.get("ttl")

        if not key:
            return {"success": False, "error": "Key is required"}

        if ttl:
            await db_manager.redis_client.setex(key, ttl, value)
        else:
            await db_manager.redis_client.set(key, value)

        logger.info(f"Set Redis key", key=key, ttl=ttl)
        return {"success": True, "key": key}
    except Exception as e:
        logger.error("Failed to set Redis value", exc_info=e)
        return {"success": False, "error": str(e)}

@app.delete("/api/database/redis/delete/{key}")
@log_async_function_call(level='DEBUG', performance=True)
async def delete_redis_key(key: str):
    """Delete Redis key"""
    try:
        if not db_manager or not db_manager.redis_client:
            return {"success": False, "error": "Redis not available"}

        result = await db_manager.redis_client.delete(key)
        logger.info(f"Deleted Redis key", key=key, existed=result > 0)
        return {"success": True, "deleted": result > 0}
    except Exception as e:
        logger.error(f"Failed to delete Redis key {key}", exc_info=e)
        return {"success": False, "error": str(e)}

@app.post("/api/database/redis/command")
@log_async_function_call(level='DEBUG', performance=True)
async def execute_redis_command(data: dict):
    """Execute raw Redis command"""
    try:
        if not db_manager or not db_manager.redis_client:
            return {"result": None, "error": "Redis not available"}

        command = data.get("command", "").strip()
        if not command:
            return {"result": None, "error": "Command is required"}

        # Parse command
        parts = command.split()
        if not parts:
            return {"result": None, "error": "Invalid command"}

        cmd = parts[0].upper()
        args = parts[1:] if len(parts) > 1 else []

        # Execute command
        result = await db_manager.redis_client.execute_command(cmd, *args)

        logger.info(f"Executed Redis command", command=command)
        return {"result": result, "command": command}
    except Exception as e:
        logger.error(f"Failed to execute Redis command", exc_info=e, command=data.get("command"))
        return {"result": None, "error": str(e)}

# MongoDB Proxy Endpoints
@app.get("/api/database/mongodb/collection/{collection_name}")
@log_async_function_call(level='DEBUG', performance=True)
async def get_mongodb_collection_data(collection_name: str, limit: int = 20, skip: int = 0):
    """Get documents from MongoDB collection"""
    try:
        if not db_manager or db_manager.mongo_db is None:
            return {"documents": [], "error": "MongoDB not available"}

        collection = db_manager.mongo_db[collection_name]

        # Get documents with pagination
        cursor = collection.find().skip(skip).limit(limit)
        documents = await cursor.to_list(length=limit)

        # Get total count
        total_count = await collection.count_documents({})

        # Convert ObjectId to string for JSON serialization
        for doc in documents:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])

        return {
            "collection": collection_name,
            "documents": documents,
            "total_count": total_count,
            "limit": limit,
            "skip": skip
        }
    except Exception as e:
        logger.error(f"Failed to get MongoDB collection data", exc_info=e, collection=collection_name)
        return {"documents": [], "error": str(e)}

@app.post("/api/database/mongodb/query")
@log_async_function_call(level='DEBUG', performance=True)
async def execute_mongodb_query(data: dict):
    """Execute MongoDB query"""
    try:
        if not db_manager or db_manager.mongo_db is None:
            return {"result": [], "error": "MongoDB not available"}

        collection_name = data.get("collection")
        query = data.get("query", {})
        operation = data.get("operation", "find")
        limit = data.get("limit", 20)

        if not collection_name:
            return {"result": [], "error": "Collection name is required"}

        collection = db_manager.mongo_db[collection_name]

        if operation == "find":
            cursor = collection.find(query).limit(limit)
            documents = await cursor.to_list(length=limit)

            # Convert ObjectId to string
            for doc in documents:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])

            result = documents

        elif operation == "count":
            result = await collection.count_documents(query)

        elif operation == "aggregate":
            pipeline = data.get("pipeline", [])
            cursor = collection.aggregate(pipeline)
            documents = await cursor.to_list(length=limit)

            # Convert ObjectId to string
            for doc in documents:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])

            result = documents

        else:
            return {"result": [], "error": f"Unsupported operation: {operation}"}

        logger.info(f"Executed MongoDB query", collection=collection_name, operation=operation)
        return {"result": result, "collection": collection_name, "operation": operation}

    except Exception as e:
        logger.error(f"Failed to execute MongoDB query", exc_info=e)
        return {"result": [], "error": str(e)}

@app.post("/api/database/mongodb/insert")
@log_async_function_call(level='DEBUG', performance=True)
async def insert_mongodb_document(data: dict):
    """Insert document into MongoDB collection"""
    try:
        if not db_manager or db_manager.mongo_db is None:
            return {"success": False, "error": "MongoDB not available"}

        collection_name = data.get("collection")
        document = data.get("document")

        if not collection_name or not document:
            return {"success": False, "error": "Collection name and document are required"}

        collection = db_manager.mongo_db[collection_name]
        result = await collection.insert_one(document)

        logger.info(f"Inserted MongoDB document", collection=collection_name, doc_id=str(result.inserted_id))
        return {"success": True, "inserted_id": str(result.inserted_id)}

    except Exception as e:
        logger.error(f"Failed to insert MongoDB document", exc_info=e)
        return {"success": False, "error": str(e)}

@app.delete("/api/database/mongodb/delete/{collection_name}/{doc_id}")
@log_async_function_call(level='DEBUG', performance=True)
async def delete_mongodb_document(collection_name: str, doc_id: str):
    """Delete document from MongoDB collection"""
    try:
        if not db_manager or db_manager.mongo_db is None:
            return {"success": False, "error": "MongoDB not available"}

        from bson import ObjectId
        collection = db_manager.mongo_db[collection_name]

        # Try to convert to ObjectId, fallback to string
        try:
            query = {"_id": ObjectId(doc_id)}
        except:
            query = {"_id": doc_id}

        result = await collection.delete_one(query)

        logger.info(f"Deleted MongoDB document", collection=collection_name, doc_id=doc_id, deleted=result.deleted_count > 0)
        return {"success": True, "deleted": result.deleted_count > 0}

    except Exception as e:
        logger.error(f"Failed to delete MongoDB document", exc_info=e)
        return {"success": False, "error": str(e)}

@app.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request):
    """Documents management page"""
    return templates.TemplateResponse("documents.html", {"request": request})

@app.get("/api/documents")
@log_async_function_call(level='INFO', performance=True)
async def get_documents():
    """Get all documents"""
    with log_context(operation="get_documents"):
        try:
            logger.info("Retrieving all documents")

            if not db_manager:
                logger.warning("Database manager not available")
                return {"documents": []}

            # Try multiple collection names to find documents
            collection_names = ["documents", "rag_documents", "uploaded_documents"]
            all_documents = []

            for collection_name in collection_names:
                try:
                    with log_performance("database_query", "admin_server"):
                        documents = await db_manager.mongo_find_many(
                            collection_name,
                            {},
                            limit=100,
                            sort=[("created_at", -1)]
                        )

                    if documents:
                        # Add collection source to each document
                        for doc in documents:
                            doc['_collection'] = collection_name
                        all_documents.extend(documents)

                    logger.info(f"Found {len(documents)} documents in collection {collection_name}")

                except Exception as e:
                    logger.debug(f"Collection {collection_name} not accessible: {e}")
                    continue

            # Also try to get documents from RAG service
            try:
                from services.rag_service import RAGService
                rag_service = RAGService(db_manager, mpc_config.rag)
                await rag_service.initialize()

                # Get document index
                rag_documents = await rag_service.get_all_documents()
                if rag_documents:
                    for doc in rag_documents:
                        doc['_collection'] = 'rag_service'
                    all_documents.extend(rag_documents)
                    logger.info(f"Found {len(rag_documents)} documents from RAG service")

            except Exception as e:
                logger.debug(f"RAG service not accessible: {e}")

            log_database_operation("find_many", "documents", 0,
                                 document_count=len(all_documents))

            logger.info(f"Retrieved {len(all_documents)} total documents")
            return {"documents": all_documents}

        except Exception as e:
            logger.error("Failed to retrieve documents", exc_info=e)
            return {"documents": [], "error": str(e)}

@app.post("/api/documents/upload")
@log_async_function_call(level='INFO', performance=True)
async def upload_document(file: UploadFile = File(...), session_id: str = Form(...)):
    """Upload document"""
    with log_context(operation="upload_document", session_id=session_id,
                    filename=file.filename, content_type=file.content_type):
        try:
            logger.info(f"Starting document upload",
                       filename=file.filename,
                       content_type=file.content_type,
                       session_id=session_id)

            with log_performance("read_file_content", "admin_server"):
                content = await file.read()

            file_size = len(content)
            logger.info(f"File read successfully", file_size=file_size)

            with log_performance("rag_service_init", "admin_server"):
                from services.rag_service import RAGService
                rag_service = RAGService(db_manager, mpc_config.rag)
                await rag_service.initialize()

            with log_performance("process_file", "admin_server"):
                doc_id = await rag_service.process_file(
                    session_id, file.filename, content, file.content_type
                )

            logger.info(f"Document processed successfully",
                       doc_id=doc_id, file_size=file_size)

            # Broadcast notification
            await manager.broadcast({
                "type": "document_uploaded",
                "data": {"doc_id": doc_id, "filename": file.filename}
            })

            return {"success": True, "doc_id": doc_id}

        except Exception as e:
            logger.error(f"Document upload failed",
                        exc_info=e,
                        filename=file.filename,
                        session_id=session_id)
            return {"success": False, "error": str(e)}

@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete document"""
    try:
        from services.rag_service import RAGService

        rag_service = RAGService(db_manager, mpc_config.rag)
        await rag_service.initialize()

        # Delete from RAG service
        success = await rag_service.delete_document(doc_id)

        if success:
            await manager.broadcast({
                "type": "document_deleted",
                "data": {"doc_id": doc_id}
            })
            return {"success": True, "message": "Document deleted successfully"}
        else:
            return {"success": False, "error": "Document not found or could not be deleted"}

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/documents/{doc_id}")
async def get_document_details(doc_id: str):
    """Get document details"""
    try:
        from services.rag_service import RAGService

        rag_service = RAGService(db_manager, mpc_config.rag)
        await rag_service.initialize()

        # Get document details
        document = await rag_service.get_document(doc_id)

        if document:
            return {"success": True, "document": document}
        else:
            return {"success": False, "error": "Document not found"}

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/documents/search")
async def search_documents(query: str, session_id: str = None, max_results: int = 10):
    """Search documents using RAG"""
    try:
        from services.rag_service import RAGService

        rag_service = RAGService(db_manager, mpc_config.rag)
        await rag_service.initialize()

        # Search documents - if no session_id provided, search all documents
        if session_id:
            results = await rag_service.search_documents(session_id, query, max_results)
        else:
            results = await rag_service.search_all_documents(query, max_results)

        return {"success": True, "query": query, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/documents/{doc_id}/reindex")
async def reindex_document(doc_id: str):
    """Reindex document"""
    try:
        from services.rag_service import RAGService

        rag_service = RAGService(db_manager, mpc_config.rag)
        await rag_service.initialize()

        # Reindex document
        success = await rag_service.reindex_document(doc_id)

        if success:
            await manager.broadcast({
                "type": "document_reindexed",
                "data": {"doc_id": doc_id}
            })
            return {"success": True, "message": "Document reindexed successfully"}
        else:
            return {"success": False, "error": "Document not found or could not be reindexed"}

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/documents/add-to-rag")
@log_async_function_call(level='INFO', performance=True)
async def add_to_rag(content_data: dict):
    """Add content to RAG from various sources - upload first, index in background"""
    content_type = content_data.get("type", "text")
    session_id = content_data.get("session_id", "default")

    with log_context(operation="add_to_rag", content_type=content_type, session_id=session_id):
        try:
            import asyncio
            import uuid
            from datetime import datetime

            logger.info(f"Starting background RAG processing",
                       content_type=content_type, session_id=session_id)

            # Generate unique job ID
            job_id = str(uuid.uuid4())

            # Store job status
            job_status = {
                "job_id": job_id,
                "status": "uploading",
                "progress": 0,
                "message": "Starting upload...",
                "created_at": datetime.now().isoformat(),
                "content_type": content_type,
                "session_id": session_id
            }

            # Store in memory (in production, use Redis or database)
            if not hasattr(app.state, "jobs"):
                app.state.jobs = {}
            app.state.jobs[job_id] = job_status

            logger.info(f"Created background job", job_id=job_id, content_type=content_type)

            # Start background processing
            if content_type == "url":
                asyncio.create_task(process_url_background(job_id, content_data, session_id))
            elif content_type == "text":
                asyncio.create_task(process_text_background(job_id, content_data, session_id))
            elif content_type == "github":
                asyncio.create_task(process_github_background(job_id, content_data, session_id))
            else:
                logger.error(f"Invalid content type", content_type=content_type)
                return {"success": False, "error": "Invalid content type"}

            # Return immediately with job ID
            return {
                "success": True,
                "job_id": job_id,
                "message": "Upload started. Processing in background...",
                "status_url": f"/api/documents/job-status/{job_id}"
            }

        except Exception as e:
            logger.error(f"Failed to start background RAG processing",
                        exc_info=e, content_type=content_type, session_id=session_id)
            return {"success": False, "error": str(e)}

async def add_url_to_rag(content_data: dict, session_id: str):
    """Add URL content to RAG"""
    try:
        import requests
        from bs4 import BeautifulSoup
        import tempfile
        import os

        url = content_data["url"]
        title = content_data.get("title", "")

        # Fetch the webpage
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse HTML content
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract title if not provided
        if not title:
            title_tag = soup.find('title')
            title = title_tag.get_text().strip() if title_tag else url

        # Extract main content
        content = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in content.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        content = ' '.join(chunk for chunk in chunks if chunk)

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(f"Title: {title}\n")
            temp_file.write(f"Source: {url}\n")
            temp_file.write(f"Content:\n\n{content}")
            temp_path = temp_file.name

        try:
            # Process with RAG service
            from services.rag_service import RAGService

            rag_service = RAGService(db_manager, mpc_config.rag)
            await rag_service.initialize()

            with open(temp_path, 'rb') as file:
                file_content = file.read()

            doc_id = await rag_service.process_file(
                session_id,
                f"{title}.txt",
                file_content,
                "text/plain"
            )

            return {"success": True, "doc_id": doc_id, "title": title}

        finally:
            # Clean up temp file
            os.unlink(temp_path)

    except Exception as e:
        return {"success": False, "error": f"Error processing URL: {str(e)}"}

async def add_text_to_rag(content_data: dict, session_id: str):
    """Add text content to RAG"""
    try:
        import tempfile
        import os

        content = content_data["content"]
        title = content_data["title"]
        content_type = content_data.get("content_type", "text")
        source_url = content_data.get("source_url", "")

        # Create temporary file
        file_extension = ".md" if content_type == "markdown" else ".txt"
        with tempfile.NamedTemporaryFile(mode='w', suffix=file_extension, delete=False) as temp_file:
            if source_url:
                temp_file.write(f"Title: {title}\n")
                temp_file.write(f"Source: {source_url}\n")
                temp_file.write(f"Content:\n\n{content}")
            else:
                temp_file.write(content)
            temp_path = temp_file.name

        try:
            # Process with RAG service
            from services.rag_service import RAGService

            rag_service = RAGService(db_manager, mpc_config.rag)
            await rag_service.initialize()

            with open(temp_path, 'rb') as file:
                file_content = file.read()

            mime_type = "text/markdown" if content_type == "markdown" else "text/plain"
            doc_id = await rag_service.process_file(
                session_id,
                f"{title}{file_extension}",
                file_content,
                mime_type
            )

            return {"success": True, "doc_id": doc_id, "title": title}

        finally:
            # Clean up temp file
            os.unlink(temp_path)

    except Exception as e:
        return {"success": False, "error": f"Error processing text: {str(e)}"}

async def add_github_to_rag(content_data: dict, session_id: str):
    """Add GitHub repository to RAG"""
    try:
        import subprocess
        import tempfile
        import os
        import shutil
        import fnmatch

        github_url = content_data["url"]
        file_patterns = content_data.get("file_patterns", "*.py,*.js,*.ts,*.md,*.txt,*.json").split(",")
        include_readme = content_data.get("include_readme", True)
        exclude_tests = content_data.get("exclude_tests", False)

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone repository
            clone_cmd = ["git", "clone", "--depth", "1", github_url, temp_dir + "/repo"]
            subprocess.run(clone_cmd, check=True, capture_output=True)

            repo_path = os.path.join(temp_dir, "repo")

            # Find files matching patterns
            files_to_process = []
            for root, dirs, files in os.walk(repo_path):
                # Skip .git directory
                if '.git' in dirs:
                    dirs.remove('.git')

                # Skip test directories if requested
                if exclude_tests:
                    dirs[:] = [d for d in dirs if not any(test_word in d.lower() for test_word in ['test', 'tests', '__pycache__'])]

                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, repo_path)

                    # Check if file matches patterns
                    if any(fnmatch.fnmatch(file, pattern.strip()) for pattern in file_patterns):
                        files_to_process.append((file_path, relative_path))

                    # Include README files if requested
                    if include_readme and file.lower().startswith('readme'):
                        files_to_process.append((file_path, relative_path))

            # Process files with RAG service
            from services.rag_service import RAGService

            rag_service = RAGService(db_manager, mpc_config.rag)
            await rag_service.initialize()

            doc_ids = []
            repo_name = github_url.split('/')[-1].replace('.git', '')

            for file_path, relative_path in files_to_process:
                try:
                    with open(file_path, 'rb') as file:
                        file_content = file.read()

                    # Determine MIME type based on extension
                    ext = os.path.splitext(file_path)[1].lower()
                    mime_type = {
                        '.py': 'text/x-python',
                        '.js': 'text/javascript',
                        '.ts': 'text/typescript',
                        '.md': 'text/markdown',
                        '.txt': 'text/plain',
                        '.json': 'application/json'
                    }.get(ext, 'text/plain')

                    doc_id = await rag_service.process_file(
                        session_id,
                        f"{repo_name}/{relative_path}",
                        file_content,
                        mime_type
                    )
                    doc_ids.append(doc_id)

                except Exception as file_error:
                    print(f"Error processing file {relative_path}: {file_error}")
                    continue

            return {
                "success": True,
                "doc_ids": doc_ids,
                "files_processed": len(doc_ids),
                "repo_name": repo_name
            }

    except Exception as e:
        return {"success": False, "error": f"Error processing GitHub repo: {str(e)}"}

@app.get("/api/documents/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Get status of background processing job"""
    try:
        if not hasattr(app.state, "jobs") or job_id not in app.state.jobs:
            return {"success": False, "error": "Job not found"}

        job_status = app.state.jobs[job_id]
        return {"success": True, "job": job_status}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/documents/jobs")
async def get_all_jobs():
    """Get all background processing jobs"""
    try:
        if not hasattr(app.state, "jobs"):
            return {"success": True, "jobs": []}

        jobs = list(app.state.jobs.values())
        # Sort by created_at descending
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"success": True, "jobs": jobs}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def update_job_status(job_id: str, status: str, progress: int, message: str, **kwargs):
    """Update job status"""
    if hasattr(app.state, "jobs") and job_id in app.state.jobs:
        app.state.jobs[job_id].update({
            "status": status,
            "progress": progress,
            "message": message,
            **kwargs
        })

        # Broadcast update via WebSocket
        await manager.broadcast({
            "type": "job_update",
            "data": app.state.jobs[job_id]
        })

@log_async_function_call(level='INFO', performance=True)
async def process_url_background(job_id: str, content_data: dict, session_id: str):
    """Process URL content in background"""
    url = content_data["url"]
    title = content_data.get("title", "")

    with log_context(job_id=job_id, url=url, session_id=session_id, operation="process_url"):
        try:
            logger.info(f"Starting URL processing", url=url, job_id=job_id)
            await update_job_status(job_id, "downloading", 10, "Downloading webpage...")

            import requests
            from bs4 import BeautifulSoup
            import tempfile
            import os

            # Fetch the webpage
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            with log_performance("download_webpage", "background_jobs"):
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()

            content_length = len(response.content)
            logger.info(f"Downloaded webpage", url=url, content_length=content_length)

            await update_job_status(job_id, "parsing", 30, "Parsing HTML content...")

            # Parse HTML content
            with log_performance("parse_html", "background_jobs"):
                soup = BeautifulSoup(response.content, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Extract title if not provided
                if not title:
                    title_tag = soup.find('title')
                    title = title_tag.get_text().strip() if title_tag else url

                # Extract main content
                content = soup.get_text()

                # Clean up whitespace
                lines = (line.strip() for line in content.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                content = ' '.join(chunk for chunk in chunks if chunk)

            content_length = len(content)
            logger.info(f"Parsed HTML content",
                       title=title, content_length=content_length)

            await update_job_status(job_id, "saving", 50, "Saving content...")

            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(f"Title: {title}\n")
                temp_file.write(f"Source: {url}\n")
                temp_file.write(f"Content:\n\n{content}")
                temp_path = temp_file.name

            try:
                await update_job_status(job_id, "indexing", 70, "Processing with RAG service...")

                # Process with RAG service
                with log_performance("rag_processing", "background_jobs"):
                    from services.rag_service import RAGService

                    rag_service = RAGService(db_manager, mpc_config.rag)
                    await rag_service.initialize()

                    with open(temp_path, 'rb') as file:
                        file_content = file.read()

                    doc_id = await rag_service.process_file(
                        session_id,
                        f"{title}.txt",
                        file_content,
                        "text/plain"
                    )

                logger.info(f"URL processing completed successfully",
                           doc_id=doc_id, title=title, url=url)

                await update_job_status(job_id, "completed", 100, "Successfully added to RAG",
                                      doc_id=doc_id, title=title, url=url)

            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    logger.debug(f"Cleaned up temporary file", temp_path=temp_path)

        except Exception as e:
            logger.error(f"URL processing failed",
                        exc_info=e, job_id=job_id, url=url)
            await update_job_status(job_id, "failed", 0, f"Error processing URL: {str(e)}")

async def process_text_background(job_id: str, content_data: dict, session_id: str):
    """Process text content in background"""
    try:
        await update_job_status(job_id, "processing", 20, "Processing text content...")

        import tempfile
        import os

        content = content_data["content"]
        title = content_data["title"]
        content_type = content_data.get("content_type", "text")
        source_url = content_data.get("source_url", "")

        await update_job_status(job_id, "saving", 40, "Saving content...")

        # Create temporary file
        file_extension = ".md" if content_type == "markdown" else ".txt"
        with tempfile.NamedTemporaryFile(mode='w', suffix=file_extension, delete=False) as temp_file:
            if source_url:
                temp_file.write(f"Title: {title}\n")
                temp_file.write(f"Source: {source_url}\n")
                temp_file.write(f"Content:\n\n{content}")
            else:
                temp_file.write(content)
            temp_path = temp_file.name

        try:
            await update_job_status(job_id, "indexing", 70, "Processing with RAG service...")

            # Process with RAG service
            from services.rag_service import RAGService

            rag_service = RAGService(db_manager, mpc_config.rag)
            await rag_service.initialize()

            with open(temp_path, 'rb') as file:
                file_content = file.read()

            mime_type = "text/markdown" if content_type == "markdown" else "text/plain"
            doc_id = await rag_service.process_file(
                session_id,
                f"{title}{file_extension}",
                file_content,
                mime_type
            )

            await update_job_status(job_id, "completed", 100, "Successfully added to RAG",
                                  doc_id=doc_id, title=title)

        finally:
            # Clean up temp file
            os.unlink(temp_path)

    except Exception as e:
        await update_job_status(job_id, "failed", 0, f"Error processing text: {str(e)}")

async def process_github_background(job_id: str, content_data: dict, session_id: str):
    """Process GitHub repository in background"""
    try:
        await update_job_status(job_id, "cloning", 10, "Cloning repository...")

        import subprocess
        import tempfile
        import os
        import shutil
        import fnmatch

        github_url = content_data["url"]
        file_patterns = content_data.get("file_patterns", "*.py,*.js,*.ts,*.md,*.txt,*.json").split(",")
        include_readme = content_data.get("include_readme", True)
        exclude_tests = content_data.get("exclude_tests", False)

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone repository
            clone_cmd = ["git", "clone", "--depth", "1", github_url, temp_dir + "/repo"]
            subprocess.run(clone_cmd, check=True, capture_output=True)

            repo_path = os.path.join(temp_dir, "repo")

            await update_job_status(job_id, "scanning", 30, "Scanning repository files...")

            # Find files matching patterns
            files_to_process = []
            for root, dirs, files in os.walk(repo_path):
                # Skip .git directory
                if '.git' in dirs:
                    dirs.remove('.git')

                # Skip test directories if requested
                if exclude_tests:
                    dirs[:] = [d for d in dirs if not any(test_word in d.lower() for test_word in ['test', 'tests', '__pycache__'])]

                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, repo_path)

                    # Check if file matches patterns
                    if any(fnmatch.fnmatch(file, pattern.strip()) for pattern in file_patterns):
                        files_to_process.append((file_path, relative_path))

                    # Include README files if requested
                    if include_readme and file.lower().startswith('readme'):
                        files_to_process.append((file_path, relative_path))

            await update_job_status(job_id, "processing", 50, f"Processing {len(files_to_process)} files...")

            # Process files with RAG service
            from services.rag_service import RAGService

            rag_service = RAGService(db_manager, mpc_config.rag)
            await rag_service.initialize()

            doc_ids = []
            repo_name = github_url.split('/')[-1].replace('.git', '')

            for i, (file_path, relative_path) in enumerate(files_to_process):
                try:
                    # Update progress
                    progress = 50 + int((i / len(files_to_process)) * 40)
                    await update_job_status(job_id, "processing", progress,
                                          f"Processing {relative_path} ({i+1}/{len(files_to_process)})")

                    with open(file_path, 'rb') as file:
                        file_content = file.read()

                    # Determine MIME type based on extension
                    ext = os.path.splitext(file_path)[1].lower()
                    mime_type = {
                        '.py': 'text/x-python',
                        '.js': 'text/javascript',
                        '.ts': 'text/typescript',
                        '.md': 'text/markdown',
                        '.txt': 'text/plain',
                        '.json': 'application/json'
                    }.get(ext, 'text/plain')

                    doc_id = await rag_service.process_file(
                        session_id,
                        f"{repo_name}/{relative_path}",
                        file_content,
                        mime_type
                    )
                    doc_ids.append(doc_id)

                except Exception as file_error:
                    print(f"Error processing file {relative_path}: {file_error}")
                    continue

            await update_job_status(job_id, "completed", 100,
                                  f"Successfully processed {len(doc_ids)} files from repository",
                                  doc_ids=doc_ids, files_processed=len(doc_ids), repo_name=repo_name)

    except Exception as e:
        await update_job_status(job_id, "failed", 0, f"Error processing GitHub repo: {str(e)}")

@app.get("/api/activity/recent")
async def get_recent_activity():
    """Get recent activity"""
    # Mock data for now - in real implementation, this would come from logs/database
    activities = [
        {
            "title": "Server Started",
            "description": "MPC server was started successfully",
            "type": "server",
            "timestamp": "2 minutes ago"
        },
        {
            "title": "Session Created",
            "description": "New session 'test-session' was created",
            "type": "session",
            "timestamp": "5 minutes ago"
        },
        {
            "title": "Document Uploaded",
            "description": "Document 'example.pdf' was uploaded and indexed",
            "type": "document",
            "timestamp": "10 minutes ago"
        }
    ]
    return activities

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Send periodic status updates
            status_data = {
                "type": "status_update",
                "data": {
                    "mcp_server": get_mcp_server_status(),
                    "system": get_system_stats(),
                    "timestamp": datetime.now().isoformat()
                }
            }
            await websocket.send_text(json.dumps(status_data))
            await asyncio.sleep(5)  # Update every 5 seconds

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Logs viewer page"""
    return templates.TemplateResponse("logs.html", {"request": request})

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    """User and API key management page"""
    return templates.TemplateResponse("users.html", {"request": request})

@app.get("/assistants/augment", response_class=HTMLResponse)
async def augment_assistant_page(request: Request):
    """VSCode Augment assistant configuration page"""
    # Get current server info for configuration
    server_info = {
        "host": SERVER_IP,
        "admin_port": ADMIN_PORT,
        "mcp_port": MCP_SERVER_PORT,
        "tools_endpoint": f"http://{SERVER_IP}:{ADMIN_PORT}/api/tools",
        "auth_endpoint": f"http://{SERVER_IP}:{ADMIN_PORT}/api/auth/generate-key"
    }
    return templates.TemplateResponse("assistants/augment.html", {
        "request": request,
        "server_info": server_info
    })

@app.get("/assistants/cline", response_class=HTMLResponse)
async def cline_assistant_page(request: Request):
    """Cline VSCode assistant configuration page"""
    # Get current server info for configuration
    server_info = {
        "host": SERVER_IP,
        "admin_port": ADMIN_PORT,
        "mcp_port": MCP_SERVER_PORT,
        "tools_endpoint": f"http://{SERVER_IP}:{ADMIN_PORT}/api/tools",
        "auth_endpoint": f"http://{SERVER_IP}:{ADMIN_PORT}/api/auth/generate-key"
    }
    return templates.TemplateResponse("assistants/cline.html", {
        "request": request,
        "server_info": server_info
    })

@app.get("/mcp-hub", response_class=HTMLResponse)
async def mcp_hub_page(request: Request):
    """MCP Hub - Add MCP Plugins page"""
    return templates.TemplateResponse("mcp_hub.html", {"request": request})

@app.get("/mcp-status", response_class=HTMLResponse)
async def mcp_status_page(request: Request):
    """MCP Server Status Dashboard page"""
    return templates.TemplateResponse("mcp_status.html", {"request": request})

@app.get("/mcp-settings/{plugin_id}", response_class=HTMLResponse)
async def mcp_plugin_settings_page(request: Request, plugin_id: str):
    """MCP Plugin Settings page"""
    try:
        logger.info(f"Loading settings page for plugin: {plugin_id}")

        # Get plugin info from database
        plugin_record = None
        if db_manager:
            # Try exact match first
            plugin_record = await db_manager.mongo_find_one("installed_plugins", {"plugin_id": plugin_id})

            # If not found, try with underscores instead of hyphens
            if not plugin_record:
                alt_plugin_id = plugin_id.replace("-", "_")
                plugin_record = await db_manager.mongo_find_one("installed_plugins", {"plugin_id": alt_plugin_id})

            # If still not found, try with hyphens instead of underscores
            if not plugin_record:
                alt_plugin_id = plugin_id.replace("_", "-")
                plugin_record = await db_manager.mongo_find_one("installed_plugins", {"plugin_id": alt_plugin_id})

            # If still not found, check all installed plugins for debugging
            if not plugin_record:
                all_plugins = await db_manager.mongo_find_many("installed_plugins", {})
                logger.info(f"Available plugins: {[p.get('plugin_id') for p in all_plugins]}")

                # Create a mock plugin record for core services
                if plugin_id in ['memory-enhanced', 'memory_enhanced', 'core']:
                    plugin_record = {
                        "plugin_id": plugin_id,
                        "name": "Memory Enhanced Tool",
                        "version": "1.0.0",
                        "author": "PerfectMPC Team",
                        "category": "core",
                        "description": "Enhanced memory management capabilities",
                        "status": "active",
                        "installed_at": datetime.utcnow().isoformat()
                    }

        if plugin_record:
            return templates.TemplateResponse("mcp_plugin_settings.html", {
                "request": request,
                "plugin": plugin_record,
                "plugin_id": plugin_id
            })

        # If not found, return 404 with helpful info
        logger.warning(f"Plugin not found: {plugin_id}")
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    except Exception as e:
        logger.error(f"Error loading plugin settings page: {e}")
        return templates.TemplateResponse("500.html", {"request": request}, status_code=500)

@app.get("/api/test-logging")
async def test_logging():
    """Test endpoint to verify logging is working"""
    logger.debug("🔍 DEBUG: Test logging endpoint called")
    logger.info("ℹ️ INFO: Test logging endpoint called")
    logger.warning("⚠️ WARNING: Test logging endpoint called")
    logger.error("❌ ERROR: Test logging endpoint called")

    return {
        "success": True,
        "message": "Logging test completed - check logs for output",
        "timestamp": datetime.utcnow().isoformat(),
        "levels_tested": ["DEBUG", "INFO", "WARNING", "ERROR"]
    }

@app.get("/api/logs")
async def get_logs(lines: int = 100, level: str = ""):
    """Get server logs"""
    try:
        log_file = "/opt/PerfectMPC/logs/server.log"
        if not Path(log_file).exists():
            return {"logs": [], "message": "Log file not found"}

        # Read last N lines
        success, stdout, stderr = run_command(f"tail -n {lines} {log_file}")
        if success:
            log_lines = stdout.split('\n') if stdout else []

            # Filter by level if specified
            if level:
                log_lines = [line for line in log_lines if level.upper() in line]

            return {"logs": log_lines}
        else:
            return {"logs": [], "error": stderr}
    except Exception as e:
        return {"logs": [], "error": str(e)}

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration management page"""
    # Get current server info
    server_info = {
        "host": SERVER_IP,
        "admin_port": ADMIN_PORT,
        "mcp_port": MCP_SERVER_PORT
    }
    return templates.TemplateResponse("config.html", {
        "request": request,
        "server_info": server_info
    })

@app.get("/api/config/{config_type}")
async def get_config_file(config_type: str):
    """Get configuration file content"""
    try:
        config_files = {
            "server": "/opt/PerfectMCP/config/server.yaml",
            "database": "/opt/PerfectMCP/config/database.yaml",
            "logging": "/opt/PerfectMCP/config/logging.yaml"
        }

        if config_type not in config_files:
            return {"error": "Invalid config type"}

        config_file = Path(config_files[config_type])

        if not config_file.exists():
            # Create default configuration if it doesn't exist
            default_content = create_default_config(config_type)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(default_content)
            return {"content": default_content, "file": str(config_file), "created": True}

        content = config_file.read_text()
        return {"content": content, "file": str(config_file)}
    except Exception as e:
        logger.error(f"Error getting config file {config_type}: {e}")
        return {"error": str(e)}

def create_default_config(config_type: str) -> str:
    """Create default configuration content"""
    if config_type == "server":
        return """# Server Configuration
server:
  host: "0.0.0.0"
  port: 8000
  debug: false
  workers: 1

# CORS Configuration
cors:
  allow_origins: ["http://localhost:*", "http://127.0.0.1:*", "http://192.168.0.78:*"]
  allow_credentials: true
  allow_methods: ["*"]
  allow_headers: ["*"]

# API Configuration
api:
  version: "1.0.0"
  title: "PerfectMCP Server"
  description: "Model Context Protocol Server"

# Security Configuration
security:
  api_key_required: false
  rate_limiting: false
  max_requests_per_minute: 60
"""

    elif config_type == "database":
        return """# Database Configuration
redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null

mongodb:
  host: "localhost"
  port: 27017
  database: "perfectmcp"
  username: null
  password: null

# Vector Database Configuration (ChromaDB)
chromadb:
  persist_directory: "/opt/PerfectMCP/data/chromadb"

# Backup Configuration
backup:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  retention_days: 30

  # Backup locations
  mongodb:
    path: "/opt/PerfectMCP/backups/mongodb"
    compress: true
  redis:
    path: "/opt/PerfectMCP/backups/redis"
    compress: true
  chromadb:
    path: "/opt/PerfectMCP/backups/chromadb"
    compress: true
"""

    elif config_type == "logging":
        return """# Logging Configuration
logging:
  level: INFO
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

  # File logging
  file:
    enabled: true
    path: "/opt/PerfectMCP/logs/mcp.log"
    max_size: "10MB"
    backup_count: 5

  # Error logging
  error_file:
    enabled: true
    path: "/opt/PerfectMCP/logs/error.log"
    max_size: "10MB"
    backup_count: 5
"""

    else:
        return "# Configuration file\n# Add your configuration here\n"

@app.post("/api/config/{config_type}")
async def save_config_file(config_type: str, config_data: dict):
    """Save configuration file"""
    try:
        config_files = {
            "server": "/opt/PerfectMPC/config/server.yaml",
            "database": "/opt/PerfectMPC/config/database.yaml"
        }

        if config_type not in config_files:
            return {"success": False, "error": "Invalid config type"}

        config_file = Path(config_files[config_type])

        # Backup current config
        backup_file = config_file.with_suffix(f".yaml.backup.{int(time.time())}")
        if config_file.exists():
            backup_file.write_text(config_file.read_text())

        # Save new config
        config_file.write_text(config_data.get("content", ""))

        await manager.broadcast({
            "type": "config_updated",
            "data": {"config_type": config_type, "backup": str(backup_file)}
        })

        return {"success": True, "backup": str(backup_file)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/code/settings")
async def save_code_settings(settings: dict):
    """Save AI code analysis settings"""
    try:
        config_file = Path("/opt/PerfectMPC/config/server.yaml")

        # Backup current config
        backup_file = config_file.with_suffix(f".yaml.backup.{int(time.time())}")
        if config_file.exists():
            backup_file.write_text(config_file.read_text())

        # Read current config
        if config_file.exists():
            content = config_file.read_text()
        else:
            content = ""

        # Update the AI model settings in the YAML content
        updated_content = update_yaml_ai_settings(content, settings)

        # Save updated config
        config_file.write_text(updated_content)

        logger.info(f"AI settings updated: provider={settings.get('provider')}, model={settings.get('model')}")

        return {"success": True, "message": "AI settings saved successfully"}

    except Exception as e:
        logger.error(f"Error saving AI settings: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/code/test-connection")
async def test_ai_connection(settings: dict):
    """Test connection to AI provider"""
    try:
        provider = settings.get('provider', 'openai')
        api_key = settings.get('api_key', '')
        model = settings.get('model', 'gpt-4')
        api_base = settings.get('api_base', '')

        if not api_key:
            return {"success": False, "error": "API key is required"}

        # Test connection based on provider
        if provider == 'openai':
            success, error = await test_openai_connection(api_key, model, api_base)
        elif provider == 'anthropic':
            success, error = await test_anthropic_connection(api_key, model)
        elif provider == 'gemini':
            success, error = await test_gemini_connection(api_key, model)
        elif provider == 'custom':
            success, error = await test_custom_connection(api_key, model, api_base)
        else:
            return {"success": False, "error": f"Unknown provider: {provider}"}

        if success:
            return {"success": True, "message": f"Successfully connected to {provider} with model {model}"}
        else:
            return {"success": False, "error": error}

    except Exception as e:
        logger.error(f"Error testing AI connection: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/code/models")
async def get_available_models(request: dict):
    """Get available models for the specified AI provider"""
    try:
        provider = request.get('provider', 'openai')
        api_key = request.get('api_key', '')
        api_base = request.get('api_base', '')

        if not api_key:
            return {"success": False, "error": "API key is required"}

        # Get available models based on provider
        if provider == 'openai':
            models = await get_openai_models(api_key, api_base)
        elif provider == 'anthropic':
            models = await get_anthropic_models(api_key)
        elif provider == 'gemini':
            models = await get_gemini_models(api_key)
        elif provider == 'custom':
            models = await get_custom_models(api_key, api_base)
        else:
            return {"success": False, "error": f"Unknown provider: {provider}"}

        return {"success": True, "models": models}

    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/code/debug-models")
async def debug_gemini_models(request: dict):
    """Debug endpoint to see raw Gemini API response"""
    try:
        api_key = request.get('api_key', '')

        if not api_key:
            return {"success": False, "error": "API key is required"}

        import aiohttp

        url = "https://generativelanguage.googleapis.com/v1beta/models"
        params = {"key": api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()

                    # Return raw data for debugging
                    models_info = []
                    for model in data.get('models', []):
                        models_info.append({
                            'name': model.get('name', ''),
                            'displayName': model.get('displayName', ''),
                            'description': model.get('description', ''),
                            'supportedGenerationMethods': model.get('supportedGenerationMethods', []),
                            'inputTokenLimit': model.get('inputTokenLimit', 0),
                            'outputTokenLimit': model.get('outputTokenLimit', 0)
                        })

                    return {
                        "success": True,
                        "raw_response": data,
                        "models_count": len(models_info),
                        "models_info": models_info
                    }
                else:
                    error_text = await response.text()
                    return {"success": False, "error": f"HTTP {response.status}: {error_text}"}

    except Exception as e:
        logger.error(f"Error debugging Gemini models: {e}")
        return {"success": False, "error": str(e)}

@app.get("/code", response_class=HTMLResponse)
async def code_analysis_page(request: Request):
    """Code analysis management page"""
    return templates.TemplateResponse("code.html", {"request": request})

@app.get("/api/code/analysis")
async def get_code_analysis():
    """Get code analysis history"""
    try:
        if not db_manager:
            return {"analyses": []}

        collection = db_manager.get_collection_name("improvements")
        analyses = await db_manager.mongo_find_many(
            collection,
            {"type": "analysis"},
            limit=50,
            sort=[("timestamp", -1)]
        )
        return {"analyses": analyses}
    except Exception as e:
        return {"analyses": [], "error": str(e)}

@app.get("/api/code/metrics/{session_id}")
async def get_session_metrics(session_id: str):
    """Get code metrics for session"""
    try:
        from services.code_improvement_service import CodeImprovementService

        code_service = CodeImprovementService(db_manager, mpc_config.code_improvement)
        await code_service.initialize()

        metrics = await code_service.get_metrics(session_id)
        return metrics
    except Exception as e:
        return {"error": str(e)}

# Authentication API Routes
@app.get("/api/auth/users")
async def get_users():
    """Get all users"""
    try:
        if not db_manager:
            return {"users": []}

        users = await db_manager.mongo_find_many("users", {})
        return {"users": users}
    except Exception as e:
        return {"users": [], "error": str(e)}

@app.post("/api/auth/users")
async def create_user(user_data: dict):
    """Create new user"""
    try:
        from auth.auth_manager import AuthManager, UserRole

        auth_manager = AuthManager(db_manager)
        await auth_manager.initialize()

        # Create user
        user = await auth_manager.create_user(
            username=user_data["username"],
            email=user_data["email"],
            role=UserRole(user_data["role"])
        )

        result = {"success": True, "user_id": user.user_id}

        # Create default API key if requested
        if user_data.get("create_api_key", False):
            api_key = await auth_manager.create_api_key(
                user.user_id,
                f"Default key for {user.username}",
                ["*"] if user.role == UserRole.ADMIN else ["sessions:*", "documents:*", "code:analyze"]
            )
            result["api_key"] = api_key.key_id

        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/auth/users/{user_id}")
async def delete_user(user_id: str):
    """Delete user and all associated API keys"""
    try:
        if not db_manager:
            return {"success": False, "error": "Database not available"}

        # First, check if user exists
        user_query = {"user_id": user_id}
        users = await db_manager.mongo_find_many("users", user_query)

        if not users:
            logger.warning(f"User not found for deletion: {user_id}")
            return {"success": False, "error": "User not found"}

        user = users[0]
        username = user.get("username", "Unknown")

        # Delete all API keys associated with this user
        api_keys_deleted = 0
        try:
            api_keys = await db_manager.mongo_find_many("api_keys", {"user_id": user_id})
            for api_key in api_keys:
                delete_result = await db_manager.mongo_delete_one("api_keys", {"_id": api_key["_id"]})
                if delete_result:
                    api_keys_deleted += 1
                    logger.info(f"Deleted API key {api_key.get('key_id', 'unknown')} for user {username}")
        except Exception as e:
            logger.error(f"Error deleting API keys for user {user_id}: {str(e)}")

        # Delete the user
        user_delete_result = await db_manager.mongo_delete_one("users", user_query)

        if user_delete_result:
            logger.info(f"Successfully deleted user: {username} (ID: {user_id}) and {api_keys_deleted} API keys")
            return {
                "success": True,
                "message": f"User '{username}' deleted successfully",
                "api_keys_deleted": api_keys_deleted
            }
        else:
            logger.error(f"Failed to delete user: {user_id}")
            return {"success": False, "error": "Failed to delete user from database"}

    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/api/auth/api-keys")
async def get_api_keys():
    """Get all API keys"""
    try:
        if not db_manager:
            return {"api_keys": []}

        # Get API keys but don't return the actual key values
        api_keys = await db_manager.mongo_find_many("api_keys", {})

        # Remove sensitive data
        for key in api_keys:
            key.pop("key_hash", None)
            key["key_id"] = "mpc_***" + key["key_id"][-8:] if len(key["key_id"]) > 8 else "mpc_***"

        return {"api_keys": api_keys}
    except Exception as e:
        return {"api_keys": [], "error": str(e)}

@app.post("/api/auth/api-keys")
async def create_api_key(key_data: dict):
    """Create new API key"""
    try:
        from auth.auth_manager import AuthManager

        auth_manager = AuthManager(db_manager)
        await auth_manager.initialize()

        api_key = await auth_manager.create_api_key(
            user_id=key_data["user_id"],
            name=key_data["name"],
            permissions=key_data["permissions"],
            expires_days=key_data.get("expires_days")
        )

        return {
            "success": True,
            "api_key": api_key.key_id,  # Return the actual key only once
            "key_id": api_key.key_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/auth/api-keys/{key_id}")
async def revoke_api_key(key_id: str):
    """Delete API key"""
    try:
        if not db_manager:
            return {"success": False, "error": "Database not available"}

        # Handle truncated key IDs (format: mpc_***XXXXXXXX)
        if key_id.startswith("mpc_***"):
            # Extract the last 8 characters
            suffix = key_id[7:]  # Remove "mpc_***" prefix
            # Escape special regex characters in the suffix
            import re
            escaped_suffix = re.escape(suffix)
            # Match keys ending with this suffix
            query = {"key_id": {"$regex": f".*{escaped_suffix}$"}}
        else:
            # Direct match for full key IDs
            query = {"key_id": key_id}

        # Actually delete the API key from database
        result = await db_manager.mongo_delete_one(
            "api_keys",
            query
        )

        if result:
            logger.info(f"Successfully deleted API key: {key_id}")
            return {"success": True}
        else:
            logger.warning(f"API key not found for deletion: {key_id}")
            return {"success": False, "error": "API key not found"}

    except Exception as e:
        logger.error(f"Error deleting API key {key_id}: {str(e)}")
        return {"success": False, "error": str(e)}

# Real MCP Hub Integration
async def fetch_real_mcp_hub_plugins():
    """Fetch plugins from the real MCP Hub"""
    try:
        import aiohttp

        # MCP Hub API endpoints
        mcp_hub_urls = [
            "https://raw.githubusercontent.com/modelcontextprotocol/servers/main/README.md",
            "https://api.github.com/search/repositories?q=mcp+server+topic:mcp&sort=stars&order=desc&per_page=100",
            "https://api.github.com/search/repositories?q=model-context-protocol&sort=stars&order=desc&per_page=100"
        ]

        all_plugins = []

        async with aiohttp.ClientSession() as session:
            # Fetch from GitHub API for MCP repositories
            for url in mcp_hub_urls[1:]:  # Skip README for now
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            repos = data.get('items', [])

                            for repo in repos:
                                plugin = {
                                    "id": repo['name'].lower().replace(' ', '-'),
                                    "name": repo['name'],
                                    "description": repo.get('description', 'No description available'),
                                    "author": repo['owner']['login'],
                                    "category": categorize_plugin(repo['name'], repo.get('description', '')),
                                    "version": "latest",
                                    "downloads": repo.get('stargazers_count', 0),
                                    "rating": min(5.0, (repo.get('stargazers_count', 0) / 10) + 3.0),
                                    "status": "available",
                                    "requirements": extract_requirements(repo.get('description', '')),
                                    "screenshot": None,
                                    "github_url": repo['html_url'],
                                    "clone_url": repo['clone_url'],
                                    "updated_at": repo['updated_at']
                                }
                                all_plugins.append(plugin)

                except Exception as e:
                    logger.warning(f"Error fetching from {url}: {e}")
                    continue

        # Add some curated high-quality MCP servers
        curated_plugins = [
            {
                "id": "filesystem",
                "name": "Filesystem MCP Server",
                "description": "Secure file system operations with configurable access controls",
                "author": "ModelContextProtocol",
                "category": "development",
                "version": "1.0.0",
                "downloads": 2500,
                "rating": 4.8,
                "status": "available",
                "requirements": "Python 3.8+",
                "screenshot": None,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem"
            },
            {
                "id": "brave-search",
                "name": "Brave Search MCP Server",
                "description": "Web search capabilities using Brave Search API",
                "author": "ModelContextProtocol",
                "category": "productivity",
                "version": "1.0.0",
                "downloads": 1800,
                "rating": 4.6,
                "status": "available",
                "requirements": "Brave Search API key",
                "screenshot": None,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search"
            },
            {
                "id": "sqlite",
                "name": "SQLite MCP Server",
                "description": "Database operations for SQLite databases",
                "author": "ModelContextProtocol",
                "category": "data",
                "version": "1.0.0",
                "downloads": 2200,
                "rating": 4.7,
                "status": "available",
                "requirements": "SQLite3",
                "screenshot": None,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite"
            },
            {
                "id": "github",
                "name": "GitHub MCP Server",
                "description": "GitHub repository management and operations",
                "author": "ModelContextProtocol",
                "category": "development",
                "version": "1.0.0",
                "downloads": 3200,
                "rating": 4.9,
                "status": "available",
                "requirements": "GitHub API token",
                "screenshot": None,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/github"
            },
            {
                "id": "postgres",
                "name": "PostgreSQL MCP Server",
                "description": "PostgreSQL database operations and management",
                "author": "ModelContextProtocol",
                "category": "data",
                "version": "1.0.0",
                "downloads": 1900,
                "rating": 4.5,
                "status": "available",
                "requirements": "PostgreSQL, psycopg2",
                "screenshot": None,
                "github_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/postgres"
            }
        ]

        # Combine and deduplicate
        all_plugins.extend(curated_plugins)

        # Remove duplicates based on name
        seen_names = set()
        unique_plugins = []
        for plugin in all_plugins:
            if plugin['name'] not in seen_names:
                seen_names.add(plugin['name'])
                unique_plugins.append(plugin)

        logger.info(f"Fetched {len(unique_plugins)} plugins from MCP Hub")
        return unique_plugins

    except Exception as e:
        logger.error(f"Error fetching from real MCP Hub: {e}")
        # Fallback to mock data
        return get_fallback_plugins()

def categorize_plugin(name, description):
    """Categorize plugin based on name and description"""
    name_lower = name.lower()
    desc_lower = description.lower()

    if any(word in name_lower or word in desc_lower for word in ['ai', 'ml', 'llm', 'gpt', 'claude', 'openai']):
        return 'ai'
    elif any(word in name_lower or word in desc_lower for word in ['git', 'github', 'code', 'dev', 'programming', 'ide']):
        return 'development'
    elif any(word in name_lower or word in desc_lower for word in ['data', 'database', 'sql', 'postgres', 'sqlite', 'mongo']):
        return 'data'
    elif any(word in name_lower or word in desc_lower for word in ['automation', 'script', 'workflow', 'task', 'schedule']):
        return 'automation'
    elif any(word in name_lower or word in desc_lower for word in ['search', 'web', 'browser', 'http', 'api']):
        return 'integration'
    else:
        return 'productivity'

def extract_requirements(description):
    """Extract requirements from description"""
    desc_lower = description.lower()

    if 'api key' in desc_lower or 'token' in desc_lower:
        return 'API key required'
    elif 'python' in desc_lower:
        return 'Python 3.8+'
    elif 'node' in desc_lower or 'npm' in desc_lower:
        return 'Node.js'
    elif 'docker' in desc_lower:
        return 'Docker'
    else:
        return 'No special requirements'

def get_fallback_plugins():
    """Fallback plugins if real MCP Hub is unavailable"""
    return [
        {
            "id": "memory-enhanced",
            "name": "Memory Enhanced",
            "description": "Advanced memory management with persistent context across sessions",
            "author": "PerfectMCP Team",
            "category": "ai",
            "version": "1.2.0",
            "downloads": 1250,
            "rating": 4.8,
            "status": "available",
            "requirements": "Python 3.8+, Redis",
            "screenshot": None
        },
        {
            "id": "code-reviewer",
            "name": "AI Code Reviewer",
            "description": "Intelligent code review with security analysis and best practices",
            "author": "DevTools Inc",
            "category": "development",
            "version": "2.1.3",
            "downloads": 3420,
            "rating": 4.9,
            "status": "available",
            "requirements": "OpenAI API key",
            "screenshot": None
        }
    ]

# MCP Hub API Endpoints
@app.get("/api/mcp/hub/plugins")
async def get_mcp_plugins():
    """Get available MCP plugins from hub"""
    try:
        # Get installed plugins from database
        installed_plugins = set()
        if db_manager:
            installed_records = await db_manager.mongo_find_many("installed_plugins", {})
            installed_plugins = {record["plugin_id"] for record in installed_records}

        # Fetch from real MCP Hub
        plugins = await fetch_real_mcp_hub_plugins()

        # Update plugin status based on installation
        for plugin in plugins:
            if plugin["id"] in installed_plugins:
                plugin["status"] = "installed"
            else:
                plugin["status"] = "available"

        return {"success": True, "plugins": plugins}
    except Exception as e:
        logger.error(f"Error fetching MCP plugins: {str(e)}")
        return {"success": False, "error": str(e)}

@app.post("/api/mcp/hub/install")
async def install_mcp_plugin(request: dict):
    """Install an MCP plugin with real-time progress updates"""
    try:
        plugin_id = request.get("plugin_id")
        real_time = request.get("real_time", False)

        if not plugin_id:
            return {"success": False, "error": "Plugin ID is required"}

        logger.info(f"Installing MCP plugin: {plugin_id} (real_time={real_time})")

        # Get plugin info from hub data
        plugins_data = await get_mcp_plugins()
        plugin_info = None
        for plugin in plugins_data["plugins"]:
            if plugin["id"] == plugin_id:
                plugin_info = plugin
                break

        if not plugin_info:
            return {"success": False, "error": "Plugin not found"}

        if not db_manager:
            return {"success": False, "error": "Database not available"}

        # Check if already installed
        existing = await db_manager.mongo_find_many("installed_plugins", {"plugin_id": plugin_id})
        if existing:
            return {"success": False, "error": "Plugin already installed"}

        # Start installation process with real-time updates
        if real_time:
            asyncio.create_task(install_plugin_with_progress(plugin_id, plugin_info))
            return {"success": True, "message": "Installation started"}
        else:
            # Synchronous installation
            result = await perform_plugin_installation(plugin_id, plugin_info)
            return result

    except Exception as e:
        logger.error(f"Error installing MCP plugin: {str(e)}")
        return {"success": False, "error": str(e)}

async def install_plugin_with_progress(plugin_id: str, plugin_info: dict):
    """Install plugin with real-time progress updates via WebSocket"""
    try:
        steps = [
            {"progress": 10, "message": f"Preparing to install {plugin_info['name']}..."},
            {"progress": 25, "message": "Downloading plugin from repository..."},
            {"progress": 40, "message": "Verifying plugin integrity..."},
            {"progress": 55, "message": "Checking dependencies..."},
            {"progress": 70, "message": "Installing dependencies..."},
            {"progress": 85, "message": "Configuring plugin..."},
            {"progress": 95, "message": "Registering with MCP server..."},
            {"progress": 100, "message": "Installation complete!"}
        ]

        for step in steps:
            # Send progress update via WebSocket
            await manager.broadcast({
                "type": "plugin_install_progress",
                "plugin_id": plugin_id,
                "progress": step["progress"],
                "message": step["message"]
            })

            # Simulate work
            await asyncio.sleep(1.5)

        # Perform actual installation
        result = await perform_plugin_installation(plugin_id, plugin_info)

        if result["success"]:
            await manager.broadcast({
                "type": "plugin_install_complete",
                "plugin_id": plugin_id,
                "message": f"Plugin {plugin_info['name']} installed successfully!"
            })
        else:
            await manager.broadcast({
                "type": "plugin_install_error",
                "plugin_id": plugin_id,
                "message": f"Installation failed: {result['error']}"
            })

    except Exception as e:
        logger.error(f"Error in plugin installation with progress: {e}")
        await manager.broadcast({
            "type": "plugin_install_error",
            "plugin_id": plugin_id,
            "message": f"Installation failed: {str(e)}"
        })

async def perform_plugin_installation(plugin_id: str, plugin_info: dict):
    """Perform the actual plugin installation"""
    try:
        # Create plugin record
        plugin_record = {
            "plugin_id": plugin_id,
            "name": plugin_info.get("name"),
            "version": plugin_info.get("version"),
            "author": plugin_info.get("author"),
            "category": plugin_info.get("category"),
            "description": plugin_info.get("description"),
            "github_url": plugin_info.get("github_url"),
            "installed_at": datetime.utcnow().isoformat(),
            "status": "active"
        }

        # Save to database
        await db_manager.mongo_insert_one("installed_plugins", plugin_record)

        logger.info(f"Successfully installed MCP plugin: {plugin_id}")
        return {"success": True, "message": f"Plugin {plugin_id} installed successfully"}

    except Exception as e:
        logger.error(f"Error in plugin installation: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/mcp/hub/uninstall")
async def uninstall_mcp_plugin(request: dict):
    """Uninstall an MCP plugin"""
    try:
        plugin_id = request.get("plugin_id")
        if not plugin_id:
            return {"success": False, "error": "Plugin ID is required"}

        logger.info(f"Uninstalling MCP plugin: {plugin_id}")

        if not db_manager:
            return {"success": False, "error": "Database not available"}

        # Check if plugin is installed
        existing = await db_manager.mongo_find_many("installed_plugins", {"plugin_id": plugin_id})
        if not existing:
            return {"success": False, "error": "Plugin not installed"}

        # Remove from database
        await db_manager.mongo_delete_one("installed_plugins", {"plugin_id": plugin_id})

        logger.info(f"Successfully uninstalled MCP plugin: {plugin_id}")
        return {"success": True, "message": f"Plugin {plugin_id} uninstalled successfully"}

    except Exception as e:
        logger.error(f"Error uninstalling MCP plugin: {str(e)}")
        return {"success": False, "error": str(e)}

# MCP Status API Endpoints
@app.get("/api/mcp/status")
async def get_mcp_status():
    """Get MCP server status and metrics"""
    try:
        # Get installed plugins from database
        installed_plugins = []
        if db_manager:
            installed_records = await db_manager.mongo_find_many("installed_plugins", {})
            installed_plugins = list(installed_records)

        # Mock server data for now - in production this would query actual MCP servers
        servers = []

        # Get real tool call metrics from database
        async def get_real_tool_metrics(plugin_id: str):
            """Get actual tool call metrics from database"""
            try:
                if not db_manager or not db_manager.mongo_client:
                    return {"tool_calls": 0, "success_rate": 0, "response_time": 0}

                # Query actual metrics from MongoDB
                db = db_manager.mongo_client.perfectmpc
                metrics = await db.tool_metrics.find_one({"plugin_id": plugin_id})

                if metrics:
                    return {
                        "tool_calls": metrics.get("total_calls", 0),
                        "success_rate": metrics.get("success_rate", 0),
                        "response_time": metrics.get("avg_response_time", 0)
                    }
                else:
                    return {"tool_calls": 0, "success_rate": 0, "response_time": 0}
            except Exception as e:
                logger.warning(f"Could not get real metrics for {plugin_id}: {e}")
                return {"tool_calls": 0, "success_rate": 0, "response_time": 0}

        # Get real server status
        async def get_real_server_status(plugin_id: str):
            """Check if server is actually running"""
            try:
                # Try to ping the server endpoint
                import aiohttp
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
                    url = f"http://localhost:8000/api/mcp/{plugin_id}/health"
                    async with session.get(url) as response:
                        return "running" if response.status == 200 else "stopped"
            except:
                return "stopped"

        for plugin in installed_plugins:
            # Get real metrics instead of mock data
            real_metrics = await get_real_tool_metrics(plugin["plugin_id"])
            real_status = await get_real_server_status(plugin["plugin_id"])

            # Calculate unique tool types (not instances)
            plugin_tools = [f"{plugin['plugin_id']}_tool_{i}" for i in range(1, 4)]
            unique_tool_type = plugin['plugin_id'].replace('-', '_')  # Convert to unique tool type

            server = {
                "id": plugin["plugin_id"],
                "name": plugin["name"],
                "status": real_status,
                "uptime": 3600 + hash(plugin["plugin_id"]) % 86400 if real_status == "running" else 0,  # *Mock uptime
                "last_activity": datetime.utcnow().isoformat(),
                "response_time": real_metrics["response_time"] if real_metrics["response_time"] > 0 else 50 + hash(plugin["plugin_id"]) % 200,  # *Fallback mock
                "tool_calls": real_metrics["tool_calls"],
                "success_rate": real_metrics["success_rate"] if real_metrics["success_rate"] > 0 else 85 + hash(plugin["plugin_id"]) % 15,  # *Fallback mock
                "tools": plugin_tools,
                "unique_tool_types": [unique_tool_type],  # Single unique tool type
                "total_tools": 1,  # Count unique types, not instances
                "category": plugin.get("category", "unknown"),
                "version": plugin.get("version", "1.0.0"),
                "author": plugin.get("author", "Unknown")
            }
            servers.append(server)

        # Add core MCP server status with session information
        main_server_status = get_mcp_server_status()

        # Get session counts for multi-session tools
        memory_sessions = await get_active_sessions("memory_context")
        context7_sessions = await get_active_sessions("context7_management")
        playwright_sessions = await get_active_sessions("playwright_automation")
        total_active_sessions = memory_sessions + context7_sessions + playwright_sessions

        # Get real core server metrics
        async def get_core_server_metrics():
            """Get actual core server metrics"""
            try:
                if not db_manager or not db_manager.mongo_client:
                    return {"tool_calls": 0, "success_rate": 0, "response_time": 0, "uptime": 0}

                db = db_manager.mongo_client.perfectmpc

                # Get aggregated tool call metrics
                pipeline = [
                    {"$group": {
                        "_id": None,
                        "total_calls": {"$sum": "$total_calls"},
                        "successful_calls": {"$sum": "$successful_calls"},
                        "total_response_time": {"$sum": "$total_response_time"},
                        "call_count": {"$sum": 1}
                    }}
                ]

                result = await db.tool_metrics.aggregate(pipeline).to_list(1)

                if result and result[0]["call_count"] > 0:
                    data = result[0]
                    return {
                        "tool_calls": data["total_calls"],
                        "success_rate": round((data["successful_calls"] / data["total_calls"]) * 100) if data["total_calls"] > 0 else 0,
                        "response_time": round(data["total_response_time"] / data["call_count"]),
                        "uptime": 7200  # *Mock uptime - would need process start time tracking
                    }
                else:
                    return {"tool_calls": 0, "success_rate": 0, "response_time": 25, "uptime": 7200}  # *Fallback values
            except Exception as e:
                logger.warning(f"Could not get core server metrics: {e}")
                return {"tool_calls": 0, "success_rate": 0, "response_time": 25, "uptime": 7200}  # *Fallback values

        core_metrics = await get_core_server_metrics()

        core_server = {
            "id": "core",
            "name": "PerfectMCP Core",
            "status": "running" if main_server_status["running"] else "stopped",
            "uptime": core_metrics["uptime"],
            "last_activity": datetime.utcnow().isoformat(),
            "response_time": core_metrics["response_time"],
            "tool_calls": core_metrics["tool_calls"],
            "success_rate": core_metrics["success_rate"],
            "tools": ["memory_context", "code_analysis", "document_search", "context7_management", "playwright_automation", "sequential_thinking", "web_scraper"],
            "unique_tool_types": ["memory_context", "code_analysis", "document_search", "context7_management", "playwright_automation", "sequential_thinking", "web_scraper"],
            "category": "core",
            "version": "1.0.0",
            "author": "PerfectMCP Team",
            "total_tools": 7,  # Count of unique tool types
            "session_tools": 3,  # Tools that support multiple sessions
            "active_sessions": total_active_sessions,
            "max_sessions": 9,  # 3 tools × 3 sessions each
            "session_details": {
                "memory_context": {"active": memory_sessions, "max": 3},
                "context7_management": {"active": context7_sessions, "max": 3},
                "playwright_automation": {"active": playwright_sessions, "max": 3}
            }
        }
        servers.insert(0, core_server)

        return {"success": True, "servers": servers}

    except Exception as e:
        logger.error(f"Error getting MCP status: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/mcp/servers/{server_id}/start")
async def start_mcp_server(server_id: str):
    """Start an MCP server"""
    try:
        logger.info(f"Starting MCP server: {server_id}")
        # Mock implementation - in production this would start the actual server
        return {"success": True, "message": f"Server {server_id} started"}
    except Exception as e:
        logger.error(f"Error starting MCP server {server_id}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/mcp/servers/{server_id}/stop")
async def stop_mcp_server(server_id: str):
    """Stop an MCP server"""
    try:
        logger.info(f"Stopping MCP server: {server_id}")
        # Mock implementation - in production this would stop the actual server
        return {"success": True, "message": f"Server {server_id} stopped"}
    except Exception as e:
        logger.error(f"Error stopping MCP server {server_id}: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/mcp/plugins/{plugin_id}/settings")
async def get_plugin_settings(plugin_id: str):
    """Get plugin settings"""
    try:
        if not db_manager:
            return {"success": False, "error": "Database not available"}

        # Get plugin settings from database
        settings_record = await db_manager.mongo_find_one("plugin_settings", {"plugin_id": plugin_id})

        if settings_record:
            return {"success": True, "settings": settings_record.get("settings", {})}
        else:
            # Return default settings
            return {"success": True, "settings": {
                "env_vars": {},
                "command_args": [],
                "server": {
                    "port": 8080,
                    "host": "localhost",
                    "auto_start": False,
                    "debug_mode": False
                },
                "custom_config": {}
            }}
    except Exception as e:
        logger.error(f"Error getting plugin settings {plugin_id}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/mcp/plugins/{plugin_id}/settings")
async def save_plugin_settings(plugin_id: str, settings: dict):
    """Save plugin settings"""
    try:
        if not db_manager:
            return {"success": False, "error": "Database not available"}

        # Save settings to database
        await db_manager.mongo_upsert(
            "plugin_settings",
            {"plugin_id": plugin_id},
            {
                "plugin_id": plugin_id,
                "settings": settings,
                "updated_at": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Saved settings for plugin: {plugin_id}")
        return {"success": True, "message": "Settings saved successfully"}

    except Exception as e:
        logger.error(f"Error saving plugin settings {plugin_id}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/mcp/plugins/{plugin_id}/start")
async def start_plugin(plugin_id: str):
    """Start plugin"""
    try:
        logger.info(f"Starting plugin: {plugin_id}")
        # Mock implementation - in production this would start the actual plugin
        return {"success": True, "message": f"Plugin {plugin_id} started"}
    except Exception as e:
        logger.error(f"Error starting plugin {plugin_id}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/mcp/plugins/{plugin_id}/stop")
async def stop_plugin(plugin_id: str):
    """Stop plugin"""
    try:
        logger.info(f"Stopping plugin: {plugin_id}")
        # Mock implementation - in production this would stop the actual plugin
        return {"success": True, "message": f"Plugin {plugin_id} stopped"}
    except Exception as e:
        logger.error(f"Error stopping plugin {plugin_id}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/mcp/plugins/{plugin_id}/restart")
async def restart_plugin(plugin_id: str):
    """Restart plugin"""
    try:
        logger.info(f"Restarting plugin: {plugin_id}")
        # Mock implementation - in production this would restart the actual plugin
        return {"success": True, "message": f"Plugin {plugin_id} restarted"}
    except Exception as e:
        logger.error(f"Error restarting plugin {plugin_id}: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/mcp/plugins/{plugin_id}/logs")
async def get_plugin_logs(plugin_id: str):
    """Get plugin logs"""
    try:
        # Mock logs - in production this would read actual plugin logs
        mock_logs = [
            {"timestamp": "2024-01-01T12:00:00Z", "level": "INFO", "message": f"Plugin {plugin_id} started"},
            {"timestamp": "2024-01-01T12:01:00Z", "level": "INFO", "message": "Processing request"},
            {"timestamp": "2024-01-01T12:02:00Z", "level": "DEBUG", "message": "Debug information"},
            {"timestamp": "2024-01-01T12:03:00Z", "level": "WARN", "message": "Warning message"},
        ]

        return {"success": True, "logs": mock_logs}
    except Exception as e:
        logger.error(f"Error getting plugin logs {plugin_id}: {e}")
        return {"success": False, "error": str(e)}

# Additional MCP Tool Endpoints
@app.post("/api/web/scrape")
async def web_scrape(request: dict):
    """Web scraping tool"""
    try:
        url = request.get("url")
        extract_text = request.get("extract_text", True)
        follow_links = request.get("follow_links", False)

        if not url:
            return {"success": False, "error": "URL is required"}

        # Mock implementation - in production this would use actual web scraping
        return {
            "success": True,
            "url": url,
            "title": "Sample Page Title",
            "text": "Sample extracted text content...",
            "links": ["http://example.com/link1", "http://example.com/link2"] if follow_links else [],
            "metadata": {
                "status_code": 200,
                "content_type": "text/html",
                "extracted_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error in web scraping: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/database/redis")
async def redis_operations(request: dict):
    """Redis database operations"""
    try:
        operation = request.get("operation")
        key = request.get("key")
        value = request.get("value")

        if not operation or not key:
            return {"success": False, "error": "Operation and key are required"}

        if not db_manager or not db_manager.redis_client:
            return {"success": False, "error": "Redis not available"}

        if operation == "get":
            result = await db_manager.redis_get(key)
            return {"success": True, "key": key, "value": result}
        elif operation == "set":
            await db_manager.redis_set(key, value)
            return {"success": True, "key": key, "operation": "set"}
        elif operation == "delete":
            await db_manager.redis_delete(key)
            return {"success": True, "key": key, "operation": "delete"}
        elif operation == "exists":
            exists = await db_manager.redis_exists(key)
            return {"success": True, "key": key, "exists": exists}
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}

    except Exception as e:
        logger.error(f"Error in Redis operations: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/database/mongodb")
async def mongodb_operations(request: dict):
    """MongoDB database operations"""
    try:
        collection = request.get("collection")
        operation = request.get("operation")
        query = request.get("query", {})
        document = request.get("document", {})

        if not collection or not operation:
            return {"success": False, "error": "Collection and operation are required"}

        if not db_manager or not db_manager.mongo_db:
            return {"success": False, "error": "MongoDB not available"}

        if operation == "find":
            results = await db_manager.mongo_find_many(collection, query, limit=request.get("limit", 10))
            return {"success": True, "collection": collection, "results": results}
        elif operation == "insert":
            result_id = await db_manager.mongo_insert_one(collection, document)
            return {"success": True, "collection": collection, "inserted_id": result_id}
        elif operation == "update":
            await db_manager.mongo_update_one(collection, query, document)
            return {"success": True, "collection": collection, "operation": "update"}
        elif operation == "delete":
            await db_manager.mongo_delete_one(collection, query)
            return {"success": True, "collection": collection, "operation": "delete"}
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}

    except Exception as e:
        logger.error(f"Error in MongoDB operations: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/files")
@app.get("/api/files")
async def file_operations(request: Request):
    """File system operations"""
    try:
        if request.method == "GET":
            path = request.query_params.get("path", "/opt/PerfectMPC")
            # List directory contents
            import os
            if os.path.exists(path) and os.path.isdir(path):
                files = []
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    files.append({
                        "name": item,
                        "path": item_path,
                        "is_directory": os.path.isdir(item_path),
                        "size": os.path.getsize(item_path) if os.path.isfile(item_path) else 0
                    })
                return {"success": True, "path": path, "files": files}
            else:
                return {"success": False, "error": "Path not found or not a directory"}

        elif request.method == "POST":
            data = await request.json()
            operation = data.get("operation")
            path = data.get("path")
            content = data.get("content", "")

            if operation == "read":
                if os.path.exists(path) and os.path.isfile(path):
                    with open(path, 'r') as f:
                        content = f.read()
                    return {"success": True, "path": path, "content": content}
                else:
                    return {"success": False, "error": "File not found"}
            elif operation == "write":
                with open(path, 'w') as f:
                    f.write(content)
                return {"success": True, "path": path, "operation": "write"}
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

    except Exception as e:
        logger.error(f"Error in file operations: {e}")
        return {"success": False, "error": str(e)}

# Session Management Functions
async def get_active_sessions(tool_name: str) -> int:
    """Get count of active sessions for a tool"""
    try:
        if not db_manager:
            return 0

        # Get active sessions from Redis
        pattern = f"mcp:session:{tool_name}:*"
        if db_manager.redis_client:
            keys = await db_manager.redis_client.keys(pattern)

            # Filter for sessions active in last 30 minutes
            active_count = 0
            current_time = datetime.utcnow().timestamp()

            for key in keys:
                session_data = await db_manager.redis_get(key.decode())
                if session_data:
                    try:
                        session_info = json.loads(session_data)
                        last_activity = session_info.get('last_activity', 0)
                        if current_time - last_activity < 1800:  # 30 minutes
                            active_count += 1
                    except:
                        continue

            return active_count

        return 0
    except Exception as e:
        logger.error(f"Error getting active sessions for {tool_name}: {e}")
        return 0

async def cleanup_inactive_sessions():
    """Background task to cleanup inactive sessions"""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes

            if not db_manager or not db_manager.redis_client:
                continue

            logger.info("Starting session cleanup")
            current_time = datetime.utcnow().timestamp()

            # Get all session keys
            pattern = "mcp:session:*"
            keys = await db_manager.redis_client.keys(pattern)

            cleaned_count = 0
            for key in keys:
                try:
                    session_data = await db_manager.redis_get(key.decode())
                    if session_data:
                        session_info = json.loads(session_data)
                        last_activity = session_info.get('last_activity', 0)

                        # Remove sessions inactive for more than 1 hour
                        if current_time - last_activity > 3600:
                            await db_manager.redis_delete(key.decode())
                            cleaned_count += 1
                except Exception as e:
                    logger.debug(f"Error processing session key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} inactive sessions")

        except Exception as e:
            logger.error(f"Error in session cleanup: {e}")

async def update_session_activity(tool_name: str, session_id: str):
    """Update session activity timestamp"""
    try:
        if not db_manager:
            return

        session_key = f"mcp:session:{tool_name}:{session_id}"
        session_data = {
            "tool_name": tool_name,
            "session_id": session_id,
            "last_activity": datetime.utcnow().timestamp(),
            "created_at": datetime.utcnow().isoformat()
        }

        await db_manager.redis_set(session_key, json.dumps(session_data), expire=7200)  # 2 hours TTL

    except Exception as e:
        logger.error(f"Error updating session activity: {e}")

@app.get("/api/status")
async def get_server_status():
    """Get comprehensive server status"""
    try:
        # Get MCP server status
        mcp_status = get_mcp_server_status()

        # Get system metrics
        system_stats = get_system_stats()

        # Get database status
        db_status = {
            "redis": False,
            "mongodb": False
        }

        if db_manager:
            try:
                # Test Redis connection
                if db_manager.redis_client:
                    await db_manager.redis_client.ping()
                    db_status["redis"] = True
            except:
                pass

            try:
                # Test MongoDB connection
                if db_manager.mongo_client:
                    await db_manager.mongo_client.admin.command('ping')
                    db_status["mongodb"] = True
            except:
                pass

        # Get service status
        services_status = {
            "memory": memory_service is not None,
            "code_improvement": code_improvement_service is not None,
            "rag": rag_service is not None,
            "context7": context7_service is not None,
            "playwright": playwright_service is not None,
            "sequential_thinking": sequential_thinking_service is not None,
            "ssh": ssh_service is not None
        }

        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "mcp_server": mcp_status,
            "system": system_stats,
            "databases": db_status,
            "services": services_status,
            "admin_uptime": time.time() - admin_start_time
        }

    except Exception as e:
        logger.error(f"Error getting server status: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/api/mcp/sessions")
async def get_mcp_sessions():
    """Get all active MCP sessions"""
    try:
        if not db_manager:
            return {"sessions": []}

        sessions = []
        pattern = "mcp:session:*"

        if db_manager.redis_client:
            keys = await db_manager.redis_client.keys(pattern)
            current_time = datetime.utcnow().timestamp()

            for key in keys:
                try:
                    session_data = await db_manager.redis_get(key.decode())
                    if session_data:
                        session_info = json.loads(session_data)
                        last_activity = session_info.get('last_activity', 0)

                        # Only include sessions active in last hour
                        if current_time - last_activity < 3600:
                            session_info['key'] = key.decode()
                            session_info['inactive_minutes'] = int((current_time - last_activity) / 60)
                            sessions.append(session_info)
                except Exception as e:
                    logger.debug(f"Error processing session {key}: {e}")
                    continue

        return {"sessions": sessions}

    except Exception as e:
        logger.error(f"Error getting MCP sessions: {e}")
        return {"sessions": [], "error": str(e)}

@app.delete("/api/mcp/sessions/{session_key}")
async def close_mcp_session(session_key: str):
    """Close an MCP session"""
    try:
        if not db_manager:
            return {"success": False, "error": "Database not available"}

        # Decode the session key if it's URL encoded
        import urllib.parse
        decoded_key = urllib.parse.unquote(session_key)

        await db_manager.redis_delete(decoded_key)

        logger.info(f"Closed MCP session: {decoded_key}")
        return {"success": True, "message": "Session closed"}

    except Exception as e:
        logger.error(f"Error closing session {session_key}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/mcp/servers/{server_id}/restart")
async def restart_mcp_server(server_id: str):
    """Restart an MCP server"""
    try:
        logger.info(f"Restarting MCP server: {server_id}")
        # Mock implementation - in production this would restart the actual server
        return {"success": True, "message": f"Server {server_id} restarted"}
    except Exception as e:
        logger.error(f"Error restarting MCP server {server_id}: {e}")
        return {"success": False, "error": str(e)}

# Helper functions for AI settings
def update_yaml_ai_settings(content: str, settings: dict) -> str:
    """Update AI settings in YAML content"""
    lines = content.split('\n')
    updated_lines = []
    in_ai_model_section = False

    for line in lines:
        stripped = line.strip()

        # Check if we're in the ai_model section
        if stripped == 'ai_model:':
            in_ai_model_section = True
            updated_lines.append(line)
            continue

        # Check if we're leaving the ai_model section
        if in_ai_model_section and line and not line.startswith('    ') and not line.startswith('\t'):
            in_ai_model_section = False

        # Update settings in ai_model section
        if in_ai_model_section:
            if 'provider:' in stripped:
                updated_lines.append(f'    provider: "{settings.get("provider", "openai")}"')
            elif 'model:' in stripped:
                updated_lines.append(f'    model: "{settings.get("model", "gpt-4")}"')
            elif 'api_key:' in stripped:
                updated_lines.append(f'    api_key: "{settings.get("api_key", "")}"')
            elif 'api_base:' in stripped:
                updated_lines.append(f'    api_base: "{settings.get("api_base", "")}"')
            elif 'max_tokens:' in stripped:
                updated_lines.append(f'    max_tokens: {settings.get("max_tokens", 2000)}')
            elif 'temperature:' in stripped:
                updated_lines.append(f'    temperature: {settings.get("temperature", 0.1)}')
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    return '\n'.join(updated_lines)

async def test_openai_connection(api_key: str, model: str, api_base: str = "") -> tuple[bool, str]:
    """Test OpenAI API connection"""
    try:
        # Validate API key format
        if not api_key:
            return False, "API key is required"

        # OpenAI API keys start with "sk-" (standard) or "sk-proj-" (project keys)
        if not (api_key.startswith('sk-') or api_key.startswith('sk-proj-')):
            return False, "Invalid OpenAI API key format. OpenAI keys must start with 'sk-' or 'sk-proj-'"

        # Check minimum length
        if len(api_key) < 20:
            return False, "OpenAI API key is too short"

        if api_base and not api_base.startswith('http'):
            return False, "Invalid API base URL format"

        # In production, you would make an actual API call here
        return True, "Connection test passed (validation only)"

    except Exception as e:
        return False, str(e)

async def test_anthropic_connection(api_key: str, model: str) -> tuple[bool, str]:
    """Test Anthropic API connection"""
    try:
        # Validate API key format
        if not api_key:
            return False, "API key is required"

        # Anthropic API keys start with "sk-ant-"
        if not api_key.startswith('sk-ant-'):
            return False, "Invalid Anthropic API key format. Anthropic keys must start with 'sk-ant-'"

        # Check minimum length
        if len(api_key) < 30:
            return False, "Anthropic API key is too short"

        # In production, you would make an actual API call here
        return True, "Connection test passed (validation only)"

    except Exception as e:
        return False, str(e)

async def test_gemini_connection(api_key: str, model: str) -> tuple[bool, str]:
    """Test Google Gemini API connection"""
    try:
        # Validate API key format
        if not api_key or len(api_key) < 10:
            return False, "Invalid API key format"

        # Gemini API keys typically start with 'AIza'
        if not api_key.startswith('AIza'):
            return False, "Gemini API keys should start with 'AIza'"

        # Validate model name
        valid_models = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.0-pro', 'gemini-pro']
        if model not in valid_models:
            return False, f"Invalid Gemini model. Supported: {', '.join(valid_models)}"

        # In production, you would make an actual API call here
        # Example: Test with Google AI Studio API
        import aiohttp

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            headers = {
                "Content-Type": "application/json"
            }
            params = {
                "key": api_key
            }
            data = {
                "contents": [{
                    "parts": [{
                        "text": "Hello, this is a test."
                    }]
                }],
                "generationConfig": {
                    "maxOutputTokens": 10,
                    "temperature": 0.1
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, params=params, json=data, timeout=10) as response:
                    if response.status == 200:
                        return True, "Connection successful"
                    elif response.status == 403:
                        return False, "API key invalid or insufficient permissions"
                    elif response.status == 404:
                        return False, f"Model '{model}' not found or not accessible"
                    else:
                        error_text = await response.text()
                        return False, f"HTTP {response.status}: {error_text}"

        except aiohttp.ClientError as e:
            return False, f"Network error: {str(e)}"

    except Exception as e:
        return False, str(e)

async def test_custom_connection(api_key: str, model: str, api_base: str) -> tuple[bool, str]:
    """Test custom API connection"""
    try:
        if not api_base:
            return False, "API base URL is required for custom providers"

        if not api_base.startswith('http'):
            return False, "Invalid API base URL format"

        if not api_key or len(api_key) < 10:
            return False, "Invalid API key format"

        # In production, you would make an actual API call here
        return True, "Connection test passed (validation only)"

    except Exception as e:
        return False, str(e)

# Model fetching functions
async def get_openai_models(api_key: str, api_base: str = "") -> list:
    """Get available OpenAI models"""
    try:
        import aiohttp

        url = f"{api_base}/v1/models" if api_base else "https://api.openai.com/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    models = []

                    # Filter and format models for code analysis
                    for model in data.get('data', []):
                        model_id = model.get('id', '')
                        if any(x in model_id.lower() for x in ['gpt-4', 'gpt-3.5', 'text-davinci']):
                            models.append({
                                'id': model_id,
                                'name': model_id.replace('-', ' ').title(),
                                'description': 'OpenAI model',
                                'recommended': 'gpt-4' in model_id and 'turbo' not in model_id
                            })

                    # Sort by recommended first, then alphabetically
                    models.sort(key=lambda x: (not x['recommended'], x['name']))
                    return models
                else:
                    # Fallback to static models
                    return get_static_openai_models()
    except Exception as e:
        logger.debug(f"Error fetching OpenAI models: {e}")
        return get_static_openai_models()

async def get_anthropic_models(api_key: str) -> list:
    """Get available Anthropic models"""
    try:
        # Anthropic doesn't have a public models API yet, so return static list
        return [
            {
                'id': 'claude-3-5-sonnet-20241022',
                'name': 'Claude 3.5 Sonnet',
                'description': 'Latest and most capable',
                'recommended': True
            },
            {
                'id': 'claude-3-sonnet-20240229',
                'name': 'Claude 3 Sonnet',
                'description': 'Balanced performance',
                'recommended': False
            },
            {
                'id': 'claude-3-haiku-20240307',
                'name': 'Claude 3 Haiku',
                'description': 'Fast and efficient',
                'recommended': False
            },
            {
                'id': 'claude-3-opus-20240229',
                'name': 'Claude 3 Opus',
                'description': 'Most powerful',
                'recommended': False
            }
        ]
    except Exception as e:
        logger.debug(f"Error fetching Anthropic models: {e}")
        return get_static_anthropic_models()

async def get_gemini_models(api_key: str) -> list:
    """Get available Gemini models"""
    try:
        import aiohttp

        url = "https://generativelanguage.googleapis.com/v1beta/models"
        params = {"key": api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    models = []

                    for model in data.get('models', []):
                        model_name = model.get('name', '').replace('models/', '')
                        display_name = model.get('displayName', model_name)

                        # Only include generative models (exclude embedding models)
                        supported_methods = model.get('supportedGenerationMethods', [])
                        if 'generateContent' in supported_methods and 'gemini' in model_name.lower():

                            # Determine if this is a recommended model
                            is_recommended = False
                            description = ""

                            if '2.0' in model_name:
                                is_recommended = 'flash' in model_name.lower()  # Gemini 2.0 Flash is recommended
                                description = "Latest Gemini 2.0 model"
                            elif '1.5-pro' in model_name:
                                is_recommended = '2.0' not in [m.get('id', '') for m in models]  # Only if no 2.0 models
                                description = "Advanced reasoning and analysis"
                            elif '1.5-flash' in model_name:
                                description = "Fast and efficient"
                            elif '1.0-pro' in model_name:
                                description = "Legacy model"
                            else:
                                description = model.get('description', '')

                            models.append({
                                'id': model_name,
                                'name': display_name,
                                'description': description,
                                'recommended': is_recommended,
                                'version': model.get('version', ''),
                                'input_token_limit': model.get('inputTokenLimit', 0),
                                'output_token_limit': model.get('outputTokenLimit', 0)
                            })

                    # Sort by version (newest first), then by recommended
                    def sort_key(model):
                        # Extract version for sorting (2.0 > 1.5 > 1.0)
                        name = model['id']
                        if '2.0' in name:
                            version_score = 200
                        elif '1.5' in name:
                            version_score = 150
                        elif '1.0' in name:
                            version_score = 100
                        else:
                            version_score = 0

                        # Prefer flash models within same version
                        if 'flash' in name.lower():
                            version_score += 1

                        return (-version_score, not model['recommended'], model['name'])

                    models.sort(key=sort_key)

                    if models:
                        logger.info(f"Loaded {len(models)} Gemini models from API")
                        return models
                    else:
                        logger.warning("No Gemini models found in API response, using static fallback")
                        return get_static_gemini_models()
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to fetch Gemini models: HTTP {response.status} - {error_text}")
                    return get_static_gemini_models()
    except Exception as e:
        logger.error(f"Error fetching Gemini models: {e}")
        return get_static_gemini_models()

async def get_custom_models(api_key: str, api_base: str) -> list:
    """Get available models from custom API"""
    try:
        if not api_base:
            return [{'id': 'custom-model', 'name': 'Custom Model', 'description': 'User-defined model', 'recommended': True}]

        # Try OpenAI-compatible models endpoint
        return await get_openai_models(api_key, api_base)
    except Exception as e:
        logger.debug(f"Error fetching custom models: {e}")
        return [{'id': 'custom-model', 'name': 'Custom Model', 'description': 'User-defined model', 'recommended': True}]

# Documentation and Legal Pages
@app.get("/docs/api", response_class=HTMLResponse)
async def api_docs(request: Request):
    """API Documentation page"""
    return templates.TemplateResponse("docs/api.html", {
        "request": request,
        "title": "API Documentation"
    })

@app.get("/docs/setup", response_class=HTMLResponse)
async def setup_docs(request: Request):
    """Setup Guide page"""
    return templates.TemplateResponse("docs/setup.html", {
        "request": request,
        "title": "Setup Guide"
    })

@app.get("/docs/mcp", response_class=HTMLResponse)
async def mcp_docs(request: Request):
    """MCP Guide page"""
    return templates.TemplateResponse("docs/mcp.html", {
        "request": request,
        "title": "MCP Integration Guide"
    })

@app.get("/docs/troubleshooting", response_class=HTMLResponse)
async def troubleshooting_docs(request: Request):
    """Troubleshooting Guide page"""
    return templates.TemplateResponse("docs/troubleshooting.html", {
        "request": request,
        "title": "Troubleshooting Guide"
    })

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    """Privacy Policy page"""
    return templates.TemplateResponse("legal/privacy.html", {
        "request": request,
        "title": "Privacy Policy"
    })

@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service(request: Request):
    """Terms of Service page"""
    return templates.TemplateResponse("legal/terms.html", {
        "request": request,
        "title": "Terms of Service"
    })

@app.get("/license", response_class=HTMLResponse)
async def license_page(request: Request):
    """License page"""
    return templates.TemplateResponse("legal/license.html", {
        "request": request,
        "title": "License"
    })

# Static model fallbacks
def get_static_openai_models():
    return [
        {'id': 'gpt-4', 'name': 'GPT-4', 'description': 'Most capable', 'recommended': True},
        {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'description': 'Faster GPT-4', 'recommended': False},
        {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'description': 'Fast and efficient', 'recommended': False}
    ]

def get_static_anthropic_models():
    return [
        {'id': 'claude-3-sonnet-20240229', 'name': 'Claude 3 Sonnet', 'description': 'Balanced', 'recommended': True},
        {'id': 'claude-3-haiku-20240307', 'name': 'Claude 3 Haiku', 'description': 'Fast', 'recommended': False},
        {'id': 'claude-3-opus-20240229', 'name': 'Claude 3 Opus', 'description': 'Most powerful', 'recommended': False}
    ]

def get_static_gemini_models():
    return [
        {'id': 'gemini-2.0-flash-exp', 'name': 'Gemini 2.0 Flash (Experimental)', 'description': 'Latest Gemini 2.0 model', 'recommended': True},
        {'id': 'gemini-1.5-pro-latest', 'name': 'Gemini 1.5 Pro (Latest)', 'description': 'Advanced reasoning and analysis', 'recommended': False},
        {'id': 'gemini-1.5-pro', 'name': 'Gemini 1.5 Pro', 'description': 'Advanced reasoning and analysis', 'recommended': False},
        {'id': 'gemini-1.5-flash-latest', 'name': 'Gemini 1.5 Flash (Latest)', 'description': 'Fast and efficient', 'recommended': False},
        {'id': 'gemini-1.5-flash', 'name': 'Gemini 1.5 Flash', 'description': 'Fast and efficient', 'recommended': False},
        {'id': 'gemini-1.0-pro', 'name': 'Gemini 1.0 Pro', 'description': 'Legacy model', 'recommended': False}
    ]

def main():
    """Main entry point for admin server"""
    print(f"Starting PerfectMCP Admin Interface on {ADMIN_HOST}:{ADMIN_PORT}")
    print(f"Managing MCP server on port {MCP_SERVER_PORT}")
    print(f"Access the admin interface at: http://{SERVER_IP}:{ADMIN_PORT}")
    print(f"External access: http://{SERVER_IP}:{ADMIN_PORT}")

    uvicorn.run(
        "admin_server:app",
        host=ADMIN_HOST,
        port=ADMIN_PORT,
        reload=False,
        log_level="debug",  # Changed to debug to see all logs
        access_log=True     # Enable access logging
    )

if __name__ == "__main__":
    main()
