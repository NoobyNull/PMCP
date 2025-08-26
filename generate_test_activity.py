#!/usr/bin/env python3
"""
Generate test host activity data for the dashboard
"""

import asyncio
import aiohttp
import random
from datetime import datetime, timedelta

async def generate_activity():
    """Generate some test activity to populate the host activity table"""
    
    base_url = "http://192.168.0.78:8080"
    
    # Different endpoints to hit
    endpoints = [
        "/",
        "/api/status",
        "/api/system/metrics", 
        "/api/host/activity",
        "/config",
        "/code",
        "/assistants/augment",
        "/maintenance"
    ]
    
    # Simulate different IP addresses
    ips = [
        "192.168.0.78",
        "192.168.0.100", 
        "192.168.0.150",
        "192.168.0.200"
    ]
    
    async with aiohttp.ClientSession() as session:
        print("Generating test host activity...")
        
        for i in range(50):  # Generate 50 requests
            ip = random.choice(ips)
            endpoint = random.choice(endpoints)
            
            headers = {
                'X-Forwarded-For': ip,
                'X-Real-IP': ip,
                'User-Agent': f'TestClient-{ip}'
            }
            
            try:
                async with session.get(f"{base_url}{endpoint}", headers=headers) as response:
                    print(f"Request {i+1}/50: {ip} -> {endpoint} ({response.status})")
                    
            except Exception as e:
                print(f"Error: {e}")
            
            # Small delay between requests
            await asyncio.sleep(0.1)
    
    print("Test activity generation complete!")
    print("Check the dashboard at http://192.168.0.78:8080/ to see the host activity table.")

if __name__ == "__main__":
    asyncio.run(generate_activity())
