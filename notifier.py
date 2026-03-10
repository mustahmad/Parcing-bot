import logging
import aiohttp

log = logging.getLogger(__name__)


class TelegramNotifier:
    """Отправляет уведомления о заказах в Telegram."""

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"

    async def send_order(self, order: dict, evaluation: dict):
        budget = f"{order['budget']:,} ₽" if order.get("budget") else "не указан"
        score = evaluation.get("score", "?")
        draft = evaluation.get("response_draft", "")

        text = (
            f"🔥 <b>Новый заказ — {order['source']}</b>\n"
            f"\n"
            f"<b>{self._escape(order['title'])}</b>\n"
            f"\n"
            f"{self._escape(order.get('description', '')[:300])}\n"
            f"\n"
            f"💰 Бюджет: <b>{budget}</b>\n"
            f"⭐ Оценка AI: <b>{score}/10</b>\n"
            f"🔗 <a href=\"{order['url']}\">Открыть заказ</a>\n"
        )

        if draft:
            text += (
                f"\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📝 <b>Готовый отклик (скопируй):</b>\n"
                f"\n"
                f"<code>{self._escape(draft)}</code>\n"
            )

        await self._send(text)

    async def send_status(self, message: str):
        await self._send(f"ℹ️ {self._escape(message)}")

    async def _send(self, text: str):
        if not self.token or not self.chat_id:
            log.warning("Telegram токен или chat_id не заданы — пропуск")
            return

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/sendMessage",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        log.error("Telegram API ошибка %s: %s", resp.status, body)
        except Exception as e:
            log.error("Telegram отправка: %s", e)

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
