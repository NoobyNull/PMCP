"""
Memory Service for PerfectMPC
Handles session memory, context management, and code history
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from utils.database import DatabaseManager
from utils.config import MemoryConfig
from utils.logger import LoggerMixin


class MemoryService(LoggerMixin):
    """Service for managing session memory and context"""
    
    def __init__(self, db_manager: DatabaseManager, config: MemoryConfig):
        self.db = db_manager
        self.config = config
        self._sessions: Dict[str, Dict] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """Initialize the memory service"""
        self.logger.info("Initializing Memory Service")
        
        # Start cleanup task for expired sessions
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
        
        self.logger.info("Memory Service initialized successfully")
    
    async def shutdown(self):
        """Shutdown the memory service"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Memory Service shutdown complete")
    
    async def create_session(self, session_id: str = None) -> str:
        """Create a new memory session"""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # Check if session already exists
        if await self._session_exists(session_id):
            self.logger.warning(f"Session {session_id} already exists")
            return session_id
        
        session_data = {
            "session_id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
            "context": "",
            "context_size": 0,
            "metadata": {},
            "active": True
        }
        
        # Store in Redis for fast access
        redis_key = self.db.get_redis_key("session", session_id)
        await self.db.redis_set(
            redis_key,
            json.dumps(session_data),
            self.config.session_timeout
        )
        
        # Store in MongoDB for persistence
        collection = self.db.get_collection_name("sessions")
        await self.db.mongo_insert_one(collection, session_data)
        
        # Cache locally
        self._sessions[session_id] = session_data
        
        self.logger.info(f"Created session: {session_id}")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        # Try local cache first
        if session_id in self._sessions:
            session_data = self._sessions[session_id]
            await self._update_last_accessed(session_id)
            return session_data
        
        # Try Redis
        redis_key = self.db.get_redis_key("session", session_id)
        session_json = await self.db.redis_get(redis_key)
        
        if session_json:
            session_data = json.loads(session_json)
            self._sessions[session_id] = session_data
            await self._update_last_accessed(session_id)
            return session_data
        
        # Try MongoDB
        collection = self.db.get_collection_name("sessions")
        session_data = await self.db.mongo_find_one(collection, {"session_id": session_id})
        
        if session_data:
            # Restore to Redis
            await self.db.redis_set(
                redis_key,
                json.dumps(session_data),
                self.config.session_timeout
            )
            self._sessions[session_id] = session_data
            await self._update_last_accessed(session_id)
            return session_data
        
        return None
    
    async def update_context(self, session_id: str, context: str, metadata: Optional[Dict] = None):
        """Update session context"""
        session_data = await self.get_session(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")
        
        # Check context size limits
        if len(context) > self.config.max_context_size:
            if self.config.context.auto_summarize:
                context = await self._summarize_context(context)
            else:
                context = context[-self.config.max_context_size:]
        
        # Update session data
        session_data["context"] = context
        session_data["context_size"] = len(context)
        session_data["last_accessed"] = datetime.utcnow().isoformat()
        
        if metadata:
            session_data["metadata"].update(metadata)
        
        # Store context history
        await self._store_context_history(session_id, context, metadata)
        
        # Update in all storage layers
        await self._update_session_data(session_id, session_data)
        
        self.logger.debug(f"Updated context for session {session_id}, size: {len(context)}")
    
    async def get_context(self, session_id: str) -> Optional[str]:
        """Get current session context"""
        session_data = await self.get_session(session_id)
        if session_data:
            return session_data.get("context", "")
        return None
    
    async def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get session context history"""
        collection = self.db.get_collection_name("code_history")
        history = await self.db.mongo_find_many(
            collection,
            {"session_id": session_id},
            limit=limit,
            sort=[("timestamp", -1)]
        )
        return history
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        # Remove from local cache
        if session_id in self._sessions:
            del self._sessions[session_id]
        
        # Remove from Redis
        redis_key = self.db.get_redis_key("session", session_id)
        await self.db.redis_delete(redis_key)
        
        # Mark as inactive in MongoDB (don't delete for audit trail)
        collection = self.db.get_collection_name("sessions")
        success = await self.db.mongo_update_one(
            collection,
            {"session_id": session_id},
            {"active": False, "deleted_at": datetime.utcnow().isoformat()}
        )
        
        self.logger.info(f"Deleted session: {session_id}")
        return success
    
    async def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        collection = self.db.get_collection_name("sessions")
        sessions = await self.db.mongo_find_many(
            collection,
            {"active": True},
            limit=self.config.max_sessions
        )
        return [session["session_id"] for session in sessions]
    
    async def _session_exists(self, session_id: str) -> bool:
        """Check if session exists"""
        # Check local cache
        if session_id in self._sessions:
            return True
        
        # Check Redis
        redis_key = self.db.get_redis_key("session", session_id)
        if await self.db.redis_exists(redis_key):
            return True
        
        # Check MongoDB
        collection = self.db.get_collection_name("sessions")
        session = await self.db.mongo_find_one(collection, {"session_id": session_id, "active": True})
        return session is not None
    
    async def _update_last_accessed(self, session_id: str):
        """Update last accessed timestamp"""
        now = datetime.utcnow().isoformat()
        
        # Update local cache
        if session_id in self._sessions:
            self._sessions[session_id]["last_accessed"] = now
        
        # Update Redis
        redis_key = self.db.get_redis_key("session", session_id)
        session_json = await self.db.redis_get(redis_key)
        if session_json:
            session_data = json.loads(session_json)
            session_data["last_accessed"] = now
            await self.db.redis_set(
                redis_key,
                json.dumps(session_data),
                self.config.session_timeout
            )
    
    async def _update_session_data(self, session_id: str, session_data: Dict[str, Any]):
        """Update session data in all storage layers"""
        # Update local cache
        self._sessions[session_id] = session_data
        
        # Update Redis
        redis_key = self.db.get_redis_key("session", session_id)
        await self.db.redis_set(
            redis_key,
            json.dumps(session_data),
            self.config.session_timeout
        )
        
        # Update MongoDB
        collection = self.db.get_collection_name("sessions")
        await self.db.mongo_update_one(
            collection,
            {"session_id": session_id},
            session_data
        )
    
    async def _store_context_history(self, session_id: str, context: str, metadata: Optional[Dict]):
        """Store context change in history"""
        history_entry = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
            "context_size": len(context),
            "metadata": metadata or {},
            "type": "context_update"
        }
        
        collection = self.db.get_collection_name("code_history")
        await self.db.mongo_insert_one(collection, history_entry)
    
    async def _summarize_context(self, context: str) -> str:
        """Summarize context when it exceeds size limits"""
        # Simple truncation for now - could be enhanced with AI summarization
        target_size = self.config.context.summary_threshold
        if len(context) <= target_size:
            return context
        
        # Keep the most recent part of the context
        return "...[context summarized]...\n" + context[-target_size:]
    
    async def _cleanup_expired_sessions(self):
        """Background task to cleanup expired sessions"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                cutoff_time = datetime.utcnow() - timedelta(seconds=self.config.session_timeout)
                cutoff_str = cutoff_time.isoformat()
                
                # Find expired sessions
                collection = self.db.get_collection_name("sessions")
                expired_sessions = await self.db.mongo_find_many(
                    collection,
                    {
                        "active": True,
                        "last_accessed": {"$lt": cutoff_str}
                    }
                )
                
                # Mark as inactive
                for session in expired_sessions:
                    session_id = session["session_id"]
                    await self.delete_session(session_id)
                    self.logger.info(f"Cleaned up expired session: {session_id}")
                
                # Clean local cache
                expired_local = [
                    sid for sid, data in self._sessions.items()
                    if data.get("last_accessed", "") < cutoff_str
                ]
                
                for session_id in expired_local:
                    del self._sessions[session_id]
                
                if expired_sessions or expired_local:
                    self.logger.info(f"Cleaned up {len(expired_sessions + expired_local)} expired sessions")
                
            except Exception as e:
                self.logger.error(f"Error in session cleanup: {e}")
                await asyncio.sleep(60)  # Wait before retrying
