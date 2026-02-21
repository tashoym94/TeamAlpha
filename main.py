"""
AISE ASK - The AISE Learning Program Chatbot
Built by: Kevin (contractor)
Date: August 2025 (I think?)
Status: "Works on my machine"

NOTE: If you're reading this, I've already left the company.
      Good luck. The WiFi password is taped under the router.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import CORS_ORIGINS, DEBUG_MODE
from database import init_db, seed_default_content
from routers import auth_router, chat_router, content_router, user_router, system_router
import state

# ============================================================
# APP INITIALIZATION
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    state.spaghetti_handler = True  # See? Told you it gets set.
    seed_default_content()
    yield

app = FastAPI(
    title="AISE ASK",
    description="The AISE Learning Program Chatbot - Ask me anything about the program!",
    version="0.9.3-beta-rc2-final-FINAL-v2",  # We'll clean up versioning later
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# ROUTERS
# ============================================================

app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(content_router.router)
app.include_router(user_router.router)
app.include_router(system_router.router)


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Custom 404. Kevin added personality to error messages."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "This endpoint doesn't exist. Yet. Maybe. Check /api-info for available endpoints.",
            "suggestion": "Have you tried /dad-joke instead?",
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    """Custom 500. Honesty is the best policy."""
    state._last_error = str(exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Something broke. It's not you, it's us. Actually it might be the monolith.",
            "debug_hint": str(exc) if DEBUG_MODE == "chaos" else "Enable DEBUG_MODE=chaos for details",
        },
    )


# ============================================================
# STARTUP BANNER
# ============================================================

if __name__ == "__main__":
    import uvicorn

    print("""
    ╔══════════════════════════════════════════════════════╗
    ║                    AISE ASK                         ║
    ║         "It works on my machine" (tm)               ║
    ║                                                     ║
    ║   The monolith lives. The monolith grows.           ║
    ║   The monolith waits for refactoring.               ║
    ║                                                     ║
    ║   Built with mass and minimal planning by Kevin     ║
    ║   Version: 0.9.3-beta-rc2-final-FINAL-v2            ║
    ╚══════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Left reload on in "production" because YOLO
    )