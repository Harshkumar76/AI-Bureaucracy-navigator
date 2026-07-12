"""Link checker — verifies every official_url in the scheme database.

Run before demos/deploys:
    python scripts/check_links.py            # report only
    python scripts/check_links.py --stamp    # also update last_verified for live links

This is what keeps the "verified <date>" label on each finding card honest.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "backend" / "data" / "schemes.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def alive(url: str) -> bool:
    try:
        r = requests.head(url, timeout=20, allow_redirects=True, headers=HEADERS)
        if r.status_code >= 400:  # some gov servers reject HEAD
            r = requests.get(url, timeout=25, stream=True, headers=HEADERS)
        return r.status_code < 400
    except requests.exceptions.SSLError:
        # several gov servers send incomplete cert chains that browsers repair
        # via AIA but certifi cannot; retry unverified — we only test liveness
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            r = requests.get(url, timeout=25, stream=True, headers=HEADERS, verify=False)
            if r.status_code < 400:
                print(f"   (note: {url} serves an incomplete TLS cert chain)")
                return True
            return False
        except requests.RequestException:
            return False
    except requests.RequestException:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stamp", action="store_true",
                        help="update last_verified to today for live links")
    args = parser.parse_args()

    schemes = json.loads(DATA.read_text(encoding="utf-8"))
    today = datetime.date.today().isoformat()
    dead = []
    checked = {}

    for s in schemes:
        url = s["official_url"]
        if url not in checked:
            checked[url] = alive(url)
            print(f"{'✓' if checked[url] else '✗ DEAD'}  {url}")
        if checked[url]:
            if args.stamp:
                s["last_verified"] = today
        else:
            dead.append((s["id"], url))

    if args.stamp:
        DATA.write_text(json.dumps(schemes, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"\nStamped last_verified={today} on schemes with live links.")

    if dead:
        print(f"\n{len(dead)} dead link(s):")
        for sid, url in dead:
            print(f"  - {sid}: {url}")
        sys.exit(1)
    print(f"\nAll {len(checked)} unique links are alive.")


if __name__ == "__main__":
    main()
