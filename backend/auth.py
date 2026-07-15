"""JWT authentication with PostgreSQL-backed users and logout revocation."""
import hashlib
import os
import re
import secrets
import time
from typing import Optional

import jwt
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
from psycopg.errors import UniqueViolation
from pydantic import BaseModel

from backend.database import db_connection

TOKEN_TTL = 7 * 24 * 3600  # 7 days
COOKIE = "access_token"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "ai-bureaucracy-navigator"
# Set JWT_SECRET to a stable, high-entropy value in production. The development
# fallback is deliberately process-local, so tokens do not survive a restart.
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_urlsafe(48)
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _hash_pw(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE, token, max_age=TOKEN_TTL, httponly=True,
                        secure=COOKIE_SECURE, samesite="lax", path="/")


def _create_token(user: dict) -> str:
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


def current_user(access_token: Optional[str] = Cookie(default=None),
                 authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    token = _read_token(access_token, authorization)
    if not token:
        return None
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
    except jwt.PyJWTError:
        return None

    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM revoked_tokens WHERE expires_at <= %s", (int(time.time()),))
        cur.execute("SELECT 1 FROM revoked_tokens WHERE jti = %s", (claims["jti"],))
        if cur.fetchone():
            conn.commit()
            return None
        cur.execute("SELECT id, email, name FROM users WHERE id = %s", (claims["sub"],))
        user = cur.fetchone()
        conn.commit()
        return user


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

    try:
        with db_connection() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO users (email, name, pw_hash, salt, created_at)
                           VALUES (%s, %s, %s, %s, %s)
                           RETURNING id, email, name""",
                        (email, name, _hash_pw(creds.password, salt), salt.hex(), int(time.time())))
            user = cur.fetchone()
            conn.commit()
    except UniqueViolation:
        raise HTTPException(400, "This email is already registered - sign in instead")

    _set_cookie(response, _create_token(user))
    return {"name": name, "email": email}


@router.post("/login")
def login(creds: Credentials, response: Response):
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (creds.email.strip().lower(),))
        user = cur.fetchone()
    if not user or not secrets.compare_digest(
            user["pw_hash"], _hash_pw(creds.password, bytes.fromhex(user["salt"]))):
        raise HTTPException(401, "Wrong email or password")
    _set_cookie(response, _create_token(user))
    return {"name": user["name"], "email": user["email"]}


@router.post("/logout")
def logout(response: Response, access_token: Optional[str] = Cookie(default=None),
           authorization: Optional[str] = Header(default=None)):
    token = _read_token(access_token, authorization)
    if token:
        try:
            claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
            with db_connection() as conn, conn.cursor() as cur:
                cur.execute("INSERT INTO revoked_tokens (jti, expires_at) VALUES (%s, %s) "
                            "ON CONFLICT (jti) DO UPDATE SET expires_at = EXCLUDED.expires_at",
                            (claims["jti"], claims["exp"]))
                conn.commit()
        except jwt.PyJWTError:
            pass
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(require_user)):
    return user