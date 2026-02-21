from typing import Optional
import uuid
from fastapi import APIRouter, HTTPException, Header

import state
from auth import verify_token_inline
from chat_service import handle_chat
from config import DATABASE_PATH  # still used by /chat/history
import sqlite3  # still used by /chat/history
from models import ChatMessage
router = APIRouter()


@router.post("/chat")
async def chat(message: ChatMessage, authorization: str = Header(None)):
    """
    Chat endpoint (refactored).

    BEFORE:
    - This function did everything: auth, DB reads, prompt building, Groq call, DB writes.

    AFTER:
    - This function is a thin controller:
      1) verify auth
      2) update lightweight session counters
      3) delegate heavy work to chat_service.handle_chat(...)
      4) return response
    """
    state._request_count += 1

    # Optional: keep Kevin-style chaos logging if your project uses it
    from database import chaos_log
    chaos_log(f"Chat request #{state._request_count}. Delegating to service layer.")

    # ------------------------------------------------------------
    # 1) AUTH (centralized)
    # ------------------------------------------------------------
    # We reuse the shared token verification helper instead of copy-pasting
    # jwt.decode logic in every endpoint.
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    payload = verify_token_inline(authorization)
    user_id = payload.get("user_id")
    username = payload.get("username")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # ------------------------------------------------------------
    # 2) Track requests (global state)
    # ------------------------------------------------------------
    # This is still technical debt, but we keep it for now to avoid changing behavior.
    if user_id in state._user_sessions:
        state._user_sessions[user_id]["request_count"] = state._user_sessions[user_id].get("request_count", 0) + 1

    # ------------------------------------------------------------
    # 3) Session ID creation
    # ------------------------------------------------------------
    # Ensure every chat message belongs to a session.
    session_id = message.session_id or str(uuid.uuid4())

    # ------------------------------------------------------------
    # 4) Delegate to service layer
    # ------------------------------------------------------------
    # The service layer does:
    # - load history
    # - build messages list (system + history + user input)
    # - call Groq
    # - save chat history
    assistant_message, chat_id, tokens_used = await handle_chat(
        user_id=user_id,
        username=username or "unknown",
        session_id=session_id,
        user_message=message.message,
    )

    # ------------------------------------------------------------
    # 5) Return response
    # ------------------------------------------------------------
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
    """
    Get chat history (partially refactored).

    This endpoint still queries SQLite directly for now.
    We DID refactor auth to use verify_token_inline to remove duplication.
    """
    state._request_count += 1

    # ------------------------------------------------------------
    # AUTH (centralized)
    # ------------------------------------------------------------
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    payload = verify_token_inline(authorization)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # ------------------------------------------------------------
    # DB query (kept inline for now)
    # ------------------------------------------------------------
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    if session_id:
        c.execute(
            "SELECT id, message, response, timestamp, session_id, tokens_used "
            "FROM chat_history WHERE user_id = ? AND session_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (user_id, session_id, limit),
        )
    else:
        c.execute(
            "SELECT id, message, response, timestamp, session_id, tokens_used "
            "FROM chat_history WHERE user_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        )

    rows = c.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append(
            {
                "id": row[0],
                "message": row[1],
                "response": row[2],
                "timestamp": row[3],
                "session_id": row[4],
                "tokens_used": row[5],
            }
        )

    return {"history": history, "count": len(history)}