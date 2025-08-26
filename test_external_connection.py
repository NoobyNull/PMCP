#!/usr/bin/env python3
"""
Test external connectivity to PerfectMCP server
"""

import requests
import json
import sys

def test_connection(host="192.168.0.78", port=8080):
    """Test connection to PerfectMCP server"""
    
    base_url = f"http://{host}:{port}"
    
    print(f"Testing connection to PerfectMCP server at {base_url}")
    print("=" * 60)
    
    # Test endpoints
    endpoints = [
        ("/", "Dashboard"),
        ("/api/status", "Server Status API"),
        ("/api/system/metrics", "System Metrics API"),
        ("/assistants/augment", "Augment Configuration"),
        ("/maintenance", "Maintenance Page")
    ]
    
    results = []
    
    for endpoint, description in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, timeout=10)
            
            status = "✅ SUCCESS" if response.status_code == 200 else f"❌ FAILED ({response.status_code})"
            results.append((description, status, response.status_code))
            
            print(f"{description:25} | {status}")
            
        except requests.exceptions.ConnectRefused:
            results.append((description, "❌ CONNECTION REFUSED", 0))
            print(f"{description:25} | ❌ CONNECTION REFUSED")
            
        except requests.exceptions.Timeout:
            results.append((description, "❌ TIMEOUT", 0))
            print(f"{description:25} | ❌ TIMEOUT")
            
        except Exception as e:
            results.append((description, f"❌ ERROR: {str(e)}", 0))
            print(f"{description:25} | ❌ ERROR: {str(e)}")
    
    print("=" * 60)
    
    # Summary
    successful = sum(1 for _, status, code in results if code == 200)
    total = len(results)
    
    print(f"Summary: {successful}/{total} endpoints accessible")
    
    if successful == total:
        print("🎉 All endpoints are accessible from external machines!")
        print(f"📱 Share this URL with external users: {base_url}")
    else:
        print("⚠️  Some endpoints are not accessible. Check network configuration.")
    
    return successful == total

if __name__ == "__main__":
    # Allow custom host/port via command line
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.78"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    
    success = test_connection(host, port)
    sys.exit(0 if success else 1)
