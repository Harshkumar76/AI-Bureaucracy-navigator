"""scripts/test_retrieval.py"""
from dotenv import load_dotenv
load_dotenv()


from backend.database import db_connection
from backend.retrieval_service import RetrievalService


def main():
    with db_connection() as conn:
        retrieval_service = RetrievalService(conn)
        print(f"Top-K: {retrieval_service.top_k}  Min similarity: {retrieval_service.min_similarity}")
        print("Enter a free-text situation to test retrieval (Ctrl+C to quit)\n")

        while True:
            try:
                query = input("> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nDone.")
                break

            if not query:
                continue

            results = retrieval_service.retrieve(query)
            if not results:
                print("  No results above min_similarity threshold.\n")
                continue

            for rank, r in enumerate(results, start=1):
                print(f"  {rank}. [{r['similarity']:.3f}] {r['name']} ({r['category']})")
            print()


if __name__ == "__main__":
    main()