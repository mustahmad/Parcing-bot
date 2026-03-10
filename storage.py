import json
import aiosqlite


class Storage:
    """SQLite-хранилище для заказов и отслеживания статусов."""

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
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id       TEXT PRIMARY KEY,
                source         TEXT,
                title          TEXT,
                description    TEXT,
                budget         INTEGER DEFAULT 0,
                url            TEXT,
                response_draft TEXT,
                analysis       TEXT,
                score          INTEGER DEFAULT 0,
                status         TEXT DEFAULT 'new',
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self._db.commit()

    # --- seen tracking ---

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

    # --- full order storage ---

    async def save_order(self, order: dict, evaluation: dict):
        await self._db.execute(
            """
            INSERT OR REPLACE INTO orders
                (order_id, source, title, description, budget, url,
                 response_draft, analysis, score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
            """,
            (
                order["id"],
                order.get("source", ""),
                order.get("title", ""),
                order.get("description", ""),
                order.get("budget", 0),
                order.get("url", ""),
                evaluation.get("response_draft", ""),
                evaluation.get("analysis", ""),
                evaluation.get("score", 0),
            ),
        )
        await self._db.commit()

    async def get_order(self, order_id: str) -> dict | None:
        self._db.row_factory = aiosqlite.Row
        cursor = await self._db.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        )
        row = await cursor.fetchone()
        self._db.row_factory = None
        if not row:
            return None
        return dict(row)

    async def update_response(self, order_id: str, new_draft: str):
        await self._db.execute(
            "UPDATE orders SET response_draft = ? WHERE order_id = ?",
            (new_draft, order_id),
        )
        await self._db.commit()

    async def set_status(self, order_id: str, status: str):
        await self._db.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?",
            (status, order_id),
        )
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
