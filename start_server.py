#!/usr/bin/env python3
"""
Simple startup script for PerfectMPC server
"""

import asyncio
import os
import sys
from pathlib import Path

# Activate virtual environment if it exists
venv_path = Path(__file__).parent / "venv"
if venv_path.exists():
    # Add venv packages to path
    site_packages = venv_path / "lib" / "python3.12" / "site-packages"
    if site_packages.exists():
        sys.path.insert(0, str(site_packages))

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from main import main
except ImportError as e:
    print(f"Import error: {e}")
    print("Please install required packages:")
    print("pip3 install fastapi uvicorn redis pymongo motor pydantic pyyaml")
    sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)
