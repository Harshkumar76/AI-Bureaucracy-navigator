"""Verify official scheme links stored in PostgreSQL.

Run before demos/deploys:
    python scripts/check_links.py
    python scripts/check_links.py --stamp
"""
import argparse
import datetime
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.database import db_connection

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Some government sites (Akamai/WAF-protected) block automated requests based
# on TLS fingerprinting, not headers — they load fine in a real browser but
# will always fail here. Manually verified working; skip the automated check
# and just stamp them. Re-verify manually every so often and update the date
# comment below.
MANUALLY_VERIFIED = {
    "https://beneficiary.nha.gov.in/",   # confirmed working in browser 2026-07
    "https://www.nsiindia.gov.in/",      # confirmed working in browser 2026-07
}


def alive(url: str) -> bool:
    if url in MANUALLY_VERIFIED:
        return True

    try:
        response = requests.head(url, timeout=20, allow_redirects=True, headers=HEADERS)
        if response.status_code < 400:
            return True
    except requests.RequestException:
        pass

    try:
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
            note = " (manually verified)" if scheme["official_url"] in MANUALLY_VERIFIED else ""
            print(f"{'OK' if is_alive else 'DEAD'}  {scheme['official_url']}{note}")
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