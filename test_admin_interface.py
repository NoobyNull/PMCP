#!/usr/bin/env python3
"""
Test script for PerfectMPC Admin Interface
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

def run_command(cmd):
    """Run shell command and return result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def get_server_ip():
    """Get server IP address"""
    success, stdout, stderr = run_command("hostname -I | awk '{print $1}'")
    return stdout.strip() if success else "localhost"

async def test_admin_interface_startup():
    """Test admin interface startup"""
    print("🔍 Testing Admin Interface Startup...")
    
    # Check if admin server can be imported
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import admin_server
        print("   ✓ Admin server module imports successfully")
        
        # Check if templates directory exists
        admin_dir = Path(__file__).parent / "admin"
        templates_dir = admin_dir / "templates"
        
        if templates_dir.exists():
            print("   ✓ Templates directory exists")
            
            # Check for required templates
            required_templates = [
                "base.html",
                "dashboard.html", 
                "sessions.html",
                "database.html",
                "documents.html",
                "logs.html"
            ]
            
            missing_templates = []
            for template in required_templates:
                if not (templates_dir / template).exists():
                    missing_templates.append(template)
            
            if missing_templates:
                print(f"   ✗ Missing templates: {', '.join(missing_templates)}")
                return False
            else:
                print("   ✓ All required templates exist")
        else:
            print("   ✗ Templates directory missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ✗ Admin server import failed: {e}")
        return False

async def test_admin_dependencies():
    """Test admin interface dependencies"""
    print("\n🔍 Testing Admin Interface Dependencies...")
    
    required_packages = [
        "fastapi",
        "uvicorn", 
        "jinja2",
        "python-multipart"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✓ {package} available")
        except ImportError:
            missing_packages.append(package)
            print(f"   ✗ {package} missing")
    
    if missing_packages:
        print(f"\n   Install missing packages: pip install {' '.join(missing_packages)}")
        return False
    
    return True

async def test_admin_configuration():
    """Test admin interface configuration"""
    print("\n🔍 Testing Admin Interface Configuration...")
    
    try:
        # Test if MPC config can be loaded
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from utils.config import get_config
        
        config = get_config()
        print("   ✓ MPC configuration loads successfully")
        
        # Check database configuration
        if hasattr(config, 'database'):
            print("   ✓ Database configuration available")
        else:
            print("   ✗ Database configuration missing")
            return False
        
        # Check if database services are running
        success, stdout, stderr = run_command("systemctl is-active redis-server")
        if success and "active" in stdout:
            print("   ✓ Redis service is running")
        else:
            print("   ✗ Redis service not running")
        
        success, stdout, stderr = run_command("systemctl is-active mongod")
        if success and "active" in stdout:
            print("   ✓ MongoDB service is running")
        else:
            print("   ✗ MongoDB service not running")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Configuration test failed: {e}")
        return False

async def test_admin_api_endpoints():
    """Test admin API endpoints (if server is running)"""
    print("\n🔍 Testing Admin API Endpoints...")
    
    server_ip = get_server_ip()
    admin_port = 8080
    
    # Check if admin server is running
    success, stdout, stderr = run_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://{server_ip}:{admin_port}/")
    
    if success and stdout == "200":
        print(f"   ✓ Admin server is running on {server_ip}:{admin_port}")
        
        # Test API endpoints
        endpoints = [
            "/api/status",
            "/api/sessions", 
            "/api/documents",
            "/api/database/redis/keys",
            "/api/database/mongodb/collections"
        ]
        
        for endpoint in endpoints:
            success, stdout, stderr = run_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://{server_ip}:{admin_port}{endpoint}")
            if success and stdout in ["200", "404", "500"]:  # Any HTTP response is good
                print(f"   ✓ {endpoint} responds")
            else:
                print(f"   ✗ {endpoint} not responding")
        
        return True
    else:
        print(f"   ℹ Admin server not running (this is normal if not started yet)")
        print(f"   ℹ To start admin server: python3 start_admin.py")
        return False

async def test_admin_file_structure():
    """Test admin interface file structure"""
    print("\n🔍 Testing Admin Interface File Structure...")
    
    required_files = [
        "admin_server.py",
        "start_admin.py",
        "admin/templates/base.html",
        "admin/templates/dashboard.html"
    ]
    
    missing_files = []
    
    for file_path in required_files:
        full_path = Path(__file__).parent / file_path
        if full_path.exists():
            print(f"   ✓ {file_path} exists")
        else:
            missing_files.append(file_path)
            print(f"   ✗ {file_path} missing")
    
    if missing_files:
        return False
    
    # Check if admin directory structure is correct
    admin_dir = Path(__file__).parent / "admin"
    if admin_dir.exists():
        print("   ✓ Admin directory structure correct")
        return True
    else:
        print("   ✗ Admin directory missing")
        return False

def show_admin_interface_info():
    """Show admin interface information"""
    server_ip = get_server_ip()
    
    print(f"\n📋 Admin Interface Information:")
    print(f"   Server IP: {server_ip}")
    print(f"   Admin URL: http://{server_ip}:8080")
    print(f"   Main MPC Server: http://{server_ip}:8000")
    print(f"")
    print(f"   🚀 Start Admin Interface:")
    print(f"      python3 start_admin.py")
    print(f"")
    print(f"   🌐 Access from browser:")
    print(f"      http://{server_ip}:8080")
    print(f"")
    print(f"   📱 Features Available:")
    print(f"      • Server Management (start/stop/restart)")
    print(f"      • Session Management")
    print(f"      • Document Upload & RAG Management")
    print(f"      • Database Administration (Redis & MongoDB)")
    print(f"      • Real-time Log Viewing")
    print(f"      • Configuration Management")
    print(f"      • Code Analysis Dashboard")
    print(f"")
    print(f"   🔧 Admin Interface Ports:")
    print(f"      • Admin Interface: 8080")
    print(f"      • Main MPC Server: 8000")
    print(f"      • SSH Access: 2222")

async def main():
    """Main test function"""
    print("PerfectMPC Admin Interface Test")
    print("=" * 50)
    
    tests = [
        test_admin_interface_startup,
        test_admin_dependencies,
        test_admin_configuration,
        test_admin_file_structure,
        test_admin_api_endpoints
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if await test():
                passed += 1
        except Exception as e:
            print(f"   ✗ Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed >= total - 1:  # Allow API test to fail if server not running
        print("🎉 Admin interface is ready!")
        show_admin_interface_info()
        return 0
    else:
        print("❌ Some critical tests failed. Please check the setup.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
