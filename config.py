"""
Конфигурация приложения (корневой файл)
Импортирует все настройки из shared.config и добавляет специфичные
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === Telegram Bot ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@your_channel")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# === FastAPI ===
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.maximikvpn.fun")
DOMAIN = os.getenv("DOMAIN", "api.maximikvpn.fun")

# === Database ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vpn_system.db")

# === VPS Configuration ===
VPS_IP = "77.91.84.43"
BANNER_PATH = os.getenv("BANNER_PATH", "./media/banner.png")

# === Pricing ===
BASE_PRICE_PER_MONTH = 100
DISCOUNT_3_MONTHS = 0.05
DISCOUNT_6_MONTHS = 0.10
DISCOUNT_12_MONTHS = 0.20
TEST_PERIOD_DAYS = 5
REFERRAL_BONUS = 50

# === Payment ===
SBP_PHONE = os.getenv("SBP_PHONE", "+7XXXXXXXXXX")

# === Logging ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
