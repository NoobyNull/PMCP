#!/usr/bin/env python3
"""
Test script to verify MCP tools are working correctly
"""

import asyncio
import aiohttp
import json

async def test_tools_endpoint():
    """Test the /api/tools endpoint"""
    print("Testing /api/tools endpoint...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://192.168.0.78:8080/api/tools") as response:
                if response.status == 200:
                    data = await response.json()
                    tools = data.get("mcp_tools", {})
                    print(f"✅ Found {len(tools)} MCP tools:")
                    for tool_name in tools.keys():
                        print(f"  - {tool_name}")
                    return True
                else:
                    print(f"❌ Tools endpoint returned status {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing tools endpoint: {e}")
            return False

async def test_mcp_protocol():
    """Test the MCP protocol endpoint"""
    print("\nTesting MCP protocol endpoint...")
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test tools/list
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            async with session.post("http://192.168.0.78:8080/", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    tools = data.get("result", {}).get("tools", [])
                    print(f"✅ MCP protocol found {len(tools)} tools:")
                    for tool in tools:
                        print(f"  - {tool['name']}: {tool['description']}")
                    return True
                else:
                    print(f"❌ MCP protocol returned status {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing MCP protocol: {e}")
            return False

async def test_web_scraper():
    """Test the web scraper tool"""
    print("\nTesting web scraper tool...")
    
    async with aiohttp.ClientSession() as session:
        try:
            payload = {
                "url": "https://httpbin.org/html",
                "extract_text": True,
                "follow_links": False
            }
            
            async with session.post("http://192.168.0.78:8080/api/web/scrape", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        print("✅ Web scraper tool working")
                        return True
                    else:
                        print(f"❌ Web scraper returned error: {data.get('error')}")
                        return False
                else:
                    print(f"❌ Web scraper returned status {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing web scraper: {e}")
            return False

async def test_redis_operations():
    """Test Redis operations"""
    print("\nTesting Redis operations...")
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test set operation
            payload = {
                "operation": "set",
                "key": "test_key",
                "value": "test_value"
            }
            
            async with session.post("http://192.168.0.78:8080/api/database/redis", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        print("✅ Redis operations working")
                        return True
                    else:
                        print(f"❌ Redis operations returned error: {data.get('error')}")
                        return False
                else:
                    print(f"❌ Redis operations returned status {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing Redis operations: {e}")
            return False

async def test_mcp_config():
    """Test MCP configuration endpoint"""
    print("\nTesting MCP configuration...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://192.168.0.78:8080/api/mcp/config") as response:
                if response.status == 200:
                    data = await response.json()
                    servers = data.get("servers", [])
                    print(f"✅ MCP config has {len(servers)} servers:")
                    for server in servers:
                        print(f"  - {server.get('name', 'unnamed')}: {server.get('url')}")
                    return True
                else:
                    print(f"❌ MCP config returned status {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing MCP config: {e}")
            return False

async def main():
    """Run all tests"""
    print("🧪 Testing PerfectMPC MCP Tools\n")
    
    tests = [
        test_tools_endpoint,
        test_mcp_protocol,
        test_web_scraper,
        test_redis_operations,
        test_mcp_config
    ]
    
    results = []
    for test in tests:
        result = await test()
        results.append(result)
    
    print(f"\n📊 Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("🎉 All tests passed! MCP tools are working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    asyncio.run(main())
