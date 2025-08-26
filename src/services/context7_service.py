"""
Context 7 Service for PerfectMPC
Advanced context management with 7-layer context hierarchy
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from utils.database import DatabaseManager
from utils.config import MemoryConfig
from utils.logger import LoggerMixin


class ContextLayer(Enum):
    """7-layer context hierarchy"""
    IMMEDIATE = 1      # Current conversation/task context
    SESSION = 2        # Current session context
    PROJECT = 3        # Project-level context
    DOMAIN = 4         # Domain knowledge context
    HISTORICAL = 5     # Historical patterns and learnings
    GLOBAL = 6         # Global knowledge and patterns
    META = 7           # Meta-cognitive and reasoning context


class ContextPriority(Enum):
    """Context priority levels"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class Context7Service(LoggerMixin):
    """Advanced context management service with 7-layer hierarchy"""
    
    def __init__(self, db_manager: DatabaseManager, config: MemoryConfig):
        self.db = db_manager
        self.config = config
        self._context_store: Dict[str, Dict] = {}
        self._layer_weights = {
            ContextLayer.IMMEDIATE: 1.0,
            ContextLayer.SESSION: 0.8,
            ContextLayer.PROJECT: 0.6,
            ContextLayer.DOMAIN: 0.5,
            ContextLayer.HISTORICAL: 0.4,
            ContextLayer.GLOBAL: 0.3,
            ContextLayer.META: 0.2
        }
        
    async def initialize(self):
        """Initialize the Context 7 service"""
        self.logger.info("Initializing Context 7 Service")
        
        # Load existing contexts from database
        await self._load_contexts()
        
        self.logger.info("Context 7 Service initialized successfully")
    
    async def shutdown(self):
        """Shutdown the Context 7 service"""
        # Save all contexts to database
        await self._save_contexts()
        self.logger.info("Context 7 Service shutdown complete")
    
    async def add_context(
        self, 
        session_id: str, 
        content: str, 
        layer: ContextLayer,
        priority: ContextPriority = ContextPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add context to a specific layer"""
        context_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        context_entry = {
            "id": context_id,
            "session_id": session_id,
            "content": content,
            "layer": layer.value,
            "priority": priority.value,
            "metadata": metadata or {},
            "timestamp": timestamp.isoformat(),
            "access_count": 0,
            "last_accessed": timestamp.isoformat(),
            "relevance_score": 1.0
        }
        
        # Store in memory
        if session_id not in self._context_store:
            self._context_store[session_id] = {}
        if layer.value not in self._context_store[session_id]:
            self._context_store[session_id][layer.value] = []
            
        self._context_store[session_id][layer.value].append(context_entry)
        
        # Store in database
        await self.db.mongo_insert_one("context7", context_entry)
        
        self.logger.debug(f"Added context to layer {layer.name}", 
                         session_id=session_id, context_id=context_id)
        
        return context_id
    
    async def get_layered_context(
        self, 
        session_id: str, 
        max_tokens: int = 4000,
        include_layers: Optional[List[ContextLayer]] = None
    ) -> Dict[str, Any]:
        """Get context from all layers with intelligent merging"""
        
        if include_layers is None:
            include_layers = list(ContextLayer)
        
        layered_context = {}
        total_tokens = 0
        
        # Sort layers by priority (immediate first)
        sorted_layers = sorted(include_layers, key=lambda x: x.value)
        
        for layer in sorted_layers:
            if total_tokens >= max_tokens:
                break
                
            layer_context = await self._get_layer_context(
                session_id, layer, max_tokens - total_tokens
            )
            
            if layer_context:
                layered_context[layer.name] = layer_context
                total_tokens += self._estimate_tokens(layer_context)
        
        # Calculate context coherence score
        coherence_score = await self._calculate_coherence(layered_context)
        
        return {
            "session_id": session_id,
            "layers": layered_context,
            "total_tokens": total_tokens,
            "coherence_score": coherence_score,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def merge_contexts(
        self, 
        session_id: str, 
        context_ids: List[str],
        target_layer: ContextLayer
    ) -> str:
        """Intelligently merge multiple contexts into a single context"""
        
        contexts = []
        for context_id in context_ids:
            context = await self._get_context_by_id(session_id, context_id)
            if context:
                contexts.append(context)
        
        if not contexts:
            raise ValueError("No valid contexts found for merging")
        
        # Merge content with intelligent summarization
        merged_content = await self._intelligent_merge(contexts)
        
        # Calculate merged metadata
        merged_metadata = self._merge_metadata([ctx["metadata"] for ctx in contexts])
        
        # Create new merged context
        merged_id = await self.add_context(
            session_id=session_id,
            content=merged_content,
            layer=target_layer,
            priority=ContextPriority.HIGH,
            metadata=merged_metadata
        )
        
        self.logger.info(f"Merged {len(contexts)} contexts into {merged_id}")
        
        return merged_id
    
    async def switch_context(
        self, 
        session_id: str, 
        new_context_id: str,
        preserve_immediate: bool = True
    ) -> Dict[str, Any]:
        """Switch to a different context while preserving important information"""
        
        # Get current immediate context
        current_immediate = None
        if preserve_immediate:
            current_immediate = await self._get_layer_context(
                session_id, ContextLayer.IMMEDIATE
            )
        
        # Load new context
        new_context = await self._get_context_by_id(session_id, new_context_id)
        if not new_context:
            raise ValueError(f"Context {new_context_id} not found")
        
        # Create context switch record
        switch_record = {
            "session_id": session_id,
            "from_context": current_immediate,
            "to_context": new_context,
            "timestamp": datetime.utcnow().isoformat(),
            "preserved_immediate": preserve_immediate
        }
        
        # Store switch record
        await self.db.mongo_insert_one("context_switches", switch_record)
        
        return {
            "switched_to": new_context_id,
            "preserved_immediate": preserve_immediate,
            "switch_record": switch_record
        }
    
    async def analyze_context_patterns(self, session_id: str) -> Dict[str, Any]:
        """Analyze context usage patterns and provide insights"""
        
        contexts = await self._get_all_session_contexts(session_id)
        
        if not contexts:
            return {"message": "No contexts found for analysis"}
        
        # Analyze patterns
        layer_distribution = {}
        priority_distribution = {}
        temporal_patterns = []
        
        for context in contexts:
            layer = context["layer"]
            priority = context["priority"]
            
            layer_distribution[layer] = layer_distribution.get(layer, 0) + 1
            priority_distribution[priority] = priority_distribution.get(priority, 0) + 1
            
            temporal_patterns.append({
                "timestamp": context["timestamp"],
                "layer": layer,
                "access_count": context["access_count"]
            })
        
        # Calculate insights
        most_used_layer = max(layer_distribution, key=layer_distribution.get)
        context_diversity = len(layer_distribution) / len(ContextLayer)
        
        return {
            "session_id": session_id,
            "total_contexts": len(contexts),
            "layer_distribution": layer_distribution,
            "priority_distribution": priority_distribution,
            "most_used_layer": most_used_layer,
            "context_diversity": context_diversity,
            "temporal_patterns": temporal_patterns,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    
    # Private helper methods
    async def _load_contexts(self):
        """Load contexts from database"""
        try:
            contexts = await self.db.mongo_find_many("context7", {})
            for context in contexts:
                session_id = context["session_id"]
                layer = context["layer"]

                if session_id not in self._context_store:
                    self._context_store[session_id] = {}
                if layer not in self._context_store[session_id]:
                    self._context_store[session_id][layer] = []

                self._context_store[session_id][layer].append(context)

        except Exception as e:
            self.logger.error(f"Failed to load contexts: {e}")
    
    async def _save_contexts(self):
        """Save contexts to database"""
        try:
            # This is handled by individual operations, but could batch save here
            pass
        except Exception as e:
            self.logger.error(f"Failed to save contexts: {e}")
    
    async def _get_layer_context(
        self, 
        session_id: str, 
        layer: ContextLayer, 
        max_tokens: int = 1000
    ) -> Optional[List[Dict]]:
        """Get context from a specific layer"""
        
        if session_id not in self._context_store:
            return None
        
        layer_contexts = self._context_store[session_id].get(layer.value, [])
        
        if not layer_contexts:
            return None
        
        # Sort by relevance and recency
        sorted_contexts = sorted(
            layer_contexts,
            key=lambda x: (x["relevance_score"], x["timestamp"]),
            reverse=True
        )
        
        # Select contexts within token limit
        selected_contexts = []
        current_tokens = 0
        
        for context in sorted_contexts:
            context_tokens = self._estimate_tokens(context["content"])
            if current_tokens + context_tokens <= max_tokens:
                selected_contexts.append(context)
                current_tokens += context_tokens
            else:
                break
        
        return selected_contexts
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        # Simple estimation: ~4 characters per token
        return len(str(text)) // 4
    
    async def _calculate_coherence(self, layered_context: Dict) -> float:
        """Calculate coherence score for layered context"""
        # Simple coherence calculation based on layer consistency
        if not layered_context:
            return 0.0
        
        # More layers with content = higher coherence
        layer_count = len(layered_context)
        max_layers = len(ContextLayer)
        
        return min(1.0, layer_count / max_layers)
    
    async def _get_context_by_id(self, session_id: str, context_id: str) -> Optional[Dict]:
        """Get a specific context by ID"""
        try:
            context = await self.db.mongo_find_one("context7", {"id": context_id, "session_id": session_id})
            return context
        except Exception as e:
            self.logger.error(f"Failed to get context {context_id}: {e}")
            return None
    
    async def _intelligent_merge(self, contexts: List[Dict]) -> str:
        """Intelligently merge context content"""
        # Simple merge for now - could use AI summarization
        contents = [ctx["content"] for ctx in contexts]
        return "\n\n".join(contents)
    
    def _merge_metadata(self, metadata_list: List[Dict]) -> Dict:
        """Merge metadata from multiple contexts"""
        merged = {}
        for metadata in metadata_list:
            merged.update(metadata)
        return merged
    
    async def _get_all_session_contexts(self, session_id: str) -> List[Dict]:
        """Get all contexts for a session"""
        try:
            contexts = await self.db.mongo_find_many("context7", {"session_id": session_id})
            return list(contexts)
        except Exception as e:
            self.logger.error(f"Failed to get session contexts: {e}")
            return []
