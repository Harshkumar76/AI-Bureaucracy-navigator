"""scripts/verify_embeddings.py"""
"""scripts/verify_embeddings.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()
from backend.database import db_connection
from backend.embeddings import get_embedding_service


def main():
    expected_dim = get_embedding_service().dimension

    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM schemes")
        total = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS with_embedding FROM schemes WHERE embedding IS NOT NULL")
        with_embedding = cur.fetchone()["with_embedding"]

        print(f"Total schemes: {total}")
        print(f"With embedding: {with_embedding}")
        print(f"Missing embedding: {total - with_embedding}")

        if with_embedding == 0:
            print("\nNo embeddings found. Run scripts/generate_scheme_embeddings.py first.")
            return

        cur.execute(
            "SELECT id, embedding_model, embedding_updated_at, vector_dims(embedding) AS dim "
            "FROM schemes WHERE embedding IS NOT NULL ORDER BY embedding_updated_at DESC LIMIT 5"
        )
        rows = cur.fetchall()

        print(f"\nExpected dimension (current model): {expected_dim}")
        print("\nMost recently embedded schemes:")
        mismatches = 0
        for row in rows:
            status = "OK" if row["dim"] == expected_dim else "DIMENSION MISMATCH"
            if row["dim"] != expected_dim:
                mismatches += 1
            print(f"  {row['id']:30s} model={row['embedding_model']:45s} "
                  f"dim={row['dim']:<5} updated={row['embedding_updated_at']}  [{status}]")

        cur.execute("SELECT id, embedding FROM schemes WHERE embedding IS NOT NULL LIMIT 1")
        sample = cur.fetchone()
        raw_vector = sample["embedding"]
        # pgvector's Vector wrapper isn't always directly iterable depending on
        # the installed pgvector-python version -- .to_list() is the stable way
        # to get a plain Python list out of it.
        vector_values = raw_vector.to_list() if hasattr(raw_vector, "to_list") else list(raw_vector)
        preview = vector_values[:5]
        print(f"\nSample vector ({sample['id']}), first 5 values: {preview}")

        if mismatches:
            print(f"\n{mismatches} row(s) mismatch. Run: python scripts/generate_scheme_embeddings.py --force")
        else:
            print("\nAll checks passed.")


if __name__ == "__main__":
    main()