"""
Вспомогательные функции для Telegram-бота
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from shared.models import User, Admin, Payment, PromoCode, Referral, GlobalConfig
from shared.config import (
    BASE_PRICE_PER_MONTH, REFERRAL_REWARD, FREE_TRIAL_DAYS,
    API_URL, GLOBAL_DISCOUNT, PRICING
)

logger = logging.getLogger(__name__)


# ===== FORMATTING =====

def format_currency(amount: float) -> str:
    """Форматировать сумму в рублях"""
    return f"{amount:.2f} ₽"


def calculate_price(days: int, discount_percent: float = 0) -> float:
    """Рассчитать стоимость подписки на N дней"""
    daily_price = BASE_PRICE_PER_MONTH / 30
    price = daily_price * days
    price *= (1 - discount_percent / 100)
    price *= (1 - GLOBAL_DISCOUNT / 100)
    return round(price, 2)


def get_recommended_durations() -> dict:
    """Получить словарь с ценами для рекомендуемых длительностей"""
    return {
        1: calculate_price(30, 0),
        3: calculate_price(90, 5),
        6: calculate_price(180, 10),
        12: calculate_price(365, 20),
    }


def generate_referral_link(user_id: int, bot_username: str) -> str:
    """Сгенерировать реферальную ссылку"""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def get_user_stats(user: User) -> dict:
    """Получить статистику пользователя для профиля"""
    now = datetime.utcnow()
    is_active = (
        user.sub_type != "none"
        and user.sub_expires_at
        and user.sub_expires_at > now
    )

    sub_type_labels = {
        "none": "Нет",
        "normal": "Обычный доступ",
        "antiblock": "Полный доступ (обход)",
        "both": "Обычный + Полный доступ",
    }

    return {
        "telegram_id": user.telegram_id,
        "balance": user.balance,
        "sub_type": sub_type_labels.get(user.sub_type, user.sub_type),
        "is_active": is_active,
        "expires_at": user.sub_expires_at,
        "subscription_token": user.subscription_token,
    }


# ===== USER OPERATIONS =====

def get_or_create_user(db: Session, telegram_id: int, username: str = None) -> User:
    """Получить или создать пользователя"""
    user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()

    if not user:
        import uuid
        user = User(
            telegram_id=str(telegram_id),
            username=username,
            balance=0.0,
            sub_type="none",
            is_test_used=False,
            subscription_token=str(uuid.uuid4())
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"🆕 Создан новый пользователь: {telegram_id}")

    return user


def get_user_profile(db: Session, telegram_id: int) -> Optional[User]:
    """Получить профиль пользователя"""
    return db.query(User).filter(User.telegram_id == str(telegram_id)).first()


def add_days_to_subscription(user: User, days: int, sub_type: str, db: Session) -> Tuple[bool, str]:
    """Добавить дни подписки пользователю"""
    now = datetime.utcnow()

    if user.sub_expires_at and user.sub_expires_at > now:
        new_expires_at = user.sub_expires_at + timedelta(days=days)
    else:
        new_expires_at = now + timedelta(days=days)

    if user.sub_type == "none":
        user.sub_type = sub_type
    elif user.sub_type != sub_type and sub_type != "none":
        if (user.sub_type == "normal" and sub_type == "antiblock") or \
           (user.sub_type == "antiblock" and sub_type == "normal") or \
           sub_type == "both":
            user.sub_type = "both"

    user.sub_expires_at = new_expires_at
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    return True, f"✅ Подписка продлена до {new_expires_at.strftime('%d.%m.%Y')}"


def remove_subscription_days(db: Session, user: User, days: int) -> User:
    """Убрать дни подписки пользователю"""
    if user.sub_expires_at:
        user.sub_expires_at -= timedelta(days=days)
        if user.sub_expires_at <= datetime.utcnow():
            user.sub_type = "none"
            user.sub_expires_at = None

    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_subscription_url(user: User) -> str:
    """Получить URL подписки пользователя"""
    return f"{API_URL}/sub/{user.subscription_token}"


def format_subscription_info(user: User) -> str:
    """Отформатировать информацию о подписке"""
    if user.sub_type == "none" or not user.sub_expires_at:
        return "❌ Нет активной подписки"

    days_left = (user.sub_expires_at - datetime.utcnow()).days
    sub_type_text = {
        "normal": "📱 Обычный доступ",
        "antiblock": "🛡️ Полный доступ (с обходом)",
        "both": "📱 + 🛡️ Обычный + Полный доступ"
    }.get(user.sub_type, "Неизвестный тип")

    return f"""
✅ {sub_type_text}
📅 Истекает: {user.sub_expires_at.strftime('%d.%m.%Y %H:%M')}
⏳ Осталось: {days_left} дней
🔗 URL: <code>{get_subscription_url(user)}</code>
"""


# ===== BALANCE OPERATIONS =====

def add_balance(db: Session, user: User, amount: float) -> User:
    """Добавить баланс пользователю"""
    user.balance += amount
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def subtract_balance(db: Session, user: User, amount: float) -> bool:
    """Забрать баланс пользователя"""
    if user.balance < amount:
        return False
    user.balance -= amount
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return True


# ===== PAYMENT OPERATIONS =====

def create_payment_request(db: Session, user: User, amount: float) -> Payment:
    """Создать запрос на пополнение"""
    payment = Payment(
        user_id=str(user.telegram_id),
        amount=amount,
        status="pending"
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def approve_payment(db: Session, payment: Payment) -> None:
    """Одобрить платеж"""
    payment.status = "approved"
    payment.updated_at = datetime.utcnow()
    user = db.query(User).filter(User.telegram_id == payment.user_id).first()
    if user:
        user.balance += payment.amount
        user.updated_at = datetime.utcnow()
        db.add(user)
    db.add(payment)
    db.commit()


def reject_payment(db: Session, payment: Payment) -> None:
    """Отклонить платеж"""
    payment.status = "rejected"
    payment.updated_at = datetime.utcnow()
    db.add(payment)
    db.commit()


def get_pending_payments(db: Session) -> list:
    """Получить все ожидающие платежи"""
    return db.query(Payment).filter(Payment.status == "pending").all()


# ===== PROMO CODE OPERATIONS =====

def use_promo_code(db: Session, user: User, code_text: str) -> Tuple[bool, str]:
    """Использовать промокод"""
    promo = db.query(PromoCode).filter(PromoCode.code == code_text.upper()).first()
    if not promo:
        return False, "❌ Промокод не найден"
    if promo.uses_left <= 0:
        return False, "❌ Промокод истек"
    promo.uses_left -= 1
    add_balance(db, user, promo.reward)
    db.add(promo)
    db.commit()
    return True, f"✅ Вам начислено {format_currency(promo.reward)}!"


def create_promo_code(db: Session, code: str, reward: float, uses: int) -> PromoCode:
    """Создать промокод"""
    promo = PromoCode(code=code.upper(), reward=reward, uses_left=uses)
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo


# ===== REFERRAL OPERATIONS =====

def create_referral_link(user: User, bot_username: str) -> str:
    """Создать реферальную ссылку"""
    return f"https://t.me/{bot_username}?start=ref_{user.telegram_id}"


def process_referral(db: Session, referrer_id: str, referred_id: str) -> bool:
    """Обработать реферала"""
    existing = db.query(Referral).filter(Referral.referred_id == referred_id).first()
    if existing:
        return False
    referral = Referral(referrer_id=referrer_id, referred_id=referred_id, reward_given=False)
    db.add(referral)
    db.commit()
    return True


def give_referral_reward(db: Session, referrer_id: str) -> None:
    """Выдать награду за реферала"""
    referrer = db.query(User).filter(User.telegram_id == referrer_id).first()
    if referrer:
        referral = db.query(Referral).filter(
            Referral.referrer_id == referrer_id, Referral.reward_given == False
        ).first()
        if referral:
            add_balance(db, referrer, REFERRAL_REWARD)
            referral.reward_given = True
            db.add(referral)
            db.commit()
            logger.info(f"💰 Реферальный бонус {REFERRAL_REWARD}₽ начислен {referrer_id}")


# ===== ADMIN OPERATIONS =====

def is_admin(db: Session, telegram_id: int) -> bool:
    """Проверить, является ли пользователь админом"""
    from shared.config import OWNER_ID
    if telegram_id == OWNER_ID:
        return True
    admin = db.query(Admin).filter(Admin.telegram_id == str(telegram_id)).first()
    return admin is not None


def get_admin_role(db: Session, telegram_id: int) -> Optional[str]:
    """Получить роль администратора"""
    from shared.config import OWNER_ID
    if telegram_id == OWNER_ID:
        return "owner"
    admin = db.query(Admin).filter(Admin.telegram_id == str(telegram_id)).first()
    return admin.role if admin else None


def add_admin(db: Session, telegram_id: int, role: str = "admin") -> Admin:
    """Добавить администратора"""
    admin = Admin(telegram_id=str(telegram_id), role=role)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def remove_admin(db: Session, telegram_id: int) -> None:
    """Удалить администратора"""
    admin = db.query(Admin).filter(Admin.telegram_id == str(telegram_id)).first()
    if admin:
        db.delete(admin)
        db.commit()


# ===== GLOBAL CONFIG CACHE =====
# In-memory кэш для GlobalConfig — позволяет собирать конфиги без SQL-запросов

config_cache: dict = {}
"""Глобальный кэш конфигов в памяти бота"""


def load_config_cache(db: Session) -> None:
    """Загрузить все GlobalConfig в память"""
    global config_cache
    configs = db.query(GlobalConfig).all()
    config_cache = {config.key: config.value for config in configs}
    logger.info(f"📦 Загружено {len(config_cache)} конфигов в кэш")


def get_config_cached(key: str, default: str = "") -> str:
    """Получить значение из кэша (без SQL)"""
    return config_cache.get(key, default)


def invalidate_config_cache() -> None:
    """Сбросить кэш (вызывать после изменения конфигов)"""
    global config_cache
    config_cache = {}
    logger.info("🔄 Кэш конфигов сброшен")


def get_config(db: Session, key: str, default: str = "") -> str:
    """Получить глобальное значение конфигурации (с кэшем)"""
    cached = get_config_cached(key)
    if cached:
        return cached
    config = db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
    return config.value if config else default


def set_config(db: Session, key: str, value: str) -> GlobalConfig:
    """Установить глобальное значение конфигурации (с инвалидацией кэша)"""
    config = db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
    if config:
        config.value = value
    else:
        config = GlobalConfig(key=key, value=value)
    db.add(config)
    db.commit()
    db.refresh(config)
    invalidate_config_cache()
    return config


# ===== SUBSCRIPTION CONFIG GENERATION =====
# Функции для сборки текстового конфига подписки.
# Используются как FastAPI (через URL), так и ботом (отправка файла в чат).

def get_subscription_config(user: User, db: Session) -> str:
    """
    Собрать конфигурацию подписки для пользователя.
    Работает через кэш — не делает лишних SQL-запросов.
    """
    if not config_cache:
        load_config_cache(db)

    profile_title = get_config_cached("profile-title", "VPN Subscription")
    announce = get_config_cached("announce", "Welcome to VPN")
    update_interval = get_config_cached("profile-update-interval", "1")
    support_url = get_config_cached("support-url", "")
    profile_web_page_url = get_config_cached("profile-web-page-url", "")

    config_text = f"#profile-title: {profile_title}\n"
    config_text += f"#announce: {announce}\n"
    config_text += f"#profile-update-interval: {update_interval}\n"

    if support_url:
        config_text += f"#support-url: {support_url}\n"
    if profile_web_page_url:
        config_text += f"#profile-web-page-url: {profile_web_page_url}\n"

    if user.sub_type in ("normal", "both"):
        base_config_normal = get_config_cached("base_config_normal", "")
        if base_config_normal:
            config_text += base_config_normal.strip() + "\n"

    if user.sub_type in ("antiblock", "both"):
        base_config_antiblock = get_config_cached("base_config_antiblock", "")
        if base_config_antiblock:
            config_text += base_config_antiblock.strip() + "\n"

    return config_text.strip()


def get_expired_config() -> str:
    """Конфигурация для истекшей подписки"""
    return """#profile-title: Срок действия подписки истек!
#announce: ⚠️ Пожалуйста, продлите подписку в Telegram-боте.
vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1?encryption=none&type=tcp#❌_ПОДПИСКА_ИСТЕКЛА_❌
vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1?encryption=none&type=tcp#👇Продлите_в_боте_@твой_бот👇"""


def build_user_config_text(user: User, db: Session) -> str:
    """
    Собрать текст конфига для пользователя с учётом активности подписки.
    Используется ботом при отправке файла.
    """
    now = datetime.utcnow()
    if not user.sub_expires_at or user.sub_expires_at <= now or user.sub_type == "none":
        return get_expired_config()
    return get_subscription_config(user, db)


# ===== STATISTICS =====

def get_statistics(db: Session) -> dict:
    """Получить статистику"""
    from sqlalchemy import func

    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)

    monthly_sales = db.query(func.sum(Payment.amount)).filter(
        Payment.status == "approved", Payment.updated_at >= month_ago
    ).scalar() or 0

    active_users = db.query(User).filter(
        User.sub_expires_at > now, User.sub_type != "none"
    ).count()

    referrals_count = db.query(Referral).filter(Referral.reward_given == True).count()

    total_topup = db.query(func.sum(Payment.amount)).filter(
        Payment.status == "approved"
    ).scalar() or 0

    total_users = db.query(User).count()
    new_users_month = db.query(User).filter(User.created_at >= month_ago).count()

    return {
        "monthly_sales": monthly_sales,
        "active_users": active_users,
        "referrals": referrals_count,
        "total_topup": total_topup,
        "total_users": total_users,
        "new_users_month": new_users_month,
    }