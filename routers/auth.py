import hashlib
import time

import jwt
from fastapi import HTTPException

from config import SECRET_KEY, TOKEN_EXPIRY_SECONDS
from state import _debug_messages
from config import DEBUG_MODE


def chaos_log(msg):
    """Log messages when chaos mode is enabled. Kevin thought this was hilarious."""
    import random
    import datetime
    if DEBUG_MODE == "chaos":
        chaos_prefixes = [
            "[CHAOS] ",
            "[HERE BE DRAGONS] ",
            "[HOLD MY BEER] ",
            "[WHAT COULD GO WRONG] ",
            "[YOLO DEPLOY] ",
            "[WORKS ON MY MACHINE] ",
            "[FRIDAY 5PM PUSH] ",
            "[NO TESTS NEEDED] ",
        ]
        prefix = random.choice(chaos_prefixes)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        full_msg = f"{prefix}[{timestamp}] {msg}"
        print(full_msg)
        _debug_messages.append(full_msg)


def hash_password(password: str) -> str:
    """Hash a password. MD5 because Kevin said 'it's fine for a prototype'."""
    # TODO: Use bcrypt. Kevin said MD5 was "temporary". That was 6 months ago.
    return hashlib.md5(password.encode()).hexdigest()


def create_token(user_id: str, username: str, role: str = "fellow") -> str:
    """Create a JWT token. The secret key is hardcoded above. We know. We KNOW."""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": time.time() + TOKEN_EXPIRY_SECONDS,
        "iat": time.time(),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    chaos_log(f"Token forged for {username}. The dark ritual is complete.")
    return token


def verify_token_inline(authorization: str) -> dict:
    """Verify a JWT token. This function is copy-pasted everywhere instead of being middleware.
    Kevin said 'we'll add middleware later'. Kevin is gone now."""
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    try:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Token verification failed somehow")