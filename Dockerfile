# === Сборка образа для VPN Subscription System ===
# Используется multi-stage build для минимизации финального размера

# ---- Stage 1: Установка зависимостей ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Копируем только файлы с зависимостями
COPY pyproject.toml requirements.txt ./

# Устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: Финальный образ ----
FROM python:3.11-slim

WORKDIR /app

# Копируем установленные пакеты из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем исходный код проекта
COPY . .

# Создаем директорию для БД и медиа
RUN mkdir -p /app/data /app/media

# Переменные окружения (переопределяются в .env или docker-compose)
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///./data/vpn_bot.db
ENV BANNER_PATH=/app/media/banner.jpg

# Порт для FastAPI
EXPOSE 8000

# Команда по умолчанию — запуск API (бот запускается отдельно)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]