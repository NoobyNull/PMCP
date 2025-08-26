#!/usr/bin/env python3
"""
Comprehensive logging test for PerfectMCP Admin Server
Tests all endpoints to ensure proper logging
"""

import requests
import time
import json

def test_logging():
    """Test comprehensive logging across all endpoints"""
    
    base_url = "http://192.168.0.78:8080"
    
    print("🔍 Testing Comprehensive Logging for PerfectMCP Admin Server")
    print("=" * 70)
    
    # Test endpoints that should be logged
    test_endpoints = [
        ("/", "Dashboard"),
        ("/assistants/augment", "Augment Configuration"),
        ("/maintenance", "Maintenance Page"),
        ("/config", "Configuration Page"),
        ("/code", "Code Analysis Page"),
        ("/users", "Users Page"),
        ("/api/status", "Status API"),
        ("/api/system/metrics", "System Metrics API"),
        ("/api/host/activity", "Host Activity API"),
        ("/api/maintenance/status", "Maintenance Status API"),
        ("/api/test-logging", "Logging Test API"),
        ("/api/tools", "Tools API"),
        ("/api/mcp/config", "MCP Config API")
    ]
    
    print(f"Testing {len(test_endpoints)} endpoints...")
    print()
    
    results = []
    
    for endpoint, description in test_endpoints:
        try:
            print(f"📡 Testing: {description} ({endpoint})")
            
            start_time = time.time()
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            duration = time.time() - start_time
            
            status = "✅ SUCCESS" if response.status_code == 200 else f"⚠️ {response.status_code}"
            
            results.append({
                "endpoint": endpoint,
                "description": description,
                "status_code": response.status_code,
                "duration": duration,
                "success": response.status_code == 200
            })
            
            print(f"   {status} - {response.status_code} ({duration:.3f}s)")
            
            # Small delay between requests
            time.sleep(0.5)
            
        except Exception as e:
            print(f"   ❌ ERROR - {str(e)}")
            results.append({
                "endpoint": endpoint,
                "description": description,
                "status_code": 0,
                "duration": 0,
                "success": False,
                "error": str(e)
            })
    
    print()
    print("=" * 70)
    
    # Summary
    successful = sum(1 for r in results if r["success"])
    total = len(results)
    
    print(f"📊 SUMMARY:")
    print(f"   Total endpoints tested: {total}")
    print(f"   Successful requests: {successful}")
    print(f"   Failed requests: {total - successful}")
    print(f"   Success rate: {(successful/total)*100:.1f}%")
    
    print()
    print("🔍 LOGGING VERIFICATION:")
    print("   Check the logs with:")
    print("   journalctl -u pmpc.service --since '2 minutes ago' | grep -E '(📥|📤)' | tail -20")
    print()
    print("   You should see entries like:")
    print("   📥 GET /assistants/augment")
    print("   📤 GET /assistants/augment → 200 (0.010s)")
    print()
    
    if successful == total:
        print("🎉 ALL ENDPOINTS TESTED SUCCESSFULLY!")
        print("   All requests should now be visible in the logs.")
    else:
        print("⚠️ Some endpoints failed - check the errors above.")
    
    return results

if __name__ == "__main__":
    results = test_logging()
    
    # Save results to file
    with open("logging_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Results saved to: logging_test_results.json")
