import os
import asyncio
import asyncpg
from dotenv import load_dotenv

async def init_db():
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set.")
        return
    print(f"Connecting to {dsn}")

    with open('database/init.sql', 'r') as f:
        sql = f.read()

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(sql)
        print("Successfully created tables!")
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(init_db())

