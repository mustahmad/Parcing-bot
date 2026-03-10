import logging
from groq import AsyncGroq

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Ты — ассистент фрилансера. Твоя задача — оценить заказ и написать цепляющий отклик.

Правила отклика:
- 2-4 предложения, без воды и шаблонов
- Покажи, что понял задачу — перефразируй суть
- Упомяни релевантный опыт или инструмент
- Назови примерный срок
- Будь уверенным, но не высокомерным
"""


class AIEvaluator:
    """Оценивает заказы и генерирует отклики через Groq API."""

    def __init__(self, api_key: str, skills: str):
        self.client = AsyncGroq(api_key=api_key)
        self.skills = skills.strip()

    async def evaluate(self, order: dict) -> dict:
        budget_str = f"{order['budget']:,} ₽" if order.get("budget") else "не указан"

        user_prompt = f"""\
Заказ с {order['source']}:
— Название: {order['title']}
— Описание: {order.get('description', 'нет')}
— Бюджет: {budget_str}

Мои навыки:
{self.skills}

Ответь СТРОГО в таком формате:

РЕЛЕВАНТНОСТЬ: да/нет
ОЦЕНКА: число от 1 до 10
ПРИЧИНА: одно предложение почему стоит/не стоит браться
ОТКЛИК:
(текст отклика тут)
"""

        try:
            response = await self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=400,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = response.choices[0].message.content

            relevant = "релевантность: да" in text.lower()
            score = self._extract_score(text)
            response_text = self._extract_response(text)

            return {
                "relevant": relevant,
                "score": score,
                "analysis": text,
                "response_draft": response_text,
            }

        except Exception as e:
            log.error("Groq API ошибка: %s", e)
            return {
                "relevant": True,
                "score": 0,
                "analysis": f"[Ошибка AI: {e}]",
                "response_draft": "",
            }

    async def regenerate(self, order_data: dict, user_instructions: str) -> dict:
        """Перегенерирует отклик с учётом пожеланий пользователя."""
        prompt = f"""\
Заказ:
— Название: {order_data.get('title', '')}
— Описание: {order_data.get('description', '')}
— Бюджет: {order_data.get('budget', 'не указан')} ₽
— Источник: {order_data.get('source', '')}

Предыдущий отклик:
{order_data.get('response_draft', '')}

Пожелания к новому отклику:
{user_instructions}

Мои навыки:
{self.skills}

Напиши ТОЛЬКО новый отклик (2-4 предложения), без пояснений и заголовков.
"""

        try:
            response = await self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=300,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            new_draft = response.choices[0].message.content.strip()
            return {"response_draft": new_draft}

        except Exception as e:
            log.error("Groq regenerate ошибка: %s", e)
            return {"response_draft": f"[Ошибка: {e}]"}

    @staticmethod
    def _extract_score(text: str) -> int:
        for line in text.split("\n"):
            if "ОЦЕНКА:" in line.upper():
                digits = "".join(c for c in line if c.isdigit())
                if digits:
                    return min(int(digits), 10)
        return 0

    @staticmethod
    def _extract_response(text: str) -> str:
        marker = "ОТКЛИК:"
        idx = text.upper().find(marker.upper())
        if idx == -1:
            return ""
        return text[idx + len(marker) :].strip()
