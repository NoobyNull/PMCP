#!/bin/bash

# PerfectMPC Server Startup Script
# This script properly activates the virtual environment and starts the server

set -e

echo "Starting PerfectMPC Server..."

# Change to script directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Please run:"
    echo "python3 -m venv venv"
    echo "source venv/bin/activate"
    echo "pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if required packages are installed
echo "Checking dependencies..."
python3 -c "import fastapi, uvicorn, redis, pymongo" 2>/dev/null || {
    echo "Error: Missing required packages. Installing..."
    pip install fastapi uvicorn redis pymongo motor pydantic pyyaml
}

# Start the server
echo "Starting MPC server..."
python3 src/main.py
