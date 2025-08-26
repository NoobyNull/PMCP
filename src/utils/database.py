"""
Database management for PerfectMPC server
Handles Redis and MongoDB connections
"""

import asyncio
import logging
from typing import Optional, Dict, Any

import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError

from .config import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.mongo_db = None
        
    async def initialize(self):
        """Initialize database connections"""
        await self._init_redis()
        await self._init_mongodb()
        
    async def _init_redis(self):
        """Initialize Redis connection"""
        try:
            redis_config = self.config.redis
            
            self.redis_client = redis.Redis(
                host=redis_config.host,
                port=redis_config.port,
                db=redis_config.db,
                password=redis_config.password,
                max_connections=redis_config.connection.max_connections,
                retry_on_timeout=redis_config.connection.retry_on_timeout,
                socket_timeout=redis_config.connection.socket_timeout,
                socket_connect_timeout=redis_config.connection.socket_connect_timeout,
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Redis connection established")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
            
    async def _init_mongodb(self):
        """Initialize MongoDB connection"""
        try:
            mongo_config = self.config.mongodb
            
            # Build connection string
            if mongo_config.username and mongo_config.password:
                connection_string = (
                    f"mongodb://{mongo_config.username}:{mongo_config.password}@"
                    f"{mongo_config.host}:{mongo_config.port}/{mongo_config.database}"
                )
            else:
                connection_string = f"mongodb://{mongo_config.host}:{mongo_config.port}"
            
            self.mongo_client = AsyncIOMotorClient(
                connection_string,
                maxPoolSize=mongo_config.connection.max_pool_size,
                minPoolSize=mongo_config.connection.min_pool_size,
                maxIdleTimeMS=mongo_config.connection.max_idle_time_ms,
                serverSelectionTimeoutMS=mongo_config.connection.server_selection_timeout_ms
            )
            
            self.mongo_db = self.mongo_client[mongo_config.database]
            
            # Test connection
            await self.mongo_client.admin.command('ping')
            logger.info("MongoDB connection established")
            
            # Create indexes
            await self._create_indexes()
            
        except ServerSelectionTimeoutError as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"MongoDB initialization error: {e}")
            raise
            
    async def _create_indexes(self):
        """Create database indexes"""
        try:
            collections = self.config.mongodb.collections
            
            # Sessions collection indexes
            sessions_collection = self.mongo_db[collections.sessions]
            await sessions_collection.create_index("session_id", unique=True)
            await sessions_collection.create_index("timestamp")
            
            # Code history collection indexes
            code_history_collection = self.mongo_db[collections.code_history]
            await code_history_collection.create_index([("session_id", 1), ("timestamp", -1)])
            
            # Documents collection indexes
            documents_collection = self.mongo_db[collections.documents]
            await documents_collection.create_index("doc_id", unique=True)
            await documents_collection.create_index("session_id")
            
            # Embeddings collection indexes
            embeddings_collection = self.mongo_db[collections.embeddings]
            await embeddings_collection.create_index([("doc_id", 1), ("chunk_id", 1)], unique=True)
            
            # Improvements collection indexes
            improvements_collection = self.mongo_db[collections.improvements]
            await improvements_collection.create_index([("session_id", 1), ("timestamp", -1)])
            
            # Analytics collection indexes
            analytics_collection = self.mongo_db[collections.analytics]
            await analytics_collection.create_index([("timestamp", -1)])
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            # Don't raise here as indexes might already exist
            
    async def close(self):
        """Close database connections"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
            
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB connection closed")
    
    # Redis operations
    async def redis_get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        try:
            return await self.redis_client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    async def redis_set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in Redis"""
        try:
            if ttl:
                return await self.redis_client.setex(key, ttl, value)
            else:
                return await self.redis_client.set(key, value)
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    async def redis_delete(self, key: str) -> bool:
        """Delete key from Redis"""
        try:
            return bool(await self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
    
    async def redis_exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        try:
            return bool(await self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    # MongoDB operations
    async def mongo_insert_one(self, collection: str, document: Dict[str, Any]) -> Optional[str]:
        """Insert document into MongoDB"""
        try:
            result = await self.mongo_db[collection].insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"MongoDB INSERT error for collection {collection}: {e}")
            return None
    
    async def mongo_find_one(self, collection: str, filter_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find one document in MongoDB"""
        try:
            result = await self.mongo_db[collection].find_one(filter_dict)
            if result and '_id' in result:
                result['_id'] = str(result['_id'])
            return result
        except Exception as e:
            logger.error(f"MongoDB FIND_ONE error for collection {collection}: {e}")
            return None
    
    async def mongo_find_many(self, collection: str, filter_dict: Dict[str, Any], 
                             limit: Optional[int] = None, sort: Optional[list] = None) -> list:
        """Find multiple documents in MongoDB"""
        try:
            cursor = self.mongo_db[collection].find(filter_dict)
            
            if sort:
                cursor = cursor.sort(sort)
            if limit:
                cursor = cursor.limit(limit)
                
            results = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for result in results:
                if '_id' in result:
                    result['_id'] = str(result['_id'])
                    
            return results
        except Exception as e:
            logger.error(f"MongoDB FIND_MANY error for collection {collection}: {e}")
            return []
    
    async def mongo_update_one(self, collection: str, filter_dict: Dict[str, Any], 
                              update_dict: Dict[str, Any]) -> bool:
        """Update one document in MongoDB"""
        try:
            result = await self.mongo_db[collection].update_one(filter_dict, {"$set": update_dict})
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"MongoDB UPDATE_ONE error for collection {collection}: {e}")
            return False
    
    async def mongo_delete_one(self, collection: str, filter_dict: Dict[str, Any]) -> bool:
        """Delete one document from MongoDB"""
        try:
            result = await self.mongo_db[collection].delete_one(filter_dict)
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"MongoDB DELETE_ONE error for collection {collection}: {e}")
            return False
    
    # Utility methods
    def get_redis_key(self, prefix: str, identifier: str) -> str:
        """Generate Redis key with prefix"""
        prefixes = self.config.redis.prefixes
        prefix_map = {
            "session": prefixes.session,
            "cache": prefixes.cache,
            "memory": prefixes.memory,
            "context": prefixes.context
        }
        return f"{prefix_map.get(prefix, prefix)}{identifier}"
    
    def get_collection_name(self, collection_type: str) -> str:
        """Get MongoDB collection name"""
        collections = self.config.mongodb.collections
        collection_map = {
            "users": collections.users,
            "sessions": collections.sessions,
            "code_history": collections.code_history,
            "documents": collections.documents,
            "embeddings": collections.embeddings,
            "improvements": collections.improvements,
            "analytics": collections.analytics
        }
        return collection_map.get(collection_type, collection_type)
