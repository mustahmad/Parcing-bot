import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from storage import Storage
from evaluator import AIEvaluator

log = logging.getLogger(__name__)


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class TelegramBot:
    """Telegram-бот с инлайн-кнопками для управления откликами."""

    def __init__(self, token: str, chat_id: str, storage: Storage, evaluator: AIEvaluator):
        self.chat_id = int(chat_id)
        self.storage = storage
        self.evaluator = evaluator

        self.app = Application.builder().token(token).build()
        self.app.add_handler(CallbackQueryHandler(self._on_callback))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text)
        )

    # --- Lifecycle (called from main.py) ---

    async def start(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        log.info("Telegram бот запущен (polling)")

    async def stop(self):
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        log.info("Telegram бот остановлен")

    # --- Send order notification ---

    async def send_order(self, order: dict, evaluation: dict):
        """Отправляет заказ с инлайн-кнопками."""
        # Save full order for later callbacks
        await self.storage.save_order(order, evaluation)

        budget = f"{order['budget']:,} ₽" if order.get("budget") else "не указан"
        score = evaluation.get("score", "?")
        draft = evaluation.get("response_draft", "")

        text = (
            f"🔥 <b>Новый заказ — {escape_html(order['source'])}</b>\n"
            f"\n"
            f"<b>{escape_html(order['title'])}</b>\n"
            f"\n"
            f"{escape_html(order.get('description', '')[:300])}\n"
            f"\n"
            f"💰 Бюджет: <b>{budget}</b>\n"
            f"⭐ Оценка AI: <b>{score}/10</b>\n"
        )

        if draft:
            text += (
                f"\n━━━━━━━━━━━━━━━━━━━\n"
                f"📝 <b>Отклик:</b>\n"
                f"<i>{escape_html(draft)}</i>\n"
            )

        # Inline keyboard
        oid = order["id"]
        keyboard = [
            [InlineKeyboardButton("🔗 Открыть заказ", url=order["url"])],
            [
                InlineKeyboardButton("✅ Откликнуться", callback_data=f"go:{oid}"),
                InlineKeyboardButton("❌ Пропуск", callback_data=f"skip:{oid}"),
            ],
            [
                InlineKeyboardButton("✏️ Другой отклик", callback_data=f"edit:{oid}"),
            ],
        ]

        await self.app.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True,
        )

    # --- Callback handler ---

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if ":" not in query.data:
            return

        action, order_id = query.data.split(":", 1)

        if action == "go":
            await self._handle_respond(query, order_id)
        elif action == "skip":
            await self._handle_skip(query, order_id)
        elif action == "edit":
            await self._handle_edit(query, order_id, context)

    async def _handle_respond(self, query, order_id: str):
        """Отправляет чистый текст отклика для копирования."""
        order_data = await self.storage.get_order(order_id)
        if not order_data or not order_data.get("response_draft"):
            await query.message.reply_text("⚠️ Отклик не найден")
            return

        draft = order_data["response_draft"]
        url = order_data.get("url", "")

        # Чистый текст — легко скопировать
        await query.message.reply_text(
            f"📋 <b>Скопируй и отправь:</b>\n\n"
            f"<code>{escape_html(draft)}</code>\n\n"
            f"🔗 <a href=\"{url}\">Перейти к заказу</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        await self.storage.set_status(order_id, "responded")

        # Update original message — remove buttons, add checkmark
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

    async def _handle_skip(self, query, order_id: str):
        """Помечает заказ как пропущенный."""
        await self.storage.set_status(order_id, "skipped")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.message.reply_text("⏭ Пропущено")

    async def _handle_edit(self, query, order_id: str, context: ContextTypes.DEFAULT_TYPE):
        """Запрашивает инструкции для перегенерации отклика."""
        context.user_data["editing_order"] = order_id
        context.user_data["editing_message"] = query.message

        await query.message.reply_text(
            "✏️ <b>Напиши, что изменить в отклике:</b>\n\n"
            "Примеры:\n"
            "• <i>добавь про опыт с CRM</i>\n"
            "• <i>сделай короче и увереннее</i>\n"
            "• <i>упомяни срок 1 день</i>",
            parse_mode="HTML",
        )

    # --- Text message handler (for edit flow) ---

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        editing_order = context.user_data.get("editing_order")
        if not editing_order:
            return  # No active edit session

        order_data = await self.storage.get_order(editing_order)
        if not order_data:
            await update.message.reply_text("⚠️ Заказ не найден")
            context.user_data.pop("editing_order", None)
            return

        # Show "thinking" indicator
        thinking_msg = await update.message.reply_text("🔄 Генерирую новый отклик...")

        # Regenerate
        result = await self.evaluator.regenerate(order_data, update.message.text)
        new_draft = result["response_draft"]

        # Save new draft
        await self.storage.update_response(editing_order, new_draft)

        # Delete thinking message
        try:
            await thinking_msg.delete()
        except Exception:
            pass

        # Send new draft with action buttons
        oid = editing_order
        keyboard = [
            [InlineKeyboardButton("🔗 Открыть заказ", url=order_data.get("url", ""))],
            [
                InlineKeyboardButton("✅ Откликнуться", callback_data=f"go:{oid}"),
                InlineKeyboardButton("❌ Пропуск", callback_data=f"skip:{oid}"),
            ],
            [
                InlineKeyboardButton("✏️ Ещё раз изменить", callback_data=f"edit:{oid}"),
            ],
        ]

        await update.message.reply_text(
            f"📝 <b>Новый отклик:</b>\n\n"
            f"<i>{escape_html(new_draft)}</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        # Clear edit state
        context.user_data.pop("editing_order", None)
        context.user_data.pop("editing_message", None)
