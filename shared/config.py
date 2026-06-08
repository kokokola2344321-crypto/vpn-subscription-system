"""
Конфигурация приложения
"""
import os
from dotenv import load_dotenv

# Загружаем .env из корня проекта
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# === БОТ ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# === API ===
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.maximikvpn.fun")
API_URL = API_BASE_URL  # алиас для обратной совместимости

# === БАЗА ДАННЫХ ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vpn_bot.db")

# === КАНАЛ ===
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@maximikvpn")

# === БАННЕР ===
BANNER_PATH = os.getenv("BANNER_PATH", "/root/vpn_bot/banner.jpg")

# === ЦЕНЫ ===
BASE_PRICE_PER_MONTH = float(os.getenv("BASE_PRICE_PER_MONTH", "100"))
REFERRAL_REWARD = float(os.getenv("REFERRAL_REWARD", "50"))
FREE_TRIAL_DAYS = int(os.getenv("FREE_TRIAL_DAYS", "5"))
TEST_PERIOD_DAYS = int(os.getenv("TEST_PERIOD_DAYS", "5"))
GLOBAL_DISCOUNT = float(os.getenv("GLOBAL_DISCOUNT", "0"))

# === СБП ===
SBP_PHONE = os.getenv("SBP_PHONE", "+7XXXXXXXXXX")
SUPPORT_PHONE = os.getenv("SUPPORT_PHONE", SBP_PHONE)

# === ЦЕНООБРАЗОВАНИЕ ===
PRICING = {
    "1m": {"days": 30, "discount": 0},
    "3m": {"days": 90, "discount": 5},
    "6m": {"days": 180, "discount": 10},
    "12m": {"days": 365, "discount": 20},
}
