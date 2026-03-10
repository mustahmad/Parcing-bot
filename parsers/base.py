from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Базовый класс для парсеров фриланс-бирж."""

    name: str = "unknown"

    @abstractmethod
    async def fetch(self) -> list[dict]:
        """
        Возвращает список заказов. Каждый заказ — словарь:
        {
            "id":          str,   # уникальный ID (source_prefix + id)
            "title":       str,   # заголовок
            "description": str,   # описание (до 500 символов)
            "budget":      int,   # бюджет в рублях (0 если не указан)
            "url":         str,   # ссылка на заказ
            "source":      str,   # название источника
        }
        """
