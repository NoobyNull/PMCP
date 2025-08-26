#!/usr/bin/env python3
"""
Test LAN access for PerfectMPC server
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

def run_command(cmd):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def get_server_ip():
    """Get server IP address"""
    success, stdout, stderr = run_command("hostname -I | awk '{print $1}'")
    return stdout.strip() if success else "unknown"

async def test_database_lan_access():
    """Test database LAN access"""
    print("🔍 Testing Database LAN Access...")
    
    server_ip = get_server_ip()
    print(f"   Server IP: {server_ip}")
    
    # Test Redis LAN access
    success, stdout, stderr = run_command(f"redis-cli -h {server_ip} ping")
    redis_status = "✓ Accessible" if success and "PONG" in stdout else "✗ Not accessible"
    print(f"   Redis ({server_ip}:6379): {redis_status}")
    
    # Test MongoDB LAN access
    success, stdout, stderr = run_command(f"mongosh --host {server_ip} --eval 'db.adminCommand(\"ping\")' --quiet")
    mongo_status = "✓ Accessible" if success else "✗ Not accessible"
    print(f"   MongoDB ({server_ip}:27017): {mongo_status}")
    
    return redis_status.startswith("✓") and mongo_status.startswith("✓")

async def test_server_startup():
    """Test server startup"""
    print("\n🚀 Testing Server Startup...")
    
    # Add src to path for imports
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    
    try:
        from utils.config import get_config
        from utils.database import DatabaseManager
        
        config = get_config()
        print(f"   ✓ Configuration loaded")
        print(f"   ✓ Server configured for: {config.server.host}:{config.server.port}")
        
        # Test database manager initialization
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()
        print(f"   ✓ Database connections established")
        
        # Test basic operations
        await db_manager.redis_set("test:lan", "working", 60)
        result = await db_manager.redis_get("test:lan")
        if result == "working":
            print(f"   ✓ Redis operations working")
        else:
            print(f"   ✗ Redis operations failed")
        
        # Test MongoDB
        test_doc = {"test": "lan_access", "timestamp": time.time()}
        doc_id = await db_manager.mongo_insert_one("test_collection", test_doc)
        if doc_id:
            print(f"   ✓ MongoDB operations working")
        else:
            print(f"   ✗ MongoDB operations failed")
        
        await db_manager.close()
        return True
        
    except Exception as e:
        print(f"   ✗ Server startup test failed: {e}")
        return False

async def test_api_endpoints():
    """Test API endpoints (if server is running)"""
    print("\n🌐 Testing API Endpoints...")
    
    server_ip = get_server_ip()
    
    # Test if server is running
    success, stdout, stderr = run_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://{server_ip}:8000/health")
    
    if success and stdout == "200":
        print(f"   ✓ Server is running and accessible at http://{server_ip}:8000")
        
        # Test health endpoint
        success, stdout, stderr = run_command(f"curl -s http://{server_ip}:8000/health")
        if success and "healthy" in stdout:
            print(f"   ✓ Health endpoint working")
        else:
            print(f"   ✗ Health endpoint failed")
        
        # Test root endpoint
        success, stdout, stderr = run_command(f"curl -s http://{server_ip}:8000/")
        if success and "PerfectMPC" in stdout:
            print(f"   ✓ Root endpoint working")
        else:
            print(f"   ✗ Root endpoint failed")
        
        return True
    else:
        print(f"   ℹ Server not running (this is normal if not started yet)")
        print(f"   ℹ To start server: python3 start_server.py")
        return False

def show_connection_examples():
    """Show connection examples"""
    server_ip = get_server_ip()
    
    print(f"\n📋 LAN Connection Examples:")
    print(f"   Server IP: {server_ip}")
    print(f"")
    print(f"   🌐 HTTP API:")
    print(f"      curl http://{server_ip}:8000/health")
    print(f"      curl http://{server_ip}:8000/")
    print(f"")
    print(f"   🔧 SSH Access:")
    print(f"      ssh -p 2222 user@{server_ip}")
    print(f"")
    print(f"   📁 SFTP Access:")
    print(f"      sftp -P 2222 user@{server_ip}")
    print(f"")
    print(f"   💾 Database Access:")
    print(f"      redis-cli -h {server_ip} -p 6379")
    print(f"      mongosh --host {server_ip} --port 27017")
    print(f"")
    print(f"   🔌 Augment VSCode Plugin Config:")
    print(f"      Host: {server_ip}")
    print(f"      Port: 8000")
    print(f"      Protocol: http")

async def main():
    """Main test function"""
    print("PerfectMPC LAN Access Test")
    print("=" * 50)
    
    # Test database LAN access
    db_success = await test_database_lan_access()
    
    # Test server startup capability
    server_success = await test_server_startup()
    
    # Test API endpoints (if running)
    api_success = await test_api_endpoints()
    
    # Show connection examples
    show_connection_examples()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"   Database LAN Access: {'✓ PASS' if db_success else '✗ FAIL'}")
    print(f"   Server Startup:      {'✓ PASS' if server_success else '✗ FAIL'}")
    print(f"   API Endpoints:       {'✓ PASS' if api_success else 'ℹ NOT RUNNING'}")
    
    if db_success and server_success:
        print("\n🎉 LAN configuration is working correctly!")
        print("   Ready for Augment VSCode plugin integration")
        
        if not api_success:
            print("\n📝 Next Steps:")
            print("   1. Start the server: python3 start_server.py")
            print("   2. Test from client machine:")
            server_ip = get_server_ip()
            print(f"      curl http://{server_ip}:8000/health")
            print("   3. Configure Augment VSCode plugin")
        
        return 0
    else:
        print("\n❌ Some tests failed. Please check the configuration.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
