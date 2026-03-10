import logging

import aiohttp
from bs4 import BeautifulSoup

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


class FLParser(BaseParser):
    """Парсер проектов с FL.ru."""

    name = "FL.ru"
    BASE_URL = "https://www.fl.ru/projects/"

    def __init__(self, config: dict):
        self.config = config

    async def fetch(self) -> list[dict]:
        orders: list[dict] = []
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            try:
                async with session.get(
                    self.BASE_URL, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        log.warning("FL.ru → %s", resp.status)
                        return orders
                    html = await resp.text()
                    orders = self._parse(html)
            except Exception as e:
                log.error("FL.ru: %s", e)
        return orders

    def _parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[dict] = []

        posts = soup.select("#projects-list .b-post")
        if not posts:
            posts = soup.select(".b-post")

        for post in posts:
            try:
                order = self._parse_post(post)
                if order:
                    results.append(order)
            except Exception:
                continue

        return results

    @staticmethod
    def _parse_post(post) -> dict | None:
        # --- Заголовок и ссылка ---
        title_el = post.select_one('a[href*="/projects/"]')
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        if not title:
            return None

        link = title_el.get("href", "")
        if link and not link.startswith("http"):
            link = f"https://www.fl.ru{link}"

        # --- Описание ---
        desc_el = post.select_one(".b-post__txt")
        description = desc_el.get_text(strip=True)[:500] if desc_el else ""

        # --- Бюджет ---
        budget = 0
        price_el = post.select_one(".b-post__price")
        if price_el:
            price_text = price_el.get_text(strip=True)
            digits = "".join(c for c in price_text if c.isdigit())
            budget = int(digits) if digits else 0

        # --- ID из URL ---
        slug = link.rstrip("/").split("/")[-1].replace(".html", "") if link else str(hash(title))
        project_id = ""
        parts = link.split("/")
        for part in parts:
            if part.isdigit():
                project_id = part
                break
        if not project_id:
            project_id = slug

        return {
            "id": f"fl_{project_id}",
            "title": title,
            "description": description,
            "budget": budget,
            "url": link,
            "source": "FL.ru",
        }
