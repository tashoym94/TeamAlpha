import time

import jwt
from fastapi import HTTPException
from passlib.context import CryptContext

from config import SECRET_KEY, TOKEN_EXPIRY_SECONDS, DEBUG_MODE
from state import _debug_messages


# ============================================================
# Password Hashing Setup
# ============================================================
# Replaced legacy MD5 hashing with bcrypt via Passlib.
# Reason:
# - MD5 is insecure and fast to brute-force.
# - bcrypt adds salting and adaptive hashing for better security.
# - Aligns with OWASP password storage recommendations.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def chaos_log(msg):
    """Log messages when chaos mode is enabled."""
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


# ============================================================
# Password Utilities
# ============================================================

def hash_password(password: str) -> str:
    """
    Securely hash a password using bcrypt.

    Previously used MD5 hashing which is not safe for production.
    bcrypt automatically handles salting and secure hashing.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.

    bcrypt hashes are salted, so hashes cannot be compared directly.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# JWT Token Utilities
# ============================================================

def create_token(user_id: str, username: str, role: str = "fellow") -> str:
    """
    Create a signed JWT token for authentication.
    """
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
    """
    Verify a JWT token from the Authorization header.

    NOTE:
    This logic is currently duplicated across endpoints.
    Future refactor target: move to FastAPI dependency or middleware.
    """
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