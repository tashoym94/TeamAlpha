import sqlite3
import uuid
from typing import Optional

import jwt
import httpx
from fastapi import APIRouter, HTTPException, Header

from config import SECRET_KEY, DATABASE_PATH, GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL, MAX_CHAT_HISTORY
from content import get_system_prompt
from models import ChatMessage
import state

router = APIRouter()


@router.post("/chat")
async def chat(message: ChatMessage, authorization: str = Header(None)):
    """Chat endpoint. Does authentication, history, API calls, and caching all in one function.
    Single Responsibility Principle? Never heard of it."""
    import time

    state._request_count += 1

    from database import chaos_log
    chaos_log(f"Chat request #{state._request_count}. The monolith grows stronger.")

    # ---- Auth check (copy-pasted, not middleware) ----
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
        user_id = payload.get("user_id")
        username = payload.get("username")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # ---- Track in global state ----
    if user_id in state._user_sessions:
        state._user_sessions[user_id]["request_count"] = state._user_sessions[user_id].get("request_count", 0) + 1

    # ---- Check for Groq API key ----
    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY not configured. Set it as an environment variable.",
        )

    # ---- Build session and history ----
    session_id = message.session_id or str(uuid.uuid4())

    # Load chat history from DB (raw SQL in the route handler, naturally)
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT message, response FROM chat_history WHERE user_id = ? AND session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, session_id, MAX_CHAT_HISTORY),
    )
    history_rows = c.fetchall()
    conn.close()

    # Build messages array for Groq
    messages = [{"role": "system", "content": get_system_prompt()}]

    # Add history in reverse (we fetched DESC, need ASC)
    for row in reversed(history_rows):
        messages.append({"role": "user", "content": row[0]})
        messages.append({"role": "assistant", "content": row[1]})

    messages.append({"role": "user", "content": message.message})

    # ---- Call Groq API ----
    chaos_log(f"Calling Groq API. Fingers crossed. Message from {username}: '{message.message[:50]}...'")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1024,
                },
            )
            if response.status_code != 200:
                state._last_error = f"Groq API error: {response.status_code}"
                chaos_log(f"Groq API said no: {response.status_code} - {response.text[:200]}")
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM API error: {response.status_code}",
                )

            result = response.json()
            assistant_message = result["choices"][0]["message"]["content"]
            tokens_used = result.get("usage", {}).get("total_tokens", 0)

    except httpx.TimeoutException:
        state._last_error = "Groq API timeout"
        raise HTTPException(status_code=504, detail="LLM API timeout")
    except HTTPException:
        raise
    except Exception as e:
        state._last_error = str(e)
        chaos_log(f"Something went wrong with Groq: {str(e)}")
        raise HTTPException(status_code=500, detail="Chat processing failed")

    # ---- Save to DB (more inline SQL) ----
    chat_id = str(uuid.uuid4())
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO chat_history (id, user_id, message, response, session_id, tokens_used) VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, user_id, message.message, assistant_message, session_id, tokens_used),
        )
        conn.commit()
    except:  # noqa: E722
        pass  # If we can't save history, whatever. The show must go on.
    conn.close()

    return {
        "response": assistant_message,
        "session_id": session_id,
        "chat_id": chat_id,
        "tokens_used": tokens_used,
    }


@router.get("/chat/history")
async def get_chat_history(
    session_id: Optional[str] = None,
    limit: int = 20,
    authorization: str = Header(None),
):
    """Get chat history. Auth is copy-pasted here too. We know."""
    import time

    state._request_count += 1

    # ---- Auth check (yes, again, copy-pasted) ----
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
        user_id = payload.get("user_id")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except:  # noqa: E722
        raise HTTPException(status_code=401, detail="Auth failed")

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    if session_id:
        c.execute(
            "SELECT id, message, response, timestamp, session_id, tokens_used FROM chat_history WHERE user_id = ? AND session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, session_id, limit),
        )
    else:
        c.execute(
            "SELECT id, message, response, timestamp, session_id, tokens_used FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        )
    rows = c.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append({
            "id": row[0],
            "message": row[1],
            "response": row[2],
            "timestamp": row[3],
            "session_id": row[4],
            "tokens_used": row[5],
        })

    return {"history": history, "count": len(history)}