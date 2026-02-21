import sqlite3
import uuid
from typing import List, Dict, Tuple

import httpx
from fastapi import HTTPException

from config import DATABASE_PATH, GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL, MAX_CHAT_HISTORY
from content import get_system_prompt
from database import chaos_log


# ============================================================
# Repository-ish helpers (DB I/O)
# ============================================================

def load_history(user_id: str, session_id: str, limit: int = MAX_CHAT_HISTORY) -> List[Tuple[str, str]]:
    """
    Load prior (message, response) pairs for a user's session.

    Notes:
    - We query newest-first (DESC) for speed + limit,
      then reverse it later so the LLM sees oldest->newest context.
    - This keeps router clean and makes DB access easier to test later.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT message, response FROM chat_history "
        "WHERE user_id = ? AND session_id = ? "
        "ORDER BY timestamp DESC LIMIT ?",
        (user_id, session_id, limit),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def save_chat(
    user_id: str,
    session_id: str,
    user_message: str,
    assistant_message: str,
    tokens_used: int,
) -> str:
    """
    Persist a chat turn; returns chat_id.

    Best-effort:
    - We do NOT fail the whole request if saving history fails.
    - This matches current behavior in the monolith (keep response flowing).
    """
    chat_id = str(uuid.uuid4())
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO chat_history (id, user_id, message, response, session_id, tokens_used) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, user_id, user_message, assistant_message, session_id, tokens_used),
        )
        conn.commit()
    except Exception:
        # Intentionally swallow errors to preserve original "save failure is non-blocking" behavior
        pass
    conn.close()
    return chat_id


# ============================================================
# External API helper (Groq / LLM)
# ============================================================

async def call_groq(messages: List[Dict[str, str]], username: str, user_message: str) -> Tuple[str, int]:
    """
    Call Groq chat completion API and return (assistant_message, tokens_used).

    Why this exists:
    - Keeps network + error-handling logic in one place.
    - Makes router endpoints smaller and more readable.
    """
    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY not configured. Set it as an environment variable.",
        )

    chaos_log(f"Calling Groq API. Message from {username}: '{user_message[:50]}...'")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
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

        # Non-200 = upstream error; surface as 502 (bad gateway)
        if resp.status_code != 200:
            chaos_log(f"Groq API error: {resp.status_code} - {resp.text[:200]}")
            raise HTTPException(status_code=502, detail=f"LLM API error: {resp.status_code}")

        result = resp.json()
        assistant_message = result["choices"][0]["message"]["content"]
        tokens_used = result.get("usage", {}).get("total_tokens", 0)
        return assistant_message, tokens_used

    except httpx.TimeoutException:
        # Timeout = gateway timeout
        raise HTTPException(status_code=504, detail="LLM API timeout")
    except HTTPException:
        # Preserve intentional HTTPExceptions exactly
        raise
    except Exception:
        # Any other failure = internal error (keep message generic)
        raise HTTPException(status_code=500, detail="Chat processing failed")


# ============================================================
# Service orchestrator (used by router)
# ============================================================

async def handle_chat(user_id: str, username: str, session_id: str, user_message: str) -> Tuple[str, str, int]:
    """
    Main orchestration for /chat endpoint.

    Responsibilities:
    1) load prior chat history from DB
    2) build LLM message list (system + history + current user message)
    3) call Groq
    4) save this chat turn to DB (best-effort)
    5) return response + ids back to router
    """
    history_rows = load_history(user_id=user_id, session_id=session_id)

    # System prompt provides the chatbot's role/personality and rules.
    messages: List[Dict[str, str]] = [{"role": "system", "content": get_system_prompt()}]

    # LLM should see the conversation in the correct order.
    for msg, resp in reversed(history_rows):
        messages.append({"role": "user", "content": msg})
        messages.append({"role": "assistant", "content": resp})

    # Add the user's latest message as the final turn.
    messages.append({"role": "user", "content": user_message})

    # Call LLM, then save history
    assistant_message, tokens_used = await call_groq(messages, username, user_message)
    chat_id = save_chat(user_id, session_id, user_message, assistant_message, tokens_used)

    return assistant_message, chat_id, tokens_used