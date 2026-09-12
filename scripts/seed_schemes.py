"""Import the legacy JSON catalogue into PostgreSQL.

Run once after starting PostgreSQL, or again to update existing scheme records:
    python scripts/seed_schemes.py
"""

from dotenv import load_dotenv
load_dotenv()
import json
import sys
from pathlib import Path
from psycopg.types.json import Jsonb



ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.database import db_connection, init_db

SOURCE = ROOT / "backend" / "data" / "schemes.json"


def main() -> None:
    schemes = json.loads(SOURCE.read_text(encoding="utf-8"))
    init_db()
    with db_connection() as conn, conn.cursor() as cur:
        for scheme in schemes:
            cur.execute("""
                INSERT INTO schemes
                    (id, name, category, level, state, benefit, official_url, last_verified, data)
                VALUES (%(id)s, %(name)s, %(category)s, %(level)s, %(state)s, %(benefit)s,
                        %(official_url)s, %(last_verified)s, %(data)s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name, category = EXCLUDED.category, level = EXCLUDED.level,
                    state = EXCLUDED.state, benefit = EXCLUDED.benefit,
                    official_url = EXCLUDED.official_url,
                    last_verified = EXCLUDED.last_verified, data = EXCLUDED.data
            """, {**scheme, "data": Jsonb(scheme)})
        conn.commit()
    print(f"Seeded {len(schemes)} schemes into PostgreSQL.")


if __name__ == "__main__":
    main()
