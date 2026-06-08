"""
FastAPI backend для VPN-подписок
Обработка конфигураций подписок
"""
from fastapi import FastAPI, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from datetime import datetime
from shared.database import get_db, init_db
from shared.models import User, GlobalConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VPN Subscription API", version="1.0.0")


@app.on_event("startup")
async def startup():
    """Инициализация при запуске"""
    init_db()
    logger.info("API сервер запущен")


def get_subscription_config(user: User, db: Session) -> str:
    """
    Собрать конфигурацию подписки для пользователя
    """
    # Получить глобальные настройки
    configs = {
        config.key: config.value
        for config in db.query(GlobalConfig).all()
    }

    # Базовые заголовки
    profile_title = configs.get("profile-title", "VPN Subscription")
    announce = configs.get("announce", "Welcome to VPN")
    update_interval = configs.get("profile-update-interval", "1")
    support_url = configs.get("support-url", "")
    profile_web_page_url = configs.get("profile-web-page-url", "")

    # Начать собирать конфиг
    config_text = f"#profile-title: {profile_title}\n"
    config_text += f"#announce: {announce}\n"
    config_text += f"#profile-update-interval: {update_interval}\n"

    if support_url:
        config_text += f"#support-url: {support_url}\n"

    if profile_web_page_url:
        config_text += f"#profile-web-page-url: {profile_web_page_url}\n"

    # Добавить серверы в зависимости от типа подписки
    if user.sub_type in ("normal", "both"):
        base_config_normal = configs.get("base_config_normal", "")
        if base_config_normal:
            config_text += base_config_normal.strip() + "\n"

    if user.sub_type in ("antiblock", "both"):
        base_config_antiblock = configs.get("base_config_antiblock", "")
        if base_config_antiblock:
            config_text += base_config_antiblock.strip() + "\n"

    return config_text.strip()


def get_expired_config() -> str:
    """Конфигурация для истекшей подписки"""
    return """#profile-title: Срок действия подписки истек!
#announce: ⚠️ Пожалуйста, продлите подписку в Telegram-боте.
vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1?encryption=none&type=tcp#❌_ПОДПИСКА_ИСТЕКЛА_❌
vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1?encryption=none&type=tcp#👇Продлите_в_боте_@твой_бот👇"""


@app.get("/sub/{token}", response_class=PlainTextResponse)
async def get_subscription(token: str, db: Session = Depends(get_db)):
    """
    Получить конфигурацию подписки по токену
    """
    # Найти пользователя по токену
    user = db.query(User).filter(User.subscription_token == token).first()

    if not user:
        logger.warning(f"Подписка по токену {token[:8]}... не найдена")
        return get_expired_config()

    # Проверить, активна ли подписка
    now = datetime.utcnow()
    if not user.sub_expires_at or user.sub_expires_at <= now or user.sub_type == "none":
        logger.info(f"Истекшая подписка для пользователя {user.telegram_id}")
        return get_expired_config()

    # Генерируем конфиг
    config = get_subscription_config(user, db)
    logger.info(f"✅ Конфиг отправлен пользователю {user.telegram_id}")
    return config


@app.get("/health")
async def health_check():
    """Проверка здоровья API"""
    return {"status": "ok", "message": "VPN API is running"}


@app.get("/")
async def root():
    """Корневой маршрут"""
    return {
        "name": "VPN Subscription API",
        "version": "1.0.0",
        "endpoints": {
            "subscription": "/sub/{token}",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
