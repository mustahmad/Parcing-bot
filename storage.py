import aiosqlite


class Storage:
    """SQLite-хранилище для отслеживания уже обработанных заказов."""

    def __init__(self, db_path: str = "seen_orders.db"):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self):
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
                order_id   TEXT PRIMARY KEY,
                source     TEXT,
                title      TEXT,
                seen_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self._db.commit()

    async def is_seen(self, order_id: str) -> bool:
        cursor = await self._db.execute(
            "SELECT 1 FROM seen WHERE order_id = ?", (order_id,)
        )
        return await cursor.fetchone() is not None

    async def mark_seen(self, order_id: str, source: str = "", title: str = ""):
        await self._db.execute(
            "INSERT OR IGNORE INTO seen (order_id, source, title) VALUES (?, ?, ?)",
            (order_id, source, title),
        )
        await self._db.commit()

    async def count(self) -> int:
        cursor = await self._db.execute("SELECT COUNT(*) FROM seen")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def close(self):
        if self._db:
            await self._db.close()
