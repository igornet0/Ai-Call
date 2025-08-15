import asyncio
from typing import Optional, Sequence

import asyncpg


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    username TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS contacts (
    owner_telegram_id BIGINT NOT NULL,
    contact_telegram_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (owner_telegram_id, contact_telegram_id),
    CONSTRAINT fk_owner_user FOREIGN KEY (owner_telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
    CONSTRAINT fk_contact_user FOREIGN KEY (contact_telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class Database:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DB pool is not initialized")
        return self._pool

    async def upsert_user(self, telegram_id: int, username: str) -> None:
        query = """
        INSERT INTO users (telegram_id, username)
        VALUES ($1, $2)
        ON CONFLICT (telegram_id) DO UPDATE SET username = EXCLUDED.username
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, telegram_id, username)

    async def get_user(self, telegram_id: int) -> Optional[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", telegram_id)

    async def add_contact(self, owner_id: int, contact_id: int) -> None:
        if owner_id == contact_id:
            return
        query = """
        INSERT INTO contacts (owner_telegram_id, contact_telegram_id)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, owner_id, contact_id)

    async def search_contacts(self, owner_id: int, q: str) -> Sequence[asyncpg.Record]:
        like = f"%{q.lower()}%"
        query = """
        SELECT u.telegram_id, u.username
        FROM contacts c
        JOIN users u ON u.telegram_id = c.contact_telegram_id
        WHERE c.owner_telegram_id = $1 AND LOWER(u.username) LIKE $2
        ORDER BY u.username ASC
        LIMIT 25
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, owner_id, like)

    async def create_room(self, room_id: str, created_by: int) -> None:
        query = "INSERT INTO rooms (id, created_by) VALUES ($1, $2) ON CONFLICT DO NOTHING"
        async with self.pool.acquire() as conn:
            await conn.execute(query, room_id, created_by)
