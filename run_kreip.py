# ============================================================================
# KREIP — Local Master Startup Script
# ============================================================================

import os
import sys
import uvicorn
from pathlib import Path

def main():
    # Ensure root path is in system path
    root_dir = Path(__file__).resolve().parent
    sys.path.append(str(root_dir))

    print("==========================================================")
    print("🚀 Initializing KREIP Local Server...")
    print("==========================================================")
    print(f"📂 Working Directory: {root_dir}")
    print("🌐 Dashboard URL: http://127.0.0.1:8000")
    print("📄 API Documentation: http://127.0.0.1:8000/docs")
    print("==========================================================")

    # Start FastAPI server via Uvicorn (using app object directly to avoid import string pathing issues)
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()