"""Verify official scheme links stored in PostgreSQL.

Run before demos/deploys:
    python scripts/check_links.py
    python scripts/check_links.py --stamp
"""
import argparse
import datetime
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.database import db_connection

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AI-Bureaucracy-Navigator/1.0)"}


def alive(url: str) -> bool:
    try:
        response = requests.head(url, timeout=20, allow_redirects=True, headers=HEADERS)
        if response.status_code >= 400:
            response = requests.get(url, timeout=25, stream=True, headers=HEADERS)
        return response.status_code < 400
    except requests.RequestException:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stamp", action="store_true", help="update last_verified for live links")
    args = parser.parse_args()
    today = datetime.date.today()
    dead = []

    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, official_url FROM schemes ORDER BY id")
        schemes = cur.fetchall()
        for scheme in schemes:
            is_alive = alive(scheme["official_url"])
            print(f"{'OK' if is_alive else 'DEAD'}  {scheme['official_url']}")
            if is_alive and args.stamp:
                cur.execute("""UPDATE schemes
                               SET last_verified = %s,
                                   data = jsonb_set(data, '{last_verified}', to_jsonb(%s::text))
                               WHERE id = %s""", (today, today.isoformat(), scheme["id"]))
            elif not is_alive:
                dead.append((scheme["id"], scheme["official_url"]))
        conn.commit()

    if dead:
        print(f"\n{len(dead)} dead link(s):")
        for scheme_id, url in dead:
            print(f"  - {scheme_id}: {url}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
