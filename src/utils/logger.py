"""
Comprehensive Logging System for PerfectMPC
Implements syslog-style logging with multiple destinations and structured formatting
"""

import json
import logging
import logging.handlers
import sys
import os
import time
import threading
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime
from contextlib import contextmanager
from functools import wraps

import structlog
from structlog.stdlib import LoggerFactory

from .config import LoggingConfig

# Custom log levels
TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")

def trace(self, message, *args, **kwargs):
    """Log trace level message"""
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kwargs)

logging.Logger.trace = trace


class StructuredJSONFormatter(logging.Formatter):
    """Enhanced JSON formatter for structured logging with context"""

    def __init__(self, include_context=True):
        super().__init__()
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "severity": self._get_severity(record.levelname),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "thread": threading.current_thread().name,
            "thread_id": threading.get_ident(),
            "process": os.getpid(),
            "hostname": os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        }

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }

        # Add context data if available
        if self.include_context and hasattr(record, 'context'):
            log_entry["context"] = record.context

        # Add performance data if available
        if hasattr(record, 'duration'):
            log_entry["performance"] = {
                "duration_ms": round(record.duration * 1000, 2),
                "operation": getattr(record, 'operation', 'unknown')
            }

        # Add extra fields
        excluded_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
            'filename', 'module', 'lineno', 'funcName', 'created',
            'msecs', 'relativeCreated', 'thread', 'threadName',
            'processName', 'process', 'getMessage', 'exc_info',
            'exc_text', 'stack_info', 'context', 'duration', 'operation'
        }

        for key, value in record.__dict__.items():
            if key not in excluded_fields:
                log_entry[key] = value

        return json.dumps(log_entry, default=str, ensure_ascii=False)

    def _get_severity(self, level_name: str) -> int:
        """Convert log level to syslog severity"""
        severity_map = {
            'TRACE': 7,     # Debug
            'DEBUG': 7,     # Debug
            'INFO': 6,      # Informational
            'WARNING': 4,   # Warning
            'ERROR': 3,     # Error
            'FATAL': 2,     # Critical
            'CRITICAL': 2   # Critical
        }
        return severity_map.get(level_name, 6)

class ConsoleFormatter(logging.Formatter):
    """Enhanced human-readable console formatter with colors and context"""

    COLORS = {
        'TRACE': '\033[90m',     # Dark gray
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'FATAL': '\033[35m',     # Magenta
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }

    LEVEL_ICONS = {
        'TRACE': '🔍',
        'DEBUG': '🐛',
        'INFO': 'ℹ️ ',
        'WARNING': '⚠️ ',
        'ERROR': '❌',
        'FATAL': '💀',
        'CRITICAL': '💀'
    }

    def __init__(self, use_colors=True, include_context=True, use_icons=True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
        self.include_context = include_context
        self.use_icons = use_icons

    def format(self, record: logging.LogRecord) -> str:
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]

        # Format level with color and icon
        level = record.levelname
        icon = self.LEVEL_ICONS.get(level, '  ') if self.use_icons else ''

        if self.use_colors:
            color = self.COLORS.get(level, '')
            reset = self.COLORS['RESET']
            level_colored = f"{color}{level:7}{reset}"
        else:
            level_colored = f"{level:7}"

        # Format logger name (shortened for readability)
        logger_parts = record.name.split('.')
        if len(logger_parts) > 2:
            logger_name = f"{logger_parts[0]}...{logger_parts[-1]}"
        else:
            logger_name = record.name
        logger_name = logger_name[:20]  # Limit length

        # Build main message
        main_message = f"{timestamp} {icon}{level_colored} [{logger_name:20}] {record.getMessage()}"

        # Add context information on separate lines for readability
        context_lines = []

        # Add function and line info for DEBUG and TRACE
        if level in ['DEBUG', 'TRACE'] and hasattr(record, 'funcName'):
            context_lines.append(f"    📍 {record.funcName}() at line {record.lineno}")

        # Add context data if available
        if self.include_context and hasattr(record, 'context'):
            context_items = []
            for key, value in record.context.items():
                # Format different types of context nicely
                if key in ['duration', 'duration_ms']:
                    if isinstance(value, (int, float)):
                        if key == 'duration_ms':
                            context_items.append(f"⏱️  {value}ms")
                        else:
                            context_items.append(f"⏱️  {value:.3f}s")
                elif key in ['request_id', 'job_id', 'doc_id']:
                    context_items.append(f"🔑 {key}: {value}")
                elif key in ['client_ip', 'host']:
                    context_items.append(f"🌐 {key}: {value}")
                elif key in ['session_id']:
                    context_items.append(f"👤 {key}: {value}")
                elif key in ['operation', 'method', 'endpoint']:
                    context_items.append(f"🔧 {key}: {value}")
                elif key in ['file_size', 'content_length', 'message_size']:
                    if isinstance(value, int):
                        if value > 1024*1024:
                            context_items.append(f"📦 {key}: {value/(1024*1024):.1f}MB")
                        elif value > 1024:
                            context_items.append(f"📦 {key}: {value/1024:.1f}KB")
                        else:
                            context_items.append(f"📦 {key}: {value}B")
                    else:
                        context_items.append(f"📦 {key}: {value}")
                elif key in ['status_code']:
                    status_icon = "✅" if value < 400 else "⚠️" if value < 500 else "❌"
                    context_items.append(f"{status_icon} {key}: {value}")
                else:
                    context_items.append(f"{key}: {value}")

            if context_items:
                context_lines.append(f"    {' | '.join(context_items)}")

        # Add performance info if available
        if hasattr(record, 'duration') and not (hasattr(record, 'context') and 'duration' in record.context):
            duration = record.duration
            if duration > 5.0:
                context_lines.append(f"    🐌 Slow operation: {duration:.3f}s")
            elif duration > 1.0:
                context_lines.append(f"    ⏱️  Duration: {duration:.3f}s")

        # Combine main message with context
        full_message = main_message
        if context_lines:
            full_message += "\n" + "\n".join(context_lines)

        # Add exception if present
        if record.exc_info:
            exception_text = self.formatException(record.exc_info)
            # Indent exception for better readability
            indented_exception = "\n".join(f"    {line}" for line in exception_text.split("\n"))
            full_message += f"\n    💥 Exception:\n{indented_exception}"

        return full_message

# Legacy alias for backward compatibility
JSONFormatter = StructuredJSONFormatter

class HumanReadableFormatter(logging.Formatter):
    """Human-readable columnar formatter - everything on one line"""

    def __init__(self):
        super().__init__()
        self.include_context = True

    def format(self, record: logging.LogRecord) -> str:
        # Format timestamp - shorter format
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')

        # Format logger name (shortened for readability)
        logger_parts = record.name.split('.')
        if 'services' in logger_parts:
            # Extract service name: src.services.memory_service -> memory
            service_name = logger_parts[-1].replace('_service', '')
            logger_name = service_name
        elif len(logger_parts) > 1:
            logger_name = logger_parts[-1]  # Just use the last part
        else:
            logger_name = record.name

        # Clean up logger name
        logger_name = logger_name.replace('Service', '').replace('_', '')

        # Get level - shorter format
        level_map = {
            'DEBUG': 'DBG',
            'INFO': 'INF',
            'WARNING': 'WRN',
            'ERROR': 'ERR',
            'CRITICAL': 'CRT'
        }
        level = level_map.get(record.levelname, record.levelname[:3])

        # Get clean message - handle dict messages
        message = record.getMessage()
        if message.startswith('{') and message.endswith('}'):
            try:
                import json
                msg_dict = eval(message)  # Safe since it's from our own logging
                if 'event' in msg_dict:
                    message = msg_dict['event']
                elif 'message' in msg_dict:
                    message = msg_dict['message']
                else:
                    # Take first meaningful value
                    for key, value in msg_dict.items():
                        if key not in ['logger', 'level', 'timestamp'] and isinstance(value, str):
                            message = f"{key}: {value}"
                            break
            except:
                pass  # Keep original message if parsing fails

        # Build columnar format: TIME LEVEL COMPONENT MESSAGE [CONTEXT]
        main_message = f"{timestamp} {level:3} {logger_name:10} {message}"

        # Add important context in a compact format
        context_parts = []
        if hasattr(record, 'context') and record.context:
            for k, v in record.context.items():
                if k in ['operation', 'session_id', 'user_id', 'endpoint']:
                    context_parts.append(f"{k}={v}")

        # Add duration if available
        if hasattr(record, 'duration'):
            context_parts.append(f"took={record.duration:.2f}s")

        if context_parts:
            main_message += f" [{', '.join(context_parts)}]"

        # Add function info for DEBUG level only
        if record.levelno <= logging.DEBUG:
            main_message += f" @{record.funcName}:{record.lineno}"

        # Add exception info on same line if present
        if record.exc_info:
            exc_msg = str(record.exc_info[1]) if record.exc_info[1] else "Exception"
            main_message += f" ERROR: {exc_msg}"

        return main_message


class PlainFormatter(logging.Formatter):
    """Plain text formatter"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging(config: LoggingConfig, enable_syslog: bool = False, syslog_address: str = '/dev/log'):
    """Setup comprehensive logging configuration"""

    # Create logs directory if it doesn't exist
    log_file_path = Path(config.file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure structlog with enhanced processors
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Get root logger
    root_logger = logging.getLogger()

    # Set log level (support TRACE level)
    log_level = config.level.upper()
    if log_level == 'TRACE':
        root_logger.setLevel(TRACE_LEVEL)
    else:
        root_logger.setLevel(getattr(logging, log_level))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Add context filter for all handlers
    context_filter = ContextFilter()

    # Set global context filter
    global _context_filter
    _context_filter = context_filter
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_level = log_level if log_level != 'TRACE' else 'DEBUG'
    console_handler.setLevel(getattr(logging, console_level))
    console_handler.addFilter(context_filter)

    if config.format.lower() == "json":
        console_formatter = StructuredJSONFormatter(include_context=True)
    else:
        # Use human-readable syslog-style formatter for console
        console_formatter = HumanReadableFormatter()

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        # Parse max_size (e.g., "100MB" -> 100 * 1024 * 1024)
        max_size_str = config.max_size.upper()
        if max_size_str.endswith('MB'):
            max_bytes = int(max_size_str[:-2]) * 1024 * 1024
        elif max_size_str.endswith('KB'):
            max_bytes = int(max_size_str[:-2]) * 1024
        elif max_size_str.endswith('GB'):
            max_bytes = int(max_size_str[:-2]) * 1024 * 1024 * 1024
        else:
            max_bytes = int(max_size_str)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=config.file,
            maxBytes=max_bytes,
            backupCount=config.backup_count,
            encoding='utf-8'
        )

        file_level = log_level if log_level != 'TRACE' else 'DEBUG'
        file_handler.setLevel(getattr(logging, file_level))
        file_handler.addFilter(context_filter)

        # Use different formatters based on configuration
        if config.format.lower() == "json":
            file_formatter = StructuredJSONFormatter(include_context=True)
        elif config.format.lower() == "human" or config.format.lower() == "syslog":
            file_formatter = HumanReadableFormatter()
        else:
            file_formatter = HumanReadableFormatter()  # Default to human-readable

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}")

    # Syslog handler (optional)
    if enable_syslog:
        try:
            if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
                syslog_handler = logging.handlers.SysLogHandler(
                    address=syslog_address,
                    facility=logging.handlers.SysLogHandler.LOG_LOCAL0
                )
            else:
                # Windows - use UDP to localhost
                syslog_handler = logging.handlers.SysLogHandler(
                    address=('localhost', 514),
                    facility=logging.handlers.SysLogHandler.LOG_LOCAL0
                )

            syslog_handler.setLevel(logging.INFO)  # Only INFO and above to syslog
            syslog_handler.addFilter(context_filter)

            # Syslog format (RFC 3164 compatible)
            syslog_formatter = logging.Formatter(
                'PerfectMPC[%(process)d]: %(levelname)s %(name)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            root_logger.addHandler(syslog_handler)

        except Exception as e:
            print(f"Warning: Could not setup syslog logging: {e}")
    
    # Configure component-specific loggers
    component_levels = config.components.dict()
    for component, level in component_levels.items():
        logger = logging.getLogger(f"src.services.{component}_service")
        logger.setLevel(getattr(logging, level.upper()))
        
        # Special cases for external libraries
        if component == "database":
            logging.getLogger("motor").setLevel(getattr(logging, level.upper()))
            logging.getLogger("pymongo").setLevel(getattr(logging, level.upper()))
            logging.getLogger("redis").setLevel(getattr(logging, level.upper()))
        elif component == "api":
            logging.getLogger("fastapi").setLevel(getattr(logging, level.upper()))
            logging.getLogger("uvicorn").setLevel(getattr(logging, level.upper()))
        elif component == "websocket":
            logging.getLogger("websockets").setLevel(getattr(logging, level.upper()))
        elif component == "ssh":
            logging.getLogger("paramiko").setLevel(getattr(logging, level.upper()))
            logging.getLogger("asyncssh").setLevel(getattr(logging, level.upper()))
    
    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Setup Redis logging
    try:
        from .redis_log_handler import setup_redis_logging
        redis_success = setup_redis_logging(
            redis_host='localhost',
            redis_port=6379,
            redis_db=15,
            max_logs=10000,
            log_level=getattr(logging, log_level)
        )
        if redis_success:
            print("✅ Redis logging enabled - DB 15")
        else:
            print("⚠️  Redis logging disabled - falling back to file only")
    except Exception as e:
        print(f"⚠️  Redis logging setup failed: {e}")

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully", extra={
        "log_level": config.level,
        "log_format": config.format,
        "log_file": config.file,
        "redis_logging": "enabled"
    })


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


class ContextFilter(logging.Filter):
    """Filter to add context information to log records"""

    def __init__(self):
        super().__init__()
        self.context_stack = threading.local()

    def filter(self, record):
        """Add context to log record"""
        if not hasattr(self.context_stack, 'contexts'):
            self.context_stack.contexts = []

        # Merge all contexts in the stack
        context = {}
        for ctx in self.context_stack.contexts:
            context.update(ctx)

        if context:
            record.context = context

        return True

    def push_context(self, **kwargs):
        """Push context onto the stack"""
        if not hasattr(self.context_stack, 'contexts'):
            self.context_stack.contexts = []
        self.context_stack.contexts.append(kwargs)

    def pop_context(self):
        """Pop context from the stack"""
        if hasattr(self.context_stack, 'contexts') and self.context_stack.contexts:
            return self.context_stack.contexts.pop()
        return {}

# Global context filter instance
_context_filter = None

class EnhancedLoggerMixin:
    """Enhanced mixin class with comprehensive logging capabilities"""

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get logger for this class"""
        return get_logger(self.__class__.__name__)

    def log_method_entry(self, method_name: str, **kwargs):
        """Log method entry with parameters"""
        self.logger.debug(
            f"Entering {method_name}",
            method=method_name,
            params=list(kwargs.keys()) if kwargs else None,
            class_name=self.__class__.__name__
        )

    def log_method_exit(self, method_name: str, result=None, duration: float = None):
        """Log method exit with result and duration"""
        extra = {
            "method": method_name,
            "class_name": self.__class__.__name__
        }

        if duration is not None:
            extra["duration"] = duration

        if result is not None:
            extra["result_type"] = type(result).__name__
            extra["result_size"] = len(result) if hasattr(result, '__len__') else None

        self.logger.debug(f"Exiting {method_name}", **extra)

    def log_error(self, message: str, error: Exception = None, **context):
        """Log error with context"""
        extra = {
            "class_name": self.__class__.__name__,
            "error_type": type(error).__name__ if error else None
        }
        extra.update(context)

        if error:
            self.logger.error(message, exc_info=error, **extra)
        else:
            self.logger.error(message, **extra)

    def log_performance(self, operation: str, duration: float, **context):
        """Log performance metrics"""
        extra = {
            "operation": operation,
            "duration": duration,
            "duration_ms": round(duration * 1000, 2),
            "class_name": self.__class__.__name__
        }
        extra.update(context)

        # Log as warning if operation is slow
        if duration > 5.0:  # 5 seconds
            self.logger.warning(f"Slow operation: {operation} took {duration:.3f}s", **extra)
        elif duration > 1.0:  # 1 second
            self.logger.info(f"Performance: {operation} completed in {duration:.3f}s", **extra)
        else:
            self.logger.debug(f"Performance: {operation} completed in {duration:.3f}s", **extra)

# Backward compatibility alias
LoggerMixin = EnhancedLoggerMixin


@contextmanager
def log_context(**context):
    """Context manager for adding structured context to logs"""
    global _context_filter
    if _context_filter:
        _context_filter.push_context(**context)
    try:
        yield
    finally:
        if _context_filter:
            _context_filter.pop_context()

@contextmanager
def log_performance(operation: str, logger_name: str = None, **context):
    """Context manager for logging operation performance"""
    logger = get_logger(logger_name or 'performance')
    start_time = time.time()

    logger.debug(f"Starting {operation}", operation=operation, **context)

    try:
        yield
        duration = time.time() - start_time

        extra = {"operation": operation, "duration": duration, "success": True}
        extra.update(context)

        if duration > 5.0:
            logger.warning(f"Slow operation: {operation} took {duration:.3f}s", **extra)
        elif duration > 1.0:
            logger.info(f"Operation {operation} completed in {duration:.3f}s", **extra)
        else:
            logger.debug(f"Operation {operation} completed in {duration:.3f}s", **extra)

    except Exception as e:
        duration = time.time() - start_time
        extra = {
            "operation": operation,
            "duration": duration,
            "success": False,
            "error_type": type(e).__name__,
            "error_message": str(e)
        }
        extra.update(context)

        logger.error(f"Operation {operation} failed after {duration:.3f}s", exc_info=e, **extra)
        raise

class LogContext:
    """Enhanced context manager for structured logging context"""

    def __init__(self, **context):
        self.context = context

    def __enter__(self):
        global _context_filter
        if _context_filter:
            _context_filter.push_context(**self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _context_filter
        if _context_filter:
            _context_filter.pop_context()


# Enhanced decorators for comprehensive logging
def log_function_call(
    logger_name: str = None,
    level: str = 'DEBUG',
    include_args: bool = False,
    include_result: bool = False,
    performance: bool = True
):
    """Enhanced decorator to log function calls with performance tracking"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name or func.__module__)
            start_time = time.time()

            # Log function entry
            extra = {
                "function": func.__name__,
                "module": func.__module__,
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys())
            }

            if include_args:
                extra["args"] = str(args)[:200]  # Truncate long args
                extra["kwargs"] = {k: str(v)[:100] for k, v in kwargs.items()}

            getattr(logger, level.lower())(f"Calling {func.__name__}", **extra)

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Log function exit
                exit_extra = {
                    "function": func.__name__,
                    "success": True,
                    "duration": duration
                }

                if include_result and result is not None:
                    exit_extra["result_type"] = type(result).__name__
                    exit_extra["result_size"] = len(result) if hasattr(result, '__len__') else None

                if performance and duration > 0.1:  # Log performance if > 100ms
                    logger.info(f"Function {func.__name__} completed in {duration:.3f}s", **exit_extra)
                else:
                    logger.debug(f"Function {func.__name__} completed", **exit_extra)

                return result

            except Exception as e:
                duration = time.time() - start_time
                error_extra = {
                    "function": func.__name__,
                    "success": False,
                    "duration": duration,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }

                logger.error(f"Function {func.__name__} failed", exc_info=e, **error_extra)
                raise

        return wrapper
    return decorator

def log_async_function_call(
    logger_name: str = None,
    level: str = 'DEBUG',
    include_args: bool = False,
    include_result: bool = False,
    performance: bool = True
):
    """Enhanced decorator to log async function calls with performance tracking"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(logger_name or func.__module__)
            start_time = time.time()

            # Log function entry
            extra = {
                "function": func.__name__,
                "module": func.__module__,
                "async": True,
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys())
            }

            if include_args:
                extra["args"] = str(args)[:200]
                extra["kwargs"] = {k: str(v)[:100] for k, v in kwargs.items()}

            getattr(logger, level.lower())(f"Calling async {func.__name__}", **extra)

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # Log function exit
                exit_extra = {
                    "function": func.__name__,
                    "async": True,
                    "success": True,
                    "duration": duration
                }

                if include_result and result is not None:
                    exit_extra["result_type"] = type(result).__name__
                    exit_extra["result_size"] = len(result) if hasattr(result, '__len__') else None

                if performance and duration > 0.1:
                    logger.info(f"Async function {func.__name__} completed in {duration:.3f}s", **exit_extra)
                else:
                    logger.debug(f"Async function {func.__name__} completed", **exit_extra)

                return result

            except Exception as e:
                duration = time.time() - start_time
                error_extra = {
                    "function": func.__name__,
                    "async": True,
                    "success": False,
                    "duration": duration,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }

                logger.error(f"Async function {func.__name__} failed", exc_info=e, **error_extra)
                raise

        return wrapper
    return decorator

# Convenience functions for common logging patterns
def log_api_request(endpoint: str, method: str, **context):
    """Log API request"""
    logger = get_logger('api')
    logger.info(f"API Request: {method} {endpoint}",
                endpoint=endpoint, method=method, **context)

def log_api_response(endpoint: str, method: str, status_code: int, duration: float, **context):
    """Log API response"""
    logger = get_logger('api')

    extra = {
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration": duration,
        "duration_ms": round(duration * 1000, 2)
    }
    extra.update(context)

    if status_code >= 500:
        logger.error(f"API Error: {method} {endpoint} -> {status_code}", **extra)
    elif status_code >= 400:
        logger.warning(f"API Client Error: {method} {endpoint} -> {status_code}", **extra)
    elif duration > 2.0:
        logger.warning(f"Slow API: {method} {endpoint} -> {status_code} ({duration:.3f}s)", **extra)
    else:
        logger.info(f"API Response: {method} {endpoint} -> {status_code}", **extra)

def log_database_operation(operation: str, collection: str, duration: float, **context):
    """Log database operation"""
    logger = get_logger('database')

    extra = {
        "operation": operation,
        "collection": collection,
        "duration": duration,
        "duration_ms": round(duration * 1000, 2)
    }
    extra.update(context)

    if duration > 1.0:
        logger.warning(f"Slow DB operation: {operation} on {collection} ({duration:.3f}s)", **extra)
    else:
        logger.debug(f"DB operation: {operation} on {collection}", **extra)
