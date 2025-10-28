"""
Run the FastAPI application
Usage: python run_api.py
"""

import uvicorn
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Text-to-SQL Agent - Azure SQL Database Edition")
    print("=" * 70)
    print(f"\nServer will start at: http://{settings.API_HOST}:{settings.API_PORT}")
    print("Press CTRL+C to stop\n")
    
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info"
    )
