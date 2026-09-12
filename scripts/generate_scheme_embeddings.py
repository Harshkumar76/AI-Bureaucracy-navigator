"""
scripts/generate_scheme_embeddings.py

Uses backend.database.db_connection(), same as every other part of the app.
"""
from dotenv import load_dotenv
load_dotenv()

import hashlib
import argparse
from backend.database import db_connection
from backend.embeddings import get_embedding_service
from backend.scheme_document import build_scheme_document

BATCH_SIZE = 32


def content_hash(document: str) -> str:
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    embedding_service = get_embedding_service()
    print(f"Model: {embedding_service.model_name} (dim {embedding_service.dimension})")

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, data, embedding, embedding_content_hash, embedding_model FROM schemes"
            )
            rows = cur.fetchall()

        print(f"Loaded {len(rows)} schemes from PostgreSQL")

        to_embed = []
        skipped = 0
        for row in rows:
            scheme = row["data"]
            document = build_scheme_document(scheme)
            new_hash = content_hash(document)

            unchanged = (
                not args.force
                and row["embedding_content_hash"] == new_hash
                and row["embedding"] is not None
                and row["embedding_model"] == embedding_service.model_name
            )
            if unchanged:
                skipped += 1
                continue

            to_embed.append((row["id"], document, new_hash))

        print(f"Skipping {skipped} unchanged; embedding {len(to_embed)}")
        if not to_embed:
            print("Nothing to do.")
            return

        with conn.cursor() as cur:
            for i in range(0, len(to_embed), BATCH_SIZE):
                batch = to_embed[i:i + BATCH_SIZE]
                vectors = embedding_service.generate_embeddings_batch([d for _, d, _ in batch])

                for (scheme_id, _, new_hash), vector in zip(batch, vectors):
                    cur.execute(
                        """
                        UPDATE schemes
                        SET embedding = %s,
                            embedding_content_hash = %s,
                            embedding_model = %s,
                            embedding_updated_at = now()
                        WHERE id = %s
                        """,
                        (vector, new_hash, embedding_service.model_name, scheme_id),
                    )
                conn.commit()
                print(f"  embedded {min(i + BATCH_SIZE, len(to_embed))}/{len(to_embed)}")

    print("Done.")


if __name__ == "__main__":
    main()