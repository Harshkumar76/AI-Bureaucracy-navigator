"""PostgreSQL connection and schema helpers."""
import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")


def _database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be set to a PostgreSQL connection URL")
    return DATABASE_URL


@contextmanager
def db_connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(_database_url(), row_factory=dict_row) as conn:
        yield conn


def init_db() -> None:
    """Create the application schema. Safe to run at every application start."""
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                pw_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at BIGINT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS revoked_tokens (
                jti TEXT PRIMARY KEY,
                expires_at BIGINT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schemes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                level TEXT NOT NULL,
                state TEXT NOT NULL,
                benefit TEXT NOT NULL,
                official_url TEXT NOT NULL,
                last_verified DATE,
                data JSONB NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS schemes_state_idx ON schemes (state)")
        cur.execute("CREATE INDEX IF NOT EXISTS schemes_data_gin_idx ON schemes USING GIN (data)")
        cur.execute("CREATE INDEX IF NOT EXISTS revoked_tokens_expiry_idx ON revoked_tokens (expires_at)")
        conn.commit()
