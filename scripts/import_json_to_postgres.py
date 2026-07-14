# scripts/import_json_to_postgres.py

import sys
from pathlib import Path

# Add project root to sys.path so "backend" can be found
sys.path.append(str(Path(__file__).resolve().parent.parent))

import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import AsyncSessionLocal
from backend.models import Scheme

DATA_FILE = Path(__file__).resolve().parent.parent / "backend" / "data" / "schemes.json"

async def import_schemes():
    async with AsyncSessionLocal() as session:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

        # Ensure it's always a list
        if isinstance(data, dict):
            schemes = [data]
        else:
            schemes = data

        count = 0
        for s in schemes:
            scheme = Scheme(
                id=None,  # auto PK
                name=s.get("name"),
                category=s.get("category"),
                level=s.get("level"),
                benefit=s.get("benefit"),
                official_url=s.get("official_url"),
                last_verified=None,
                rules=s.get("rules"),
            )
            session.add(scheme)
            count += 1

        await session.commit()
    print(f"✅ Imported {count} schemes into PostgreSQL.")

if __name__ == "__main__":
    asyncio.run(import_schemes())
