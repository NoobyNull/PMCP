#!/usr/bin/env python3
"""
Authentication and API Key Management for PerfectMPC
"""

import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"

@dataclass
class User:
    user_id: str
    username: str
    email: str
    role: UserRole
    api_keys: List[str]
    created_at: datetime
    last_login: Optional[datetime] = None
    active: bool = True

@dataclass
class APIKey:
    key_id: str
    key_hash: str
    user_id: str
    name: str
    permissions: List[str]
    created_at: datetime
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    active: bool = True

class AuthManager:
    def __init__(self, db_manager, secret_key: str = None):
        self.db_manager = db_manager
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.security = HTTPBearer(auto_error=False)
        
        # In-memory cache for performance
        self.users_cache: Dict[str, User] = {}
        self.api_keys_cache: Dict[str, APIKey] = {}
        self.sessions_cache: Dict[str, dict] = {}
        
    async def initialize(self):
        """Initialize auth system and create default admin user"""
        await self._create_default_admin()
        await self._load_cache()
    
    async def _create_default_admin(self):
        """Create default admin user if none exists"""
        try:
            # Check if any admin users exist
            admin_exists = await self.db_manager.mongo_find_one(
                "users", 
                {"role": UserRole.ADMIN.value}
            )
            
            if not admin_exists:
                # Create default admin
                admin_user = User(
                    user_id="admin-001",
                    username="admin",
                    email="admin@perfectmpc.local",
                    role=UserRole.ADMIN,
                    api_keys=[],
                    created_at=datetime.now(),
                    active=True
                )
                
                # Generate default API key
                api_key = await self.create_api_key(
                    admin_user.user_id,
                    "Default Admin Key",
                    ["*"]  # All permissions
                )
                admin_user.api_keys.append(api_key.key_id)
                
                # Save to database
                await self.db_manager.mongo_insert_one("users", {
                    "user_id": admin_user.user_id,
                    "username": admin_user.username,
                    "email": admin_user.email,
                    "role": admin_user.role.value,
                    "api_keys": admin_user.api_keys,
                    "created_at": admin_user.created_at,
                    "last_login": admin_user.last_login,
                    "active": admin_user.active
                })
                
                print(f"✅ Default admin user created")
                print(f"   Username: {admin_user.username}")
                print(f"   API Key: {api_key.key_id}")
                print(f"   Save this API key - it won't be shown again!")
                
        except Exception as e:
            print(f"Error creating default admin: {e}")
    
    async def _load_cache(self):
        """Load users and API keys into cache"""
        try:
            # Load users
            users = await self.db_manager.mongo_find_many("users", {})
            for user_data in users:
                user = User(
                    user_id=user_data["user_id"],
                    username=user_data["username"],
                    email=user_data["email"],
                    role=UserRole(user_data["role"]),
                    api_keys=user_data.get("api_keys", []),
                    created_at=user_data["created_at"],
                    last_login=user_data.get("last_login"),
                    active=user_data.get("active", True)
                )
                self.users_cache[user.user_id] = user
            
            # Load API keys
            api_keys = await self.db_manager.mongo_find_many("api_keys", {})
            for key_data in api_keys:
                api_key = APIKey(
                    key_id=key_data["key_id"],
                    key_hash=key_data["key_hash"],
                    user_id=key_data["user_id"],
                    name=key_data["name"],
                    permissions=key_data.get("permissions", []),
                    created_at=key_data["created_at"],
                    last_used=key_data.get("last_used"),
                    expires_at=key_data.get("expires_at"),
                    active=key_data.get("active", True)
                )
                self.api_keys_cache[api_key.key_id] = api_key
                
        except Exception as e:
            print(f"Error loading auth cache: {e}")
    
    def generate_api_key(self) -> Tuple[str, str]:
        """Generate a new API key and its hash"""
        # Generate a secure random key
        key = f"mpc_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return key, key_hash
    
    async def create_api_key(self, user_id: str, name: str, permissions: List[str], 
                           expires_days: Optional[int] = None) -> APIKey:
        """Create a new API key for a user"""
        key, key_hash = self.generate_api_key()
        
        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)
        
        api_key = APIKey(
            key_id=key,  # Use the actual key as ID for lookup
            key_hash=key_hash,
            user_id=user_id,
            name=name,
            permissions=permissions,
            created_at=datetime.now(),
            expires_at=expires_at,
            active=True
        )
        
        # Save to database
        await self.db_manager.mongo_insert_one("api_keys", {
            "key_id": api_key.key_id,
            "key_hash": api_key.key_hash,
            "user_id": api_key.user_id,
            "name": api_key.name,
            "permissions": api_key.permissions,
            "created_at": api_key.created_at,
            "last_used": api_key.last_used,
            "expires_at": api_key.expires_at,
            "active": api_key.active
        })
        
        # Update cache
        self.api_keys_cache[api_key.key_id] = api_key
        
        return api_key
    
    async def verify_api_key(self, api_key: str) -> Optional[Tuple[User, APIKey]]:
        """Verify an API key and return user and key info"""
        try:
            # Check cache first
            if api_key in self.api_keys_cache:
                key_obj = self.api_keys_cache[api_key]
                
                # Check if key is active and not expired
                if not key_obj.active:
                    return None
                
                if key_obj.expires_at and datetime.now() > key_obj.expires_at:
                    return None
                
                # Get user
                user = self.users_cache.get(key_obj.user_id)
                if not user or not user.active:
                    return None
                
                # Update last used
                key_obj.last_used = datetime.now()
                await self.db_manager.mongo_update_one(
                    "api_keys",
                    {"key_id": api_key},
                    {"$set": {"last_used": key_obj.last_used}}
                )
                
                return user, key_obj
            
            return None
            
        except Exception as e:
            print(f"Error verifying API key: {e}")
            return None
    
    async def create_user(self, username: str, email: str, role: UserRole) -> User:
        """Create a new user"""
        user_id = f"user_{secrets.token_urlsafe(8)}"
        
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            role=role,
            api_keys=[],
            created_at=datetime.now(),
            active=True
        )
        
        # Save to database
        await self.db_manager.mongo_insert_one("users", {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "api_keys": user.api_keys,
            "created_at": user.created_at,
            "last_login": user.last_login,
            "active": user.active
        })
        
        # Update cache
        self.users_cache[user.user_id] = user
        
        return user
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> User:
        """FastAPI dependency to get current user from API key"""
        if not credentials:
            raise HTTPException(status_code=401, detail="API key required")
        
        result = await self.verify_api_key(credentials.credentials)
        if not result:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        user, api_key = result
        return user
    
    def require_role(self, required_role: UserRole):
        """Decorator to require specific role"""
        async def role_checker(user: User = Depends(self.get_current_user)):
            if user.role != required_role and user.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return user
        return role_checker
    
    def require_permission(self, permission: str):
        """Decorator to require specific permission"""
        async def permission_checker(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
            if not credentials:
                raise HTTPException(status_code=401, detail="API key required")
            
            result = await self.verify_api_key(credentials.credentials)
            if not result:
                raise HTTPException(status_code=401, detail="Invalid API key")
            
            user, api_key = result
            
            # Admin has all permissions
            if user.role == UserRole.ADMIN:
                return user
            
            # Check if API key has required permission
            if permission not in api_key.permissions and "*" not in api_key.permissions:
                raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")
            
            return user
        return permission_checker

# Global auth manager instance
auth_manager: Optional[AuthManager] = None

def get_auth_manager() -> AuthManager:
    """Get the global auth manager instance"""
    if not auth_manager:
        raise HTTPException(status_code=500, detail="Auth manager not initialized")
    return auth_manager
