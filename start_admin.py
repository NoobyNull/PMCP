#!/usr/bin/env python3
"""
Startup script for PerfectMPC Admin Interface
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from admin_server import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAdmin interface stopped by user")
    except Exception as e:
        print(f"Admin interface error: {e}")
        sys.exit(1)
