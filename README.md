# Freelance Parser Bot

Автоматический парсер заказов с фриланс-бирж с AI-оценкой и готовыми откликами.

## Что делает

- Парсит заказы с **Kwork** и **FL.ru** каждые 10 минут
- Фильтрует по ключевым словам и минимальному бюджету
- **Groq AI (Llama 3.3 70B)** оценивает релевантность и генерирует персонализированный отклик
- Отправляет горячие заказы в **Telegram** с готовым текстом для копирования

## Быстрый старт

```bash
# Клонируй
git clone https://github.com/mustahmad/Parcing-bot.git
cd Parcing-bot

# Виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Зависимости
pip install -r requirements.txt

# Настройка
cp .env.example .env
# Заполни .env своими ключами

# Тест (без отправки в Telegram)
python main.py --once --dry-run

# Запуск
python main.py
```

## Настройка .env

| Переменная | Где взять |
|---|---|
| `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
| `TELEGRAM_BOT_TOKEN` | Создай бота через [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Узнай через [@userinfobot](https://t.me/userinfobot) |

**Важно:** после создания бота напиши ему `/start`, иначе он не сможет отправлять сообщения.

## Настройка config.yaml

- `keywords` — ключевые слова для фильтрации
- `min_budget` — минимальный бюджет (₽)
- `sources` — включение/выключение источников
- `your_skills` — описание твоих навыков (для AI)
- `check_interval` — интервал проверки в секундах

## Деплой на Railway

См. раздел ниже.

---

## Деплой на Railway (пошагово)

### 1. Создай аккаунт
Зайди на [railway.app](https://railway.app) и войди через GitHub.

### 2. Новый проект
- Нажми **"New Project"**
- Выбери **"Deploy from GitHub Repo"**
- Подключи репозиторий `mustahmad/Parcing-bot`

### 3. Переменные окружения
В настройках проекта → **Variables** → добавь:

```
GROQ_API_KEY=gsk_...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

### 4. Настройка запуска
Railway автоматически определит `Procfile`. Если нет — зайди в **Settings** → **Deploy** → **Custom Start Command**:

```
python main.py
```

### 5. Деплой
Нажми **"Deploy"**. Railway:
- Установит Python
- Установит зависимости из `requirements.txt`
- Запустит `python main.py` как worker-процесс

### 6. Проверка
- Зайди в **Deployments** → **View Logs**
- Ты должен увидеть `Freelance Parser запущен`
- Проверь Telegram — заказы начнут приходить

### Стоимость Railway
- **Trial**: 5$ бесплатного кредита (хватит на ~2 недели)
- **Hobby**: 5$/мес — бот будет работать 24/7
- Потребление: ~0.001$/час (минимальный ресурс)

### Обновление
При каждом `git push` в main — Railway автоматически передеплоит.
