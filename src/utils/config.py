"""
Configuration management for PerfectMPC server
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    reload: bool = True
    workers: int = 1


class SSLConfig(BaseModel):
    enabled: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None


class CORSConfig(BaseModel):
    enabled: bool = True
    origins: List[str] = ["*"]
    methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    headers: List[str] = ["*"]


class RateLimitConfig(BaseModel):
    enabled: bool = True
    requests_per_minute: int = 100


class APIConfig(BaseModel):
    prefix: str = "/api"
    version: str = "v1"
    title: str = "PerfectMPC Server"
    description: str = "Multi-Party Computation Server for Code Development"
    rate_limit: RateLimitConfig = RateLimitConfig()
    cors: CORSConfig = CORSConfig()


class WebSocketConfig(BaseModel):
    enabled: bool = True
    path: str = "/ws"
    heartbeat_interval: int = 30
    max_connections: int = 100


class SSHAuthConfig(BaseModel):
    enabled: bool = False
    password_auth: bool = False
    key_auth: bool = False


class SSHConfig(BaseModel):
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 2222
    host_key_path: str = "/opt/PerfectMCP/config/ssh_host_key"
    auth: SSHAuthConfig = SSHAuthConfig()


class MemoryContextConfig(BaseModel):
    auto_summarize: bool = True
    summary_threshold: int = 8000
    max_history_items: int = 100


class MemoryConfig(BaseModel):
    max_context_size: int = 10000
    session_timeout: int = 3600
    max_sessions: int = 1000
    context: MemoryContextConfig = MemoryContextConfig()


class CodeAnalysisConfig(BaseModel):
    max_file_size: int = 1048576
    supported_languages: List[str] = [
        "python", "javascript", "typescript", "java", "cpp", "c", "go", "rust"
    ]


class AIModelConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4"
    max_tokens: int = 2000
    temperature: float = 0.1


class CodeImprovementConfig(BaseModel):
    enabled: bool = True
    analysis: CodeAnalysisConfig = CodeAnalysisConfig()
    ai_model: AIModelConfig = AIModelConfig()


class VectorDBConfig(BaseModel):
    provider: str = "chromadb"
    collection_name: str = "mpc_docs"
    embedding_model: str = "all-MiniLM-L6-v2"


class DocumentConfig(BaseModel):
    max_file_size: int = 10485760
    supported_formats: List[str] = ["txt", "md", "pdf", "docx", "html"]
    chunk_size: int = 1000
    chunk_overlap: int = 200


class SearchConfig(BaseModel):
    max_results: int = 10
    similarity_threshold: float = 0.7


class RAGConfig(BaseModel):
    enabled: bool = True
    vector_db: VectorDBConfig = VectorDBConfig()
    documents: DocumentConfig = DocumentConfig()
    search: SearchConfig = SearchConfig()


class LoggingComponentsConfig(BaseModel):
    database: str = "DEBUG"
    api: str = "INFO"
    websocket: str = "INFO"
    ssh: str = "INFO"
    memory: str = "DEBUG"
    code_improvement: str = "INFO"
    rag: str = "INFO"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "human"  # Changed from "json" to "human" for better readability
    file: str = "/opt/PerfectMCP/logs/server.log"
    max_size: str = "100MB"
    backup_count: int = 5
    components: LoggingComponentsConfig = LoggingComponentsConfig()


class RedisConnectionConfig(BaseModel):
    max_connections: int = 20
    retry_on_timeout: bool = True
    socket_timeout: int = 5
    socket_connect_timeout: int = 5


class RedisPrefixesConfig(BaseModel):
    session: str = "mpc:session:"
    cache: str = "mpc:cache:"
    memory: str = "mpc:memory:"
    context: str = "mpc:context:"


class RedisTTLConfig(BaseModel):
    session: int = 3600
    cache: int = 1800
    memory: int = 7200
    context: int = 86400


class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    connection: RedisConnectionConfig = RedisConnectionConfig()
    prefixes: RedisPrefixesConfig = RedisPrefixesConfig()
    ttl: RedisTTLConfig = RedisTTLConfig()


class MongoConnectionConfig(BaseModel):
    max_pool_size: int = 20
    min_pool_size: int = 5
    max_idle_time_ms: int = 30000
    server_selection_timeout_ms: int = 5000


class MongoCollectionsConfig(BaseModel):
    users: str = "users"
    sessions: str = "sessions"
    code_history: str = "code_history"
    documents: str = "documents"
    embeddings: str = "embeddings"
    improvements: str = "improvements"
    analytics: str = "analytics"


class MongoDBConfig(BaseModel):
    host: str = "localhost"
    port: int = 27017
    database: str = "perfectmpc"
    username: Optional[str] = None
    password: Optional[str] = None
    connection: MongoConnectionConfig = MongoConnectionConfig()
    collections: MongoCollectionsConfig = MongoCollectionsConfig()


class DatabaseConfig(BaseModel):
    redis: RedisConfig = RedisConfig()
    mongodb: MongoDBConfig = MongoDBConfig()


class Config(BaseModel):
    """Main configuration class"""
    server: ServerConfig = ServerConfig()
    api: APIConfig = APIConfig()
    websocket: WebSocketConfig = WebSocketConfig()
    ssh: SSHConfig = SSHConfig()
    memory: MemoryConfig = MemoryConfig()
    code_improvement: CodeImprovementConfig = CodeImprovementConfig()
    rag: RAGConfig = RAGConfig()
    logging: LoggingConfig = LoggingConfig()
    database: DatabaseConfig = DatabaseConfig()

    @classmethod
    def load_from_files(cls, config_dir: str = "/opt/PerfectMCP/config") -> "Config":
        """Load configuration from YAML files"""
        config_path = Path(config_dir)
        
        # Load server config
        server_config = {}
        server_file = config_path / "server.yaml"
        if server_file.exists():
            with open(server_file, 'r') as f:
                server_config = yaml.safe_load(f) or {}
        
        # Load database config
        database_config = {}
        database_file = config_path / "database.yaml"
        if database_file.exists():
            with open(database_file, 'r') as f:
                database_config = yaml.safe_load(f) or {}
        
        # Merge configurations
        merged_config = {**server_config}
        if database_config:
            merged_config["database"] = database_config
        
        # Override with environment variables
        cls._override_with_env(merged_config)
        
        return cls(**merged_config)
    
    @staticmethod
    def _override_with_env(config: Dict[str, Any]):
        """Override configuration with environment variables"""
        # Server overrides
        if os.getenv("MPC_HOST"):
            config.setdefault("server", {})["host"] = os.getenv("MPC_HOST")
        if os.getenv("MPC_PORT"):
            config.setdefault("server", {})["port"] = int(os.getenv("MPC_PORT"))
        if os.getenv("MPC_DEBUG"):
            config.setdefault("server", {})["debug"] = os.getenv("MPC_DEBUG").lower() == "true"
        
        # Database overrides
        if os.getenv("REDIS_HOST"):
            config.setdefault("database", {}).setdefault("redis", {})["host"] = os.getenv("REDIS_HOST")
        if os.getenv("REDIS_PORT"):
            config.setdefault("database", {}).setdefault("redis", {})["port"] = int(os.getenv("REDIS_PORT"))
        if os.getenv("MONGO_HOST"):
            config.setdefault("database", {}).setdefault("mongodb", {})["host"] = os.getenv("MONGO_HOST")
        if os.getenv("MONGO_PORT"):
            config.setdefault("database", {}).setdefault("mongodb", {})["port"] = int(os.getenv("MONGO_PORT"))


# Global config instance
_config_instance = None

def get_config() -> Config:
    """Get global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config.load_from_files()
    return _config_instance

# For backwards compatibility - remove this line
