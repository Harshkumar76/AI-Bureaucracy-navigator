# scripts/create_tables.py

import asyncio
from backend.database import engine, Base
from backend import models   # <-- this line is critical!

async def create_tables():
    async with engine.begin() as conn:
        # Create all tables defined in models.py
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Tables created successfully.")

if __name__ == "__main__":
    asyncio.run(create_tables())
