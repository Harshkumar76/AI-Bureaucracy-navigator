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

    print("Done. No existing data was modified.")


if __name__ == "__main__":
    main()