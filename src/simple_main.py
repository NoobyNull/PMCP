#!/usr/bin/env python3
"""
Simple main server for PerfectMPC - minimal version for testing
"""

import asyncio
import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Simple configuration
class SimpleConfig:
    def __init__(self):
        self.server = SimpleServerConfig()
        self.database = SimpleDatabaseConfig()

class SimpleServerConfig:
    def __init__(self):
        self.host = "0.0.0.0"
        self.port = 8000
        self.debug = False

class SimpleDatabaseConfig:
    def __init__(self):
        self.redis = SimpleRedisConfig()
        self.mongodb = SimpleMongoConfig()

class SimpleRedisConfig:
    def __init__(self):
        self.host = "localhost"
        self.port = 6379

class SimpleMongoConfig:
    def __init__(self):
        self.host = "localhost"
        self.port = 27017

# Initialize configuration
config = SimpleConfig()

# Initialize FastAPI app
app = FastAPI(
    title="PerfectMPC Server",
    description="Multi-Party Computation Server for Code Development",
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

# Basic routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PerfectMPC Server",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "api": "running",
            "database": "checking"
        }
    }

@app.get("/api/status")
async def api_status():
    """API status endpoint"""
    return {
        "api": "running",
        "version": "1.0.0",
        "endpoints": ["/", "/health", "/api/status"]
    }

# Basic session endpoints
@app.post("/api/memory/session")
async def create_session():
    """Create session endpoint"""
    return {
        "session_id": "test-session",
        "status": "created",
        "message": "Basic session endpoint working"
    }

@app.get("/api/memory/session/{session_id}")
async def get_session(session_id: str):
    """Get session endpoint"""
    return {
        "session_id": session_id,
        "status": "active",
        "message": "Basic session retrieval working"
    }

def main():
    """Main entry point"""
    print("Starting PerfectMPC Server (Simple Mode)")
    print(f"Server will run on {config.server.host}:{config.server.port}")
    
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start server
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info"
    )

if __name__ == "__main__":
    main()
