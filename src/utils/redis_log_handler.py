"""
Redis Log Handler for PerfectMCP
Stores logs in Redis for real-time access and better performance
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
import redis
import asyncio
from threading import Lock


class RedisLogHandler(logging.Handler):
    """Custom logging handler that stores logs in Redis"""
    
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=15,
                 max_logs=10000, log_key='pmcp:logs'):
        super().__init__()
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.max_logs = max_logs
        self.log_key = log_key
        self.redis_client = None
        self._lock = Lock()
        
        # Initialize Redis connection
        self._connect()
        
    def _connect(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            print(f"✅ Redis log handler connected to {self.redis_host}:{self.redis_port} DB {self.redis_db}")
        except Exception as e:
            print(f"❌ Failed to connect to Redis for logging: {e}")
            self.redis_client = None
    
    def emit(self, record):
        """Emit a log record to Redis"""
        if not self.redis_client:
            return
            
        try:
            with self._lock:
                # Format the log record
                log_entry = self._format_log_entry(record)
                
                # Add to Redis list (LPUSH for newest first)
                self.redis_client.lpush(self.log_key, json.dumps(log_entry))
                
                # Trim list to max size (keep newest entries)
                self.redis_client.ltrim(self.log_key, 0, self.max_logs - 1)
                
        except Exception as e:
            # Don't let logging errors break the application
            print(f"Redis logging error: {e}")
    
    def _format_log_entry(self, record) -> Dict[str, Any]:
        """Format log record into structured data"""
        # Get the formatted message
        message = self.format(record)
        
        # Extract component from logger name
        component = self._extract_component(record.name)
        
        # Create structured log entry
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'component': component,
            'logger': record.name,
            'message': message,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'session_id'):
            log_entry['session_id'] = record.session_id
        if hasattr(record, 'operation'):
            log_entry['operation'] = record.operation
            
        return log_entry
    
    def _extract_component(self, logger_name: str) -> str:
        """Extract component name from logger name"""
        # Map logger names to components
        component_map = {
            'main': 'core',
            'memory': 'memory',
            'code': 'code_improvement', 
            'rag': 'rag',
            'context7': 'context7',
            'playwright': 'playwright',
            'sequential': 'sequential_thinking',
            'ssh': 'ssh',
            'plugin': 'plugin_manager',
            'admin': 'admin_server',
            'api': 'api',
            'database': 'database',
            'auth': 'auth'
        }
        
        # Check for exact matches first
        if logger_name in component_map:
            return component_map[logger_name]
            
        # Check for partial matches
        for key, component in component_map.items():
            if key in logger_name.lower():
                return component
                
        return 'system'
    
    def get_logs(self, count: int = 100, level: Optional[str] = None, 
                 component: Optional[str] = None, search: Optional[str] = None) -> list:
        """Retrieve logs from Redis with filtering"""
        if not self.redis_client:
            return []
            
        try:
            # Get logs from Redis (LRANGE for newest first)
            raw_logs = self.redis_client.lrange(self.log_key, 0, count * 2)  # Get extra for filtering
            
            logs = []
            for raw_log in raw_logs:
                try:
                    log_entry = json.loads(raw_log)
                    
                    # Apply filters
                    if level and log_entry.get('level', '').upper() != level.upper():
                        continue
                        
                    if component and log_entry.get('component', '') != component:
                        continue
                        
                    if search and search.lower() not in log_entry.get('message', '').lower():
                        continue
                        
                    logs.append(log_entry)
                    
                    # Stop when we have enough filtered results
                    if len(logs) >= count:
                        break
                        
                except json.JSONDecodeError:
                    continue
                    
            return logs
            
        except Exception as e:
            print(f"Error retrieving logs from Redis: {e}")
            return []
    
    def clear_logs(self):
        """Clear all logs from Redis"""
        if self.redis_client:
            try:
                self.redis_client.delete(self.log_key)
                return True
            except Exception as e:
                print(f"Error clearing logs: {e}")
                return False
        return False
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get statistics about stored logs"""
        if not self.redis_client:
            return {}
            
        try:
            total_logs = self.redis_client.llen(self.log_key)
            
            # Get level distribution from recent logs
            recent_logs = self.redis_client.lrange(self.log_key, 0, 999)
            level_counts = {}
            component_counts = {}
            
            for raw_log in recent_logs:
                try:
                    log_entry = json.loads(raw_log)
                    level = log_entry.get('level', 'UNKNOWN')
                    component = log_entry.get('component', 'unknown')
                    
                    level_counts[level] = level_counts.get(level, 0) + 1
                    component_counts[component] = component_counts.get(component, 0) + 1
                except:
                    continue
                    
            return {
                'total_logs': total_logs,
                'level_distribution': level_counts,
                'component_distribution': component_counts,
                'redis_db': self.redis_db,
                'max_logs': self.max_logs
            }
            
        except Exception as e:
            print(f"Error getting log stats: {e}")
            return {}


class AsyncRedisLogHandler:
    """Async wrapper for Redis log operations"""
    
    def __init__(self, redis_handler: RedisLogHandler):
        self.handler = redis_handler
    
    async def get_logs_async(self, count: int = 100, level: Optional[str] = None,
                           component: Optional[str] = None, search: Optional[str] = None) -> list:
        """Async version of get_logs"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.handler.get_logs, count, level, component, search)
    
    async def get_log_stats_async(self) -> Dict[str, Any]:
        """Async version of get_log_stats"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.handler.get_log_stats)
    
    async def clear_logs_async(self) -> bool:
        """Async version of clear_logs"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.handler.clear_logs)


# Global Redis log handler instance
_redis_log_handler = None
_async_redis_handler = None


def setup_redis_logging(redis_host='localhost', redis_port=6379, redis_db=15,
                       max_logs=10000, log_level=logging.INFO):
    """Setup Redis logging for the application"""
    global _redis_log_handler, _async_redis_handler
    
    try:
        # Create Redis log handler
        _redis_log_handler = RedisLogHandler(
            redis_host=redis_host,
            redis_port=redis_port, 
            redis_db=redis_db,
            max_logs=max_logs
        )
        
        # Set log format
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s',
            datefmt='%H:%M:%S'
        )
        _redis_log_handler.setFormatter(formatter)
        _redis_log_handler.setLevel(log_level)
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(_redis_log_handler)
        
        # Create async wrapper
        _async_redis_handler = AsyncRedisLogHandler(_redis_log_handler)
        
        print(f"✅ Redis logging setup complete - DB {redis_db}, max {max_logs} logs")
        return True
        
    except Exception as e:
        print(f"❌ Failed to setup Redis logging: {e}")
        return False


def get_redis_log_handler() -> Optional[RedisLogHandler]:
    """Get the global Redis log handler"""
    return _redis_log_handler


def get_async_redis_handler() -> Optional[AsyncRedisLogHandler]:
    """Get the async Redis log handler"""
    return _async_redis_handler
