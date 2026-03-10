import logging
import os
import re

from .base import BaseParser

log = logging.getLogger(__name__)


class TelegramChannelParser(BaseParser):
    """Парсер заказов из Telegram-каналов через Telethon."""

    name = "Telegram"

    def __init__(self, config: dict):
        self.channels = config["sources"]["telegram"].get("channels", [])
        self.api_id = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.message_limit = 30  # последних N сообщений с каждого канала

    async def fetch(self) -> list[dict]:
        if not self.api_id or not self.api_hash:
            log.warning("TELEGRAM_API_ID / TELEGRAM_API_HASH не заданы — пропуск")
            return []

        if not self.channels:
            return []

        try:
            from telethon import TelegramClient
        except ImportError:
            log.error("telethon не установлен: pip install telethon")
            return []

        orders: list[dict] = []
        client = TelegramClient(
            "freelance_parser_session",
            int(self.api_id),
            self.api_hash,
        )

        try:
            await client.start()

            for channel in self.channels:
                try:
                    entity = await client.get_entity(channel)
                    async for msg in client.iter_messages(entity, limit=self.message_limit):
                        if not msg.text or len(msg.text) < 30:
                            continue

                        order = self._parse_message(msg, channel)
                        if order:
                            orders.append(order)
                except Exception as e:
                    log.error("Telegram канал @%s: %s", channel, e)
        finally:
            await client.disconnect()

        return orders

    def _parse_message(self, msg, channel: str) -> dict | None:
        text = msg.text

        # Извлекаем бюджет из текста
        budget = 0
        patterns = [
            r"(\d[\d\s.,]*)\s*(?:руб|₽|р\b|rub)",
            r"бюджет[:\s]*(\d[\d\s.,]*)",
            r"(\d[\d\s.,]*)\s*(?:\$|usd|долл)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).replace(" ", "").replace(",", "").replace(".", "")
                budget = int(raw) if raw.isdigit() else 0
                # Если доллары — грубый пересчёт
                if any(s in pattern for s in ["\\$", "usd", "долл"]):
                    budget *= 90
                break

        # Заголовок — первая строка или первые 100 символов
        first_line = text.split("\n")[0].strip()
        title = first_line[:100] if first_line else text[:100]

        return {
            "id": f"tg_{channel}_{msg.id}",
            "title": title,
            "description": text[:500],
            "budget": budget,
            "url": f"https://t.me/{channel}/{msg.id}",
            "source": f"Telegram @{channel}",
        }
