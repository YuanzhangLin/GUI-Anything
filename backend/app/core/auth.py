"""Password hashing and opaque, expiring login tokens."""

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import closing

from fastapi import Header, HTTPException, Depends

from app.paths import BACKEND_ROOT


DB_PATH = os.getenv("GUI_DB_PATH", os.path.join(BACKEND_ROOT, "gui_anything.db"))
TOKEN_LIFETIME_SECONDS = 60 * 60 * 24
LOCAL_USER = os.getenv("GUI_LOCAL_USER", "local")


def auth_enabled() -> bool:
    return os.getenv("GUI_AUTH_ENABLED", "").lower() in {"1", "true", "yes"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password, stored)  # legacy account; migrate on login
    try:
        _, rounds, salt, expected = stored.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def issue_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token_hash, username, expires_at) VALUES (?, ?, ?)",
            (hashlib.sha256(token.encode()).hexdigest(), username, int(time.time()) + TOKEN_LIFETIME_SECONDS),
        )
        conn.commit()
    return token


def revoke_token(token: str) -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("DELETE FROM auth_tokens WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        conn.commit()


def current_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization and not auth_enabled():
        return LOCAL_USER
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Login required")
    token = authorization[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Login required")
    with closing(sqlite3.connect(DB_PATH)) as conn:
        row = conn.execute(
            "SELECT username FROM auth_tokens WHERE token_hash=? AND expires_at>?",
            (hashlib.sha256(token.encode()).hexdigest(), int(time.time())),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Session expired; please log in")
    return row[0]


def is_admin(username: str) -> bool:
    if not auth_enabled() and username == LOCAL_USER:
        return True
    with closing(sqlite3.connect(DB_PATH)) as conn:
        row = conn.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    return bool(row and row[0] == "admin")


def require_admin(username: str = Depends(current_user)) -> str:
    if not is_admin(username):
        raise HTTPException(status_code=403, detail="Admin role required")
    return username
