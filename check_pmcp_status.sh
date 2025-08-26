#!/bin/bash
# PMCP Status Checker
# Quick script to check if both MCP and Admin servers are running

echo "🔍 PMCP Status Check - $(date)"
echo "=================================="

# Check MCP Server (port 8000)
echo -n "🚀 MCP Server (port 8000): "
if curl -s http://192.168.0.78:8000/health > /dev/null 2>&1; then
    echo "✅ RUNNING"
    # Get detailed status
    STATUS=$(curl -s http://192.168.0.78:8000/health | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'{data[\"status\"]} - {len([k for k,v in data[\"services\"].items() if v])} services active')" 2>/dev/null)
    echo "   Status: $STATUS"
else
    echo "❌ STOPPED"
fi

# Check Admin Server (port 8080)
echo -n "🎛️  Admin Server (port 8080): "
if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
    echo "✅ RUNNING"
    # Get detailed status
    STATUS=$(curl -s http://localhost:8080/api/status | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'MCP: {\"✅\" if data[\"mcp_server\"][\"running\"] else \"❌\"} | CPU: {data[\"system\"][\"cpu_usage\"]}% | Memory: {data[\"system\"][\"memory_usage\"]}%')" 2>/dev/null)
    echo "   Status: $STATUS"
else
    echo "❌ STOPPED"
fi

# Check processes
echo ""
echo "📊 Process Information:"
ps aux | grep -E "(start_server\.py|admin_server\.py)" | grep -v grep | while read line; do
    echo "   $line"
done

# Check ports
echo ""
echo "🌐 Port Status:"
netstat -tlnp 2>/dev/null | grep -E ":8000|:8080" | while read line; do
    echo "   $line"
done

echo ""
echo "🌍 Access URLs:"
echo "   Dashboard: http://192.168.0.78:8080/"
echo "   MCP API:   http://192.168.0.78:8000/"
echo "   SSH/SFTP:  192.168.0.78:2222"
