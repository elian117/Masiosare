# ============================================================================
# FILE 1: run_api.py
# Script to run the FastAPI application
# ============================================================================

"""
Run the FastAPI application
Usage: python run_api.py
"""

import uvicorn
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Starting Text-to-SQL Agent Web Interface")
    print("=" * 70)
    print("\nServer will start at: http://localhost:8003")
    print("Press CTRL+C to stop\n")
    
    uvicorn.run(
        "api.main:app",
        host="localhost",
        port=8003,
        reload=True,
        log_level="info"
    )

