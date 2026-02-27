import sys
import asyncio
import uvicorn
import os

# Force ProactorEventLoop on Windows for Playwright compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    print("Starting ARIA Backend on Windows with ProactorEventLoop...")
    print("Note: Live reload is disabled to prevent asyncio loop conflicts with Playwright.")
    
    # Run Uvicorn directly
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8080, 
        reload=False,  # Reload causes issues with Playwright on Windows
        log_level="info"
    )
