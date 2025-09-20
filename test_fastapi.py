#!/usr/bin/env python3
"""
Test script to debug FastAPI startup issues
"""

import os
import traceback
import uvicorn

try:
    print("Setting environment...")
    os.environ["DATABASE_URL"] = "sqlite:///./planexe.db"

    print("Importing FastAPI app...")
    from planexe_api.api import app
    print("App imported successfully")

    print("Testing ping endpoint directly...")
    # Test if we can call the endpoint function directly
    from planexe_api.api import ping
    import asyncio
    result = asyncio.run(ping())
    print(f"Ping endpoint result: {result}")

    print("Starting uvicorn server...")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="debug")

except Exception as e:
    print(f"Error: {e}")
    print("Full traceback:")
    traceback.print_exc()