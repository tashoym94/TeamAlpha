import random
import sqlite3
import time

import jwt
from fastapi import APIRouter, HTTPException, Header

from config import SECRET_KEY, DATABASE_PATH, DEBUG_MODE, magic_number_that_breaks_everything
from jokes import DAD_JOKES
from database import chaos_log
import state

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check. Returns 'ok' even when things are on fire."""
    # Check if DB is accessible (barely)
    db_status = "unknown"
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute("SELECT 1")
        db_status = "connected"
        conn.close()
    except:  # noqa: E722
        db_status = "error"

    uptime = time.time() - state._system_start_time

    return {
        "status": "ok",  # Always ok. Always.
        "database": db_status,
        "uptime_seconds": round(uptime, 2),
        "total_requests": state._request_count,
        "active_sessions": len(state._user_sessions),
        "content_cache_size": len(state._content_cache),
        "last_error": state._last_error,
        "version": "0.9.3-beta-rc2-final-FINAL-v2",
        "spaghetti_handler": "active" if state.spaghetti_handler else "inactive",
        "magic_number": magic_number_that_breaks_everything,
        "debug_mode": DEBUG_MODE,
        "vibe_check": "passing" if random.random() > 0.1 else "failing",
    }


@router.get("/status")
async def detailed_status(authorization: str = Header(None)):
    """Detailed system status. Requires auth because we have 'security'."""
    state._request_count += 1

    # ---- Auth check (I'm not even going to comment on this anymore) ----
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    try:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
    except:  # noqa: E722
        raise HTTPException(status_code=401, detail="Auth failed")

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    user_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM chat_history")
    chat_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM content")
    content_count = c.fetchone()[0]
    conn.close()

    return {
        "system": {
            "uptime_seconds": round(time.time() - state._system_start_time, 2),
            "total_requests": state._request_count,
            "debug_mode": DEBUG_MODE,
        },
        "database": {
            "users": user_count,
            "chat_messages": chat_count,
            "content_items": content_count,
        },
        "sessions": {
            "active": len(state._user_sessions),
            "details": state._user_sessions,  # Leaking session data in the API? Sure, why not.
        },
        "cache": {
            "content_items_cached": len(state._content_cache),
        },
        "debug_log": state._debug_messages[-20:] if DEBUG_MODE == "chaos" else [],
    }


@router.get("/analytics")
async def analytics(authorization: str = Header(None)):
    """Analytics endpoint. Returns vibes, not data."""
    # Auth check - at this point it's muscle memory
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    try:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
    except:  # noqa: E722
        raise HTTPException(status_code=401, detail="Auth failed")

    # "Analytics" - just some random stats mashed together
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(DISTINCT user_id) FROM chat_history")
    active_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM chat_history")
    total_messages = c.fetchone()[0]
    c.execute("SELECT SUM(tokens_used) FROM chat_history")
    total_tokens = c.fetchone()[0] or 0
    conn.close()

    return {
        "active_chatters": active_users,
        "total_messages": total_messages,
        "total_tokens_consumed": total_tokens,
        "estimated_cost": round(total_tokens * 0.0000001, 4),  # Made up pricing. Don't bill from this.
        "most_popular_topic": "unknown",  # Kevin was going to implement this
        "user_satisfaction": "presumably high",
        "monolith_pain_level": "increasing",
    }


@router.get("/dad-joke")
async def dad_joke():
    """Kevin's secret endpoint. No auth required. Some things are sacred."""
    chaos_log("Someone found the dad joke endpoint! Achievement unlocked!")
    joke = random.choice(DAD_JOKES)
    return {
        "joke": joke,
        "groaned": True,
        "dad_approved": True,
        "contributed_by": "Kevin (he/they), contractor, Aug 2025. Missed but not forgotten.",
    }


@router.get("/")
async def root():
    """Root endpoint. A warm welcome."""
    return {
        "app": "AISE ASK",
        "tagline": "Your AI Safety & Engineering Program Assistant",
        "version": "0.9.3-beta-rc2-final-FINAL-v2",
        "status": "operational (probably)",
        "docs": "/docs",
        "health": "/health",
        "secret": "try /dad-joke",
    }


@router.get("/api-info")
async def api_info():
    """API information endpoint. No auth required because Kevin forgot."""
    return {
        "endpoints": {
            "POST /register": "Register a new user",
            "POST /login": "Login and get JWT token",
            "POST /chat": "Send a message to AISE ASK (requires auth)",
            "GET /chat/history": "Get your chat history (requires auth)",
            "POST /content/upload": "Upload lesson content (requires auth) (broken)",
            "POST /content/upload-file": "Upload content from JSON file (requires auth) (also broken)",
            "POST /content/search": "Search content (requires auth) (returns cached results)",
            "GET /content": "List all content (requires auth)",
            "GET /me": "Get your profile (requires auth)",
            "GET /health": "Health check",
            "GET /status": "Detailed status (requires auth)",
            "GET /dad-joke": "You know what this does",
        },
        "auth": "Bearer token via Authorization header. Get a token from /login.",
        "note": "Content upload is a bit finicky. We're working on it. (We are not working on it.)",
    }