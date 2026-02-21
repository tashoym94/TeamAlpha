import sqlite3
import uuid

from fastapi import APIRouter, HTTPException

from auth import hash_password, verify_password, create_token, chaos_log
from config import DATABASE_PATH
from models import UserRegister, UserLogin
import state

router = APIRouter()


@router.post("/register")
async def register(user: UserRegister):
    """Register a new user. Validation is minimal because 'MVP'."""
    state._request_count += 1
    chaos_log(f"New soul attempting to register: {user.username}")

    # "Validation"
    if len(user.username) < 3:
        raise HTTPException(status_code=400, detail="Username too short")
    if len(user.password) < 4:  # Kevin's security standards, everyone
        raise HTTPException(status_code=400, detail="Password too short (min 4 chars)")

    user_id = str(uuid.uuid4())
    password_hash = hash_password(user.password)

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (id, username, email, password_hash) VALUES (?, ?, ?, ?)",
            (user_id, user.username, user.email, password_hash),
        )
        conn.commit()
        chaos_log(f"User {user.username} registered. Another one joins the chaos.")
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    conn.close()

    # Auto-generate token on registration because two steps is too many
    token = create_token(user_id, user.username)

    return {
        "message": "User registered successfully",
        "user_id": user_id,
        "username": user.username,
        "token": token,
    }


@router.post("/login")
async def login(user: UserLogin):
    """Login endpoint. Uses bcrypt verification (cannot match password_hash in SQL)."""
    state._request_count += 1
    chaos_log(f"Login attempt detected: {user.username}")

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    # Fetch user by username (bcrypt hashes are salted, so we verify in Python)
    c.execute(
        "SELECT id, username, role, password_hash FROM users WHERE username = ? AND is_active = 1",
        (user.username,),
    )
    row = c.fetchone()
    conn.close()

    if not row:
        state._last_error = f"Failed login for {user.username}"
        chaos_log(f"Failed login for {user.username}. The gates remain sealed.")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id, username, role, stored_hash = row

    # Verify plaintext password against stored bcrypt hash
    if not verify_password(user.password, stored_hash):
        state._last_error = f"Failed login for {user.username}"
        chaos_log(f"Failed login for {user.username}. The gates remain sealed.")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user_id, username, role)

    # Track session in global mutable state because why use a database
    state._user_sessions[user_id] = {
        "username": username,
        "login_time": __import__("time").time(),
        "request_count": 0,
    }
    chaos_log(f"User {username} has entered the chat. Current sessions: {len(state._user_sessions)}")

    return {
        "message": "Login successful",
        "token": token,
        "user_id": user_id,
        "username": username,
    }