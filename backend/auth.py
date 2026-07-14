"""JWT authentication with SQLite-backed users and logout revocation."""
import hashlib
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

import jwt
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
from pydantic import BaseModel

DB_PATH = Path(__file__).resolve().parent / "data" / "users.db"
TOKEN_TTL = 7 * 24 * 3600  # 7 days
COOKIE = "access_token"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "ai-bureaucracy-navigator"
# Set JWT_SECRET to a stable, high-entropy value in production. The development
# fallback is deliberately process-local, so tokens do not survive a restart.
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_urlsafe(48)
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

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
    conn.execute("""CREATE TABLE IF NOT EXISTS revoked_tokens (
        jti TEXT PRIMARY KEY,
        expires_at INTEGER NOT NULL)""")
    return conn


def _hash_pw(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE, token, max_age=TOKEN_TTL, httponly=True,
        secure=COOKIE_SECURE, samesite="lax", path="/",
    )


def _create_token(user: sqlite3.Row) -> str:
    now = int(time.time())
    return jwt.encode({
        "sub": str(user["id"]), "email": user["email"], "name": user["name"],
        "iat": now, "exp": now + TOKEN_TTL, "iss": JWT_ISSUER,
        "jti": secrets.token_urlsafe(16),
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _read_token(cookie_token: Optional[str], authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return cookie_token


def current_user(
    access_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    token = _read_token(access_token, authorization)
    if not token:
        return None
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
    except jwt.PyJWTError:
        return None

    conn = _db()
    try:
        conn.execute("DELETE FROM revoked_tokens WHERE expires_at <= ?", (int(time.time()),))
        revoked = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (claims["jti"],)).fetchone()
        conn.commit()
        if revoked:
            return None
        row = conn.execute("SELECT id, email, name FROM users WHERE id = ?", (claims["sub"],)).fetchone()
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
        user = conn.execute("SELECT id, email, name FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "This email is already registered - sign in instead")
    finally:
        conn.close()
    token = _create_token(user)
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
    finally:
        conn.close()
    token = _create_token(row)
    _set_cookie(response, token)
    return {"name": row["name"], "email": row["email"]}


@router.post("/logout")
def logout(
    response: Response,
    access_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
):
    token = _read_token(access_token, authorization)
    if token:
        try:
            claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
            conn = _db()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO revoked_tokens (jti, expires_at) VALUES (?, ?)",
                    (claims["jti"], claims["exp"]),
                )
                conn.commit()
            finally:
                conn.close()
        except jwt.PyJWTError:
            pass
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(require_user)):
    return user
