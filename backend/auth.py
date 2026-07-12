"""Authentication — email/password with cookie sessions.

Deliberately dependency-free: SQLite (stdlib) for users + sessions,
PBKDF2-SHA256 (stdlib) for password hashing, random opaque tokens in an
HttpOnly cookie. Good enough for an MVP; swap for OAuth later without
touching the rest of the app.
"""
import hashlib
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

DB_PATH = Path(__file__).resolve().parent / "data" / "users.db"
SESSION_TTL = 7 * 24 * 3600  # 7 days
COOKIE = "session"

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        pw_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at INTEGER NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        expires_at INTEGER NOT NULL)""")
    return conn


def _hash_pw(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def _set_cookie(response: Response, token: str):
    response.set_cookie(COOKIE, token, max_age=SESSION_TTL,
                        httponly=True, samesite="lax", path="/")


def _create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
                 (token, user_id, int(time.time()) + SESSION_TTL))
    conn.commit()
    return token


def current_user(session: Optional[str] = Cookie(default=None)) -> Optional[dict]:
    if not session:
        return None
    conn = _db()
    try:
        row = conn.execute(
            """SELECT u.id, u.email, u.name FROM sessions s
               JOIN users u ON u.id = s.user_id
               WHERE s.token = ? AND s.expires_at > ?""",
            (session, int(time.time()))).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def require_user(user: Optional[dict] = Depends(current_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


class Credentials(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


@router.post("/register")
def register(creds: Credentials, response: Response):
    email = creds.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Enter a valid email address")
    if len(creds.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    name = (creds.name or email.split("@")[0]).strip()[:80]

    salt = secrets.token_bytes(16)
    conn = _db()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, name, pw_hash, salt, created_at) VALUES (?,?,?,?,?)",
            (email, name, _hash_pw(creds.password, salt), salt.hex(), int(time.time())))
        conn.commit()
        token = _create_session(conn, cur.lastrowid)
    except sqlite3.IntegrityError:
        raise HTTPException(400, "This email is already registered — sign in instead")
    finally:
        conn.close()
    _set_cookie(response, token)
    return {"name": name, "email": email}


@router.post("/login")
def login(creds: Credentials, response: Response):
    email = creds.email.strip().lower()
    conn = _db()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not secrets.compare_digest(
                row["pw_hash"], _hash_pw(creds.password, bytes.fromhex(row["salt"]))):
            raise HTTPException(401, "Wrong email or password")
        token = _create_session(conn, row["id"])
    finally:
        conn.close()
    _set_cookie(response, token)
    return {"name": row["name"], "email": row["email"]}


@router.post("/logout")
def logout(response: Response, session: Optional[str] = Cookie(default=None)):
    if session:
        conn = _db()
        conn.execute("DELETE FROM sessions WHERE token = ?", (session,))
        conn.commit()
        conn.close()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(require_user)):
    return user
