#!/usr/bin/env python3
"""
PerfectMPC - Multi-Party Computation Server
Main application entry point
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from api.routes import api_router, set_services
from services.memory_service import MemoryService
from services.code_improvement_service import CodeImprovementService
from services.rag_service import RAGService
from services.ssh_service import SSHService
from services.context7_service import Context7Service
from services.playwright_service import PlaywrightService
from services.sequential_thinking_service import SequentialThinkingService
from services.plugin_manager import PluginManager
from utils.config import get_config
from utils.database import DatabaseManager
from utils.logger import setup_logging

# Initialize configuration
config = get_config()

# Setup logging
setup_logging(config.logging)
logger = logging.getLogger(__name__)

# Request logging middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log incoming request
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"Incoming request: {request.method} {request.url.path} from {client_ip}")

        # Process request
        response = await call_next(request)

        # Log response
        duration = time.time() - start_time
        logger.info(f"Response: {request.method} {request.url.path} -> {response.status_code} [took={duration:.3f}s]")

        return response

# Global services
db_manager = None
memory_service = None
code_improvement_service = None
rag_service = None
ssh_service = None
context7_service = None
playwright_service = None
sequential_thinking_service = None
plugin_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    global db_manager, memory_service, code_improvement_service, rag_service, ssh_service
    global context7_service, playwright_service, sequential_thinking_service, plugin_manager

    # Startup
    logger.info("Starting PerfectMCP server...")

    try:
        # Initialize database manager
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()
        logger.info("Database manager initialized")

        # Initialize services
        memory_service = MemoryService(db_manager, config.memory)
        await memory_service.initialize()
        logger.info("Memory service initialized")

        code_improvement_service = CodeImprovementService(db_manager, config.code_improvement)
        await code_improvement_service.initialize()
        logger.info("Code improvement service initialized")

        rag_service = RAGService(db_manager, config.rag)
        await rag_service.initialize()
        logger.info("RAG service initialized")

        # Initialize new advanced services
        context7_service = Context7Service(db_manager, config.memory)
        await context7_service.initialize()
        logger.info("Context7 service initialized")

        try:
            playwright_service = PlaywrightService(db_manager)
            await playwright_service.initialize()
            logger.info("Playwright service initialized")
        except ImportError:
            logger.warning("Playwright not available - install with: pip install playwright")
            playwright_service = None
        except Exception as e:
            logger.warning(f"Playwright service failed to initialize: {e}")
            playwright_service = None

        sequential_thinking_service = SequentialThinkingService(db_manager)
        await sequential_thinking_service.initialize()
        logger.info("Sequential Thinking service initialized")

        # Initialize plugin manager
        plugin_manager = PluginManager(db_manager)
        await plugin_manager.initialize()
        logger.info("Plugin manager initialized")

        # Set services in API routes
        set_services(
            memory_service,
            code_improvement_service,
            rag_service,
            context7_service,
            playwright_service,
            sequential_thinking_service
        )
        logger.info("Services injected into API routes")

        # Initialize SSH service if enabled
        if config.ssh.enabled:
            ssh_service = SSHService(config.ssh, memory_service, code_improvement_service, rag_service)
            await ssh_service.start()
            logger.info(f"SSH service started on port {config.ssh.port}")

        logger.info("All services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        sys.exit(1)

    yield

    # Shutdown
    logger.info("Shutting down PerfectMCP server...")

    if ssh_service:
        await ssh_service.stop()
        logger.info("SSH service stopped")

    if sequential_thinking_service:
        await sequential_thinking_service.shutdown()
        logger.info("Sequential Thinking service stopped")

    if playwright_service:
        await playwright_service.shutdown()
        logger.info("Playwright service stopped")

    if context7_service:
        await context7_service.shutdown()
        logger.info("Context7 service stopped")

    if db_manager:
        await db_manager.close()
        logger.info("Database connections closed")

    logger.info("Server shutdown complete")

# Initialize FastAPI app
app = FastAPI(
    title=config.api.title,
    description=config.api.description,
    version=config.api.version,
    debug=config.server.debug,
    lifespan=lifespan
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add CORS middleware
if config.api.cors.enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors.origins,
        allow_credentials=True,
        allow_methods=config.api.cors.methods,
        allow_headers=config.api.cors.headers,
    )



# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")

manager = ConnectionManager()



@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PerfectMCP Server",
        "version": config.api.version,
        "status": "running",
        "services": {
            "memory": memory_service is not None,
            "code_improvement": code_improvement_service is not None,
            "rag": rag_service is not None,
            "context7": context7_service is not None,
            "playwright": playwright_service is not None,
            "sequential_thinking": sequential_thinking_service is not None,
            "ssh": ssh_service is not None and config.ssh.enabled
        }
    }

@app.post("/")
async def mcp_endpoint(request: dict):
    """MCP JSON-RPC endpoint for Augment and other MCP clients"""
    try:
        logger.info(f"MCP request: {request.get('method', 'unknown')} [id={request.get('id', 'none')}]")

        # Handle MCP JSON-RPC requests
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "tools/list":
            # Get all tools from core system and installed plugins
            if plugin_manager:
                tools = plugin_manager.get_all_tools()
                logger.info(f"Returning {len(tools)} tools to MCP client")
            else:
                # Fallback to core tools if plugin manager not available
                tools = [
                    {
                        "name": "memory_context",
                        "description": "Manage memory context for sessions",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "session_id": {"type": "string"},
                                "context": {"type": "string"}
                            }
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
                            }
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
                            }
                        }
                    }
                ]
                logger.warning("Plugin manager not available, using core tools only")

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools}
            }

        elif method == "tools/call":
            # Handle tool calls
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            logger.info(f"Tool call: {tool_name} with args: {tool_args}")

            # Route tool call through plugin manager
            if plugin_manager:
                result = await plugin_manager.handle_tool_call(tool_name, tool_args)
            else:
                result = {"status": "success", "message": f"Called {tool_name} (plugin manager not available)"}

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": str(result)}]}
            }

        elif method == "initialize":
            # MCP initialization
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True}
                    },
                    "serverInfo": {
                        "name": "PerfectMPC",
                        "version": config.api.version
                    }
                }
            }

        else:
            # Unknown method
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    except Exception as e:
        logger.error(f"MCP endpoint error: {str(e)}")
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connections
        redis_status = await db_manager.redis_client.ping() if db_manager else False
        mongo_status = db_manager.mongo_client is not None if db_manager else False
        
        return {
            "status": "healthy",
            "timestamp": asyncio.get_event_loop().time(),
            "services": {
                "redis": redis_status,
                "mongodb": mongo_status,
                "memory": memory_service is not None,
                "code_improvement": code_improvement_service is not None,
                "rag": rag_service is not None,
                "context7": context7_service is not None,
                "playwright": playwright_service is not None,
                "sequential_thinking": sequential_thinking_service is not None,
                "ssh": ssh_service is not None
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")
            
            # Echo back for now - can be extended for real-time features
            await manager.send_personal_message(f"Echo: {data}", websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Include API routes
app.include_router(api_router, prefix=config.api.prefix)

def main():
    """Main entry point"""
    logger.info(f"Starting server on {config.server.host}:{config.server.port}")
    
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug,
        workers=config.server.workers,
        log_level="info" if not config.server.debug else "debug"
    )

if __name__ == "__main__":
    main()
