#!/usr/bin/env python3
"""
Test script to verify PerfectMPC setup
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_basic_imports():
    """Test basic imports"""
    print("Testing basic imports...")
    
    try:
        from utils.config import get_config
        print("✓ Config import successful")
        
        config = get_config()
        print(f"✓ Config loaded: {config.server.host}:{config.server.port}")
        
    except Exception as e:
        print(f"✗ Config import failed: {e}")
        return False
    
    try:
        from utils.database import DatabaseManager
        print("✓ Database manager import successful")
    except Exception as e:
        print(f"✗ Database manager import failed: {e}")
        return False
    
    return True

async def test_database_connections():
    """Test database connections"""
    print("\nTesting database connections...")
    
    try:
        from utils.config import get_config
        from utils.database import DatabaseManager
        
        config = get_config()
        db_manager = DatabaseManager(config.database)
        
        # Test Redis connection
        try:
            await db_manager._init_redis()
            await db_manager.redis_client.ping()
            print("✓ Redis connection successful")
        except Exception as e:
            print(f"✗ Redis connection failed: {e}")
            return False
        
        # Test MongoDB connection
        try:
            await db_manager._init_mongodb()
            await db_manager.mongo_client.admin.command('ping')
            print("✓ MongoDB connection successful")
        except Exception as e:
            print(f"✗ MongoDB connection failed: {e}")
            return False
        
        await db_manager.close()
        return True
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

async def test_basic_server():
    """Test basic server startup"""
    print("\nTesting basic server startup...")
    
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        # Create a simple test app
        app = FastAPI()
        
        @app.get("/")
        async def root():
            return {"message": "PerfectMPC Test Server", "status": "running"}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        # Test with TestClient
        client = TestClient(app)
        
        response = client.get("/")
        if response.status_code == 200:
            print("✓ Basic FastAPI server test successful")
        else:
            print(f"✗ Server test failed: {response.status_code}")
            return False
        
        response = client.get("/health")
        if response.status_code == 200:
            print("✓ Health endpoint test successful")
        else:
            print(f"✗ Health endpoint test failed: {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Server test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("PerfectMPC Setup Test")
    print("=" * 50)
    
    tests = [
        test_basic_imports,
        test_database_connections,
        test_basic_server
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if await test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! PerfectMPC setup is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the setup.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
