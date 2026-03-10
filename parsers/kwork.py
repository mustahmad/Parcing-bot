import json
import logging
import re

import aiohttp

from .base import BaseParser

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


class KworkParser(BaseParser):
    """Парсер проектов (биржа заказов) с Kwork.ru.

    Kwork рендерит карточки на Vue.js, но вставляет JSON-массив «wants»
    прямо в HTML — мы достаём его регуляркой, без headless-браузера.
    """

    name = "Kwork"
    BASE_URL = "https://kwork.ru/projects"

    def __init__(self, config: dict):
        cats = config["sources"]["kwork"].get("categories", [])
        self.urls = [f"{self.BASE_URL}?c={c}" for c in cats] if cats else [self.BASE_URL]

    async def fetch(self) -> list[dict]:
        orders: list[dict] = []
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for url in self.urls:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status != 200:
                            log.warning("Kwork %s → %s", url, resp.status)
                            continue
                        html = await resp.text()
                        orders.extend(self._extract_from_json(html))
                except Exception as e:
                    log.error("Kwork (%s): %s", url, e)
        return orders

    def _extract_from_json(self, html: str) -> list[dict]:
        """Достаём массив wants из встроенного JSON в HTML."""
        idx = html.find('"wants":')
        if idx == -1:
            log.warning("Kwork: массив wants не найден в HTML")
            return []

        start = html.index("[", idx)
        depth = 0
        end = start
        for i in range(start, min(start + 500_000, len(html))):
            if html[i] == "[":
                depth += 1
            elif html[i] == "]":
                depth -= 1
            if depth == 0:
                end = i
                break

        raw = html[start : end + 1]

        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Kwork: не удалось распарсить wants JSON")
            return []

        results: list[dict] = []
        for item in items:
            try:
                order = self._convert(item)
                if order:
                    results.append(order)
            except Exception:
                continue
        return results

    @staticmethod
    def _convert(item: dict) -> dict | None:
        want_id = item.get("id")
        name = item.get("name", "").strip()
        if not name:
            return None

        # Описание
        desc = item.get("description", "")
        if isinstance(desc, str):
            desc = re.sub(r"<[^>]+>", " ", desc).strip()[:500]
        else:
            desc = ""

        # Бюджет — possiblePriceLimit или priceLimit
        budget = 0
        for key in ("possiblePriceLimit", "priceLimit"):
            val = item.get(key)
            if val:
                try:
                    budget = int(float(str(val)))
                except (ValueError, TypeError):
                    pass
                if budget > 0:
                    break

        return {
            "id": f"kwork_{want_id}",
            "title": name,
            "description": desc,
            "budget": budget,
            "url": f"https://kwork.ru/projects/{want_id}",
            "source": "Kwork",
        }
