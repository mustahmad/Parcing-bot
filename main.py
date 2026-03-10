#!/usr/bin/env python3
"""
Freelance Parser — автоматический поиск заказов на фриланс-биржах.

Парсит Kwork, FL.ru, Telegram-каналы.
Оценивает релевантность через Groq AI (Llama 3.3 70B).
Отправляет заказы в Telegram-бот с инлайн-кнопками:
  ✅ Откликнуться — получить чистый текст для копирования
  ✏️ Другой отклик — AI перегенерирует с твоими пожеланиями
  ❌ Пропуск — скрыть заказ

Запуск:
    python main.py              # цикл с интервалом из config.yaml
    python main.py --once       # один прогон и выход
    python main.py --dry-run    # без отправки в Telegram
"""

import argparse
import asyncio
import logging
import os
import sys

import yaml
from dotenv import load_dotenv

from parsers import KworkParser, FLParser, TelegramChannelParser
from evaluator import AIEvaluator
from bot import TelegramBot
from storage import Storage

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

log = logging.getLogger("main")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_parsers(config: dict) -> list:
    parsers = []
    src = config["sources"]

    if src.get("kwork", {}).get("enabled"):
        parsers.append(KworkParser(config))

    if src.get("fl", {}).get("enabled"):
        parsers.append(FLParser(config))

    if src.get("telegram", {}).get("enabled"):
        parsers.append(TelegramChannelParser(config))

    return parsers


def matches_keywords(order: dict, keywords: list[str]) -> bool:
    text = f"{order['title']} {order.get('description', '')}".lower()
    return any(kw.lower() in text for kw in keywords)


async def process_orders(
    parsers: list,
    storage: Storage,
    evaluator: AIEvaluator,
    bot: TelegramBot | None,
    config: dict,
    dry_run: bool = False,
) -> int:
    """Один цикл проверки. Возвращает кол-во отправленных уведомлений."""
    sent = 0
    keywords = config["keywords"]
    min_budget = config.get("min_budget", 0)

    for parser in parsers:
        try:
            orders = await parser.fetch()
            log.info("%s: получено %d заказов", parser.name, len(orders))
        except Exception as e:
            log.error("%s: ошибка — %s", parser.name, e)
            continue

        for order in orders:
            if await storage.is_seen(order["id"]):
                continue

            await storage.mark_seen(order["id"], order["source"], order["title"])

            if not matches_keywords(order, keywords):
                continue

            if order.get("budget") and order["budget"] < min_budget:
                continue

            log.info(
                "✓ Подходящий заказ: %s | %s | %s ₽",
                order["source"],
                order["title"][:60],
                order.get("budget", "?"),
            )

            evaluation = await evaluator.evaluate(order)

            if not evaluation["relevant"]:
                log.info("  → AI: не релевантно, пропуск")
                continue

            log.info("  → AI оценка: %s/10", evaluation.get("score", "?"))

            if not dry_run and bot:
                await bot.send_order(order, evaluation)

            sent += 1

    return sent


async def main():
    parser = argparse.ArgumentParser(description="Freelance order parser")
    parser.add_argument("--once", action="store_true", help="Один прогон и выход")
    parser.add_argument("--dry-run", action="store_true", help="Без отправки в Telegram")
    parser.add_argument("--config", default="config.yaml", help="Путь к конфигу")
    args = parser.parse_args()

    config = load_config(args.config)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        log.error("GROQ_API_KEY не задан в .env")
        sys.exit(1)

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not tg_token and not args.dry_run:
        log.warning("TELEGRAM_BOT_TOKEN не задан — работаем в dry-run режиме")
        args.dry_run = True

    # --- Init ---
    storage = Storage("seen_orders.db")
    await storage.init()

    evaluator = AIEvaluator(api_key=api_key, skills=config.get("your_skills", ""))
    parsers = build_parsers(config)

    if not parsers:
        log.error("Нет включённых источников в config.yaml")
        sys.exit(1)

    # --- Telegram Bot (with inline buttons & callbacks) ---
    bot = None
    if not args.dry_run and tg_token and tg_chat:
        bot = TelegramBot(
            token=tg_token,
            chat_id=tg_chat,
            storage=storage,
            evaluator=evaluator,
        )
        await bot.start()

    interval = config.get("check_interval", 600)

    log.info("=" * 50)
    log.info("Freelance Parser запущен")
    log.info("Источники: %s", ", ".join(p.name for p in parsers))
    log.info("Ключевые слова: %d шт.", len(config["keywords"]))
    log.info("Мин. бюджет: %s ₽", config.get("min_budget", 0))
    log.info("Интервал: %d сек", interval)
    log.info("Режим: %s", "dry-run" if args.dry_run else "боевой (с кнопками)")
    log.info("=" * 50)

    # --- Main loop ---
    cycle = 0
    try:
        while True:
            cycle += 1
            log.info("--- Цикл #%d ---", cycle)

            sent = await process_orders(
                parsers, storage, evaluator, bot, config, args.dry_run
            )

            total_seen = await storage.count()
            log.info("Отправлено: %d | Всего в базе: %d", sent, total_seen)

            if args.once:
                if bot:
                    log.info("Бот слушает кнопки 60 сек (Ctrl+C для выхода)...")
                    await asyncio.sleep(60)
                break

            log.info("Сон %d сек до следующей проверки...", interval)
            await asyncio.sleep(interval)
    finally:
        if bot:
            await bot.stop()
        await storage.close()

    log.info("Завершено.")


if __name__ == "__main__":
    asyncio.run(main())
