"""
scripts/setup_pgvector_schema.py

One-off schema setup for pgvector support, run manually -- NOT part of
init_db(), because computing the embedding dimension requires loading
sentence-transformers, which is too heavy to do on every app boot.

Uses your existing db_connection() helper, same as every other script.
Purely additive (ADD COLUMN IF NOT EXISTS throughout), matching the exact
pattern your own translations column already uses in database.py.

Run once:
    python scripts/setup_pgvector_schema.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()
from backend.database import db_connection
from backend.embeddings import get_embedding_service
from backend.rag_config import ENABLE_HNSW_INDEX


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return cur.fetchone() is not None


def existing_vector_dimension(cur, table: str, column: str) -> int | None:
    """Returns the declared dimension of an existing `vector(N)` column, e.g.
    256, by asking Postgres to render its full type name and parsing the
    number out of "vector(256)". Returns None if the column has no fixed
    dimension declared (bare `vector` with no size)."""
    cur.execute(
        """
        SELECT format_type(a.atttypid, a.atttypmod) AS full_type
        FROM pg_attribute a
        WHERE a.attrelid = %s::regclass AND a.attname = %s AND NOT a.attisdropped
        """,
        (table, column),
    )
    row = cur.fetchone()
    if not row:
        return None
    full_type = row["full_type"]  # e.g. "vector(256)" or just "vector"
    if "(" not in full_type:
        return None
    return int(full_type.split("(")[1].rstrip(")"))


def main():
    embedding_service = get_embedding_service()
    dim = embedding_service.dimension
    print(f"Model '{embedding_service.model_name}' -> dimension {dim}")

    with db_connection() as conn, conn.cursor() as cur:
        # Extension already installed by PostgreSQL admin
        print("pgvector extension enabled")

        if not column_exists(cur, "schemes", "embedding"):
            cur.execute(f"ALTER TABLE schemes ADD COLUMN embedding VECTOR({dim})")
            print(f"Added schemes.embedding VECTOR({dim})")
        else:
            existing_dim = existing_vector_dimension(cur, "schemes", "embedding")
            if existing_dim is not None and existing_dim != dim:
                print(
                    f"schemes.embedding is VECTOR({existing_dim}) but the current "
                    f"model produces VECTOR({dim}) -- migrating column "
                    f"(existing stored vectors are dropped; re-run "
                    f"generate_scheme_embeddings.py afterward to refill them)"
                )
                # Drop any HNSW index first -- it's built against the old
                # dimension and Postgres won't let the column change type
                # while an index depends on it.
                cur.execute("DROP INDEX IF EXISTS schemes_embedding_hnsw_idx")
                cur.execute("ALTER TABLE schemes DROP COLUMN embedding")
                cur.execute(f"ALTER TABLE schemes ADD COLUMN embedding VECTOR({dim})")
                # Old hash/model bookkeeping is meaningless for a dropped
                # column -- clear it so generate_scheme_embeddings.py's
                # "unchanged" check doesn't get confused by stale metadata.
                cur.execute(
                    "UPDATE schemes SET embedding_content_hash = NULL, embedding_model = NULL, "
                    "embedding_updated_at = NULL"
                )
                conn.commit()
                print(f"Migrated schemes.embedding to VECTOR({dim})")
            else:
                print("schemes.embedding already exists -- skipped")

        for col, ddl_type in [
            ("embedding_content_hash", "TEXT"),
            ("embedding_model", "TEXT"),
            ("embedding_updated_at", "TIMESTAMPTZ"),
        ]:
            if not column_exists(cur, "schemes", col):
                cur.execute(f"ALTER TABLE schemes ADD COLUMN {col} {ddl_type}")
                print(f"Added schemes.{col}")
            else:
                print(f"schemes.{col} already exists -- skipped")

        conn.commit()

        if ENABLE_HNSW_INDEX:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS schemes_embedding_hnsw_idx "
                "ON schemes USING hnsw (embedding vector_cosine_ops)"
            )
            conn.commit()
            print("Created HNSW index (cosine) on schemes.embedding")
        else:
            print("Skipped HNSW index (ENABLE_HNSW_INDEX=false) -- fine at 16 schemes")

    print("Done.")


if __name__ == "__main__":
    main()