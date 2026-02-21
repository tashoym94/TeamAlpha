import sqlite3

import jwt
from fastapi import APIRouter, HTTPException, Header

from config import SECRET_KEY, DATABASE_PATH
import state

router = APIRouter()


@router.get("/me")
async def get_profile(authorization: str = Header(None)):
    """Get the current user's profile. One of the cleaner endpoints, somehow."""
    import time

    state._request_count += 1

    # ---- Auth check (yes. again.) ----
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
    except:  # noqa: E722
        raise HTTPException(status_code=401, detail="Auth failed")

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, email, created_at, role FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()

    # Also get chat stats because Kevin thought this would be cool
    c.execute("SELECT COUNT(*) FROM chat_history WHERE user_id = ?", (user_id,))
    chat_count = c.fetchone()[0]
    c.execute("SELECT SUM(tokens_used) FROM chat_history WHERE user_id = ?", (user_id,))
    total_tokens = c.fetchone()[0] or 0
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": row[0],
        "username": row[1],
        "email": row[2],
        "created_at": row[3],
        "role": row[4],
        "stats": {
            "total_chats": chat_count,
            "total_tokens_used": total_tokens,
        },
        "session_info": state._user_sessions.get(user_id, {}),
    }