# VPN Subscription System

Полнофункциональная система продажи VPN-подписок с Telegram ботом и FastAPI backend. Динамический конструктор текстовых конфигураций с полным управлением через интерфейс администратора.

## 🌟 Особенности

### Архитектура
- **Разделение компонентов**: Отдельный FastAPI backend и Telegram bot на aiogram 3
- **SQLAlchemy ORM**: Гибкая работа с БД (SQLite/PostgreSQL)
- **Чистая архитектура**: Логика бизнеса отделена от хэндлеров
- **Асинхронность**: Полная поддержка async/await

### Функционал

#### 👤 Клиентская часть
- 💳 **Покупка подписок**: Выбор типа (обычный/обход глушилок/оба), гибкий выбор длительности
- 🎁 **Бесплатный тест**: 5 дней доступа с проверкой подписки на канал
- 👥 **Реферальная система**: Генерация инвайт-ссылок, бонусы 50₽
- 💰 **Пополнение баланса**: Интеграция с СБП, управление платежами
- 👤 **Профиль**: Просмотр статуса подписки, URL для клиента
- 📱 **Интуитивный интерфейс**: Кнопки, меню, FSM для управления состоянием

#### ⚙️ Администраторская часть
- **Иерархия прав**: Owner (полный доступ) и Admin (ограниченный доступ)
- 📊 **Статистика**: Продажи за месяц, активные пользователи, прибыль
- 🖥️ **Управление серверами**: Редактирование VLESS конфигов для разных типов доступа
- 👤 **Управление профилем**: Заголовки и объявления в конфигах
- 🎟️ **Промокоды**: Создание и управление кодами с бонусами
- 💳 **Подтверждение платежей**: Inline-кнопки для approv/reject платежей
- 🔐 **Управление администраторами**: Добавление/удаление админов (только Owner)
- ⌨️ **Админ-команды**: `/give_days`, `/take_days`, `/give_money`, `/take_money`, и др.

#### 🔗 FastAPI Backend
- **GET /sub/{token}** - получить конфиг подписки
  - Активная подписка: собирается из компонентов (заголовки + конфиги)
  - Истекшая подписка: специальный текст с уведомлением
- **Динамическая генерация**: Конфиги строятся в реальном времени на основе БД
- **Высокая производительность**: Оптимизирован для частых запросов

## 📋 Структура проекта

```
vpn-subscription-system/
├── backend/
│   ├── __init__.py
│   └── main.py              # FastAPI приложение
├── bot/
│   ├── __init__.py
│   ├── main.py              # Точка входа бота
│   ├── states.py            # FSM состояния
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── client.py        # Клиентские хэндлеры
│   │   └── admin.py         # Админ-хэндлеры
│   └── utils/
│       ├── __init__.py
│       └── helpers.py       # Вспомогательные функции
├── shared/
│   ├── __init__.py
│   ├── models.py            # SQLAlchemy модели
│   └── database.py          # Настройка БД
├── config.py                # Конфигурация приложения
├── pyproject.toml           # Конфигурация пакета (pip install)
├── Dockerfile               # Docker образ
├── docker-compose.yml       # Docker Compose (бот + API)
├── deploy.sh                # Скрипт быстрого развёртывания
├── requirements.txt         # Зависимости
├── .env.example             # Пример файла окружения
└── README.md                # Этот файл
```

## 🚀 Установка и запуск

### 📦 Вариант 1: Установка через GitHub (pip)

Установите пакет напрямую из репозитория:

```bash
pip install git+https://github.com/ВАШ_НИК/vpn-subscription-system.git
```

Или клонируйте репозиторий и установите локально:

```bash
git clone https://github.com/ВАШ_НИК/vpn-subscription-system.git
cd vpn-subscription-system
pip install -e .
```

### 📦 Вариант 2: Классическая установка

#### 1. Клонирование и установка зависимостей

```bash
git clone https://github.com/ВАШ_НИК/vpn-subscription-system.git
cd vpn-subscription-system
pip install -r requirements.txt
```

#### 2. Конфигурация

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Отредактируйте `.env` и установите ваши значения:
- `BOT_TOKEN` — токен вашего Telegram бота (получить у [@BotFather](https://t.me/BotFather))
- `OWNER_ID` — ваш Telegram ID (узнать у [@userinfobot](https://t.me/userinfobot))
- `TELEGRAM_CHANNEL` — канал для проверки подписки (например, `@maximikvpn`)
- `CHANNEL_ID` — ID канала (например, `-1001234567890`)
- `API_BASE_URL` — URL вашего API (например, `https://api.maximikvpn.fun`)
- `SBP_PHONE` — номер для СБП платежей
- `BANNER_PATH` — путь к файлу баннера

#### 3. Инициализация БД

БД инициализируется автоматически при первом запуске.

#### 4. Запуск компонентов

**FastAPI Backend (терминал 1):**

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Telegram Bot (терминал 2):**

```bash
python -m bot.main
```

### 🐳 Вариант 3: Docker (рекомендуется для VPS)

#### 1. Клонирование и настройка

```bash
git clone https://github.com/ВАШ_НИК/vpn-subscription-system.git
cd vpn-subscription-system
cp .env.example .env
nano .env  # отредактируйте
```

#### 2. Запуск через Docker Compose

```bash
mkdir -p data media
docker-compose up -d --build
```

Запустит два контейнера:
- **vpn-api** — FastAPI на порту 8000
- **vpn-bot** — Telegram бот

#### 3. Полезные команды

```bash
docker-compose logs -f api    # Логи API
docker-compose logs -f bot    # Логи бота
docker-compose restart        # Перезапуск
docker-compose down           # Остановка
```

## 🚀 Пошаговая инструкция по деплою на VPS

### 1️⃣ Залить код на GitHub

```bash
cd /путь/к/проекту
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/ВАШ_НИК/vpn-subscription-system.git
git push -u origin main
```

### 2️⃣ Зайти на VPS

```bash
ssh root@77.91.84.43
```

Введите пароль от сервера (если не знаете — уточните у хостинг-провайдера).

### 3️⃣ Клонировать репозиторий

```bash
apt update && apt install -y git
git clone https://github.com/ВАШ_НИК/vpn-subscription-system.git
cd vpn-subscription-system
```

### 4️⃣ Настроить .env

```bash
cp .env.example .env
nano .env
```

Заполните свои данные:

```
BOT_TOKEN=токен_от_BotFather
OWNER_ID=ваш_telegram_id
CHANNEL_ID=-100... (ID канала для проверки подписки)
TELEGRAM_CHANNEL=@maximikvpn
API_BASE_URL=https://api.maximikvpn.fun
DONATION_ALERTS_URL=https://www.donationalerts.com/r/ваш_ник
BANNER_PATH=/root/vpn_bot/banner.jpg
```

**Как сохранить в nano:**
- Редактируете стрелочками
- После редактирования: `Ctrl + X` → `Y` → `Enter`

### 5️⃣ Запустить проект (выберите один вариант)

**Вариант А — deploy.sh (рекомендую):**
```bash
bash deploy.sh
# Выберите 1 — всё сделает сам: Docker, Nginx, SSL
```

**Вариант Б — Docker вручную:**
```bash
# Установка Docker
apt install -y docker.io docker-compose

# Запуск
mkdir -p data media
docker-compose up -d --build
```

**Вариант В — без Docker:**
```bash
pip install -r requirements.txt

# Терминал 1 — API
screen -S api
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# Ctrl+A, D — открепить

# Терминал 2 — Бот
screen -S bot
python -m bot.main
# Ctrl+A, D — открепить
```

### 6️⃣ Настроить Nginx и HTTPS

```bash
apt install -y nginx certbot python3-certbot-nginx
cp nginx.conf.example /etc/nginx/sites-available/vpn-api
nano /etc/nginx/sites-available/vpn-api  # проверьте домен
ln -sf /etc/nginx/sites-available/vpn-api /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d api.maximikvpn.fun
```

### 7️⃣ Загрузить баннер

```bash
mkdir -p /root/vpn_bot
```

Залейте файл `banner.jpg` через `scp` или FileZilla в `/root/vpn_bot/`.

### 8️⃣ Проверить работу

```bash
# Проверка API
curl https://api.maximikvpn.fun/health
# Ответ: {"status": "ok", "message": "VPN API is running"}

# Откройте Telegram и напишите боту /start
```

### 🔥 Полезные команды на VPS

```bash
docker-compose logs -f bot      # Логи бота
docker-compose logs -f api      # Логи API
docker-compose restart          # Перезапуск
docker-compose down && docker-compose up -d --build  # Полный перезапуск с пересборкой

# Если запущено через screen:
screen -r api                   # Посмотреть логи API
screen -r bot                   # Посмотреть логи бота

# Обновление кода с GitHub:
git pull
docker-compose down && docker-compose up -d --build
```

## 📊 Структура БД

### Users (Пользователи)
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | |
| telegram_id | INTEGER UNIQUE | ID в Telegram |
| username | STRING | Имя пользователя |
| balance | FLOAT | Баланс в рублях |
| sub_type | STRING | none/normal/antiblock/both |
| sub_expires_at | DATETIME | Дата окончания подписки |
| referrer_id | STRING | ID пригласившего |
| is_test_used | BOOLEAN | Использован ли тестовый период |
| subscription_token | STRING UNIQUE | UUID для ссылки подписки |
| created_at | DATETIME | Дата создания |
| updated_at | DATETIME | Дата обновления |

### Admins (Администраторы)
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | |
| telegram_id | INTEGER UNIQUE | ID в Telegram |
| role | STRING | owner/admin |
| created_at | DATETIME | |

### GlobalConfig (Конфигурация)
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | |
| key | STRING UNIQUE | Ключ настройки |
| value | STRING | Значение |
| updated_at | DATETIME | |

**Ключи:**
- `profile-title` — заголовок профиля
- `announce` — объявление
- `profile-update-interval` — интервал обновления (по умолч. 1)
- `support-url` — URL поддержки
- `profile-web-page-url` — URL веб-страницы профиля
- `base_config_normal` — VLESS конфиги обычного доступа
- `base_config_antiblock` — VLESS конфиги обхода глушилок
- `global_discount` — глобальная скидка в процентах

### PromoCodes (Промокоды)
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | |
| code | STRING UNIQUE | Код промокода |
| reward | FLOAT | Сумма бонуса |
| uses_left | INTEGER | Сколько осталось активаций |
| created_at | DATETIME | |

### Payments (Платежи)
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | |
| user_id | STRING | ID пользователя |
| amount | FLOAT | Сумма |
| status | STRING | pending/approved/rejected |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### Referrals (Рефералы)
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | |
| referrer_id | STRING | ID пригласившего |
| referred_id | STRING UNIQUE | ID приглашённого |
| reward_given | BOOLEAN | Выдан ли бонус |
| created_at | DATETIME | |

## 🎮 Команды администратора

### Для всех администраторов:
```
/give_days {user_id} {количество}    - Добавить дни подписки
/take_days {user_id} {количество}    - Забрать дни подписки
/give_money {user_id} {сумма}        - Пополнить баланс
/take_money {user_id} {сумма}        - Списать со счета
```

### Только для Owner:
```
/add_admin {user_id}                 - Добавить администратора
/remove_admin {user_id}              - Удалить администратора
```

## 💰 Ценообразование

- **Базовая цена**: 100₽/месяц
- **Скидки по длительности**:
  - 3 месяца: 5% скидка
  - 6 месяцев: 10% скидка
  - 12 месяцев: 20% скидка
- **Глобальная скидка**: Настраивается админом (0-100%)
- **Тестовый период**: 5 дней (бесплатно)
- **Реферальный бонус**: 50₽ за активированного друга

## 🔄 Рабочие процессы

### Процесс покупки подписки
1. Пользователь выбирает тип доступа
2. Выбирает длительность
3. Проверяется баланс
4. Если баланса недостаточно → предлагается пополнить
5. Списываются средства
6. Добавляются дни подписки
7. Пользователю отправляется URL подписки

### Процесс пополнения баланса
1. Пользователь указывает сумму
2. Отправляется номер для СБП
3. Создается заявка на платеж (статус: pending)
4. Админ видит заявку и может подтвердить/отклонить
5. При подтверждении баланс пополняется

### Получение конфига подписки
1. Клиент (Hiddify) делает GET запрос: `https://api.maximikvpn.fun/sub/{token}`
2. API проверяет наличие и активность подписки
3. Если подписка активна:
   - Собирает заголовки из GlobalConfig
   - Добавляет соответствующие VLESS конфиги
   - Возвращает text/plain конфиг
4. Если подписка истекла:
   - Возвращает специальный конфиг с уведомлением об истечении

## 📝 Пример конфигурации подписки

```
#profile-title: VPN Subscription
#announce: Welcome! Your subscription is active
#profile-update-interval: 1
vless://uuid1@server1.com:443?encryption=none&type=tcp#Server 1
vless://uuid2@server2.com:443?encryption=none&type=tcp#Server 2
vless://uuid3@server3.com:443?encryption=none&type=tcp#Anti-block Server 1
vless://uuid4@server4.com:443?encryption=none&type=tcp#Anti-block Server 2
```

## 🔐 Безопасность

- **Приватные команды**: Только администраторы могут использовать админ-команды
- **Проверка токенов**: Каждый запрос к API проверяет валидность токена
- **Защита платежей**: Платежи требуют подтверждения администратора
- **Защита от дублей**: Уникальные токены подписки для каждого пользователя

## 🛠️ Разработка и расширение

### Добавление новых функций
1. **Новый хэндлер**: Добавьте функцию в `bot/handlers/client.py` или `admin.py`
2. **Новое состояние FSM**: Добавьте в `bot/states.py`
3. **Новый маршрут API**: Добавьте в `backend/main.py`
4. **Новая таблица БД**: Добавьте модель в `shared/models.py`

### Использование PostgreSQL
Замените `DATABASE_URL` в `.env`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/vpn_db
```

## 📚 Зависимости

- **fastapi** >=0.104.0 — веб-фреймворк
- **uvicorn** >=0.24.0 — ASGI сервер
- **aiogram** >=3.3.0 — Telegram bot API
- **sqlalchemy** >=2.0.23 — ORM для БД
- **pydantic** >=2.5.0 — валидация данных
- **python-dotenv** >=1.0.0 — управление конфигурацией

## 🐛 Troubleshooting

### Бот не запускается
- Проверьте `BOT_TOKEN` в `.env`
- Убедитесь, что все зависимости установлены

### API недоступен
- Проверьте, что FastAPI запущен на правильном порту
- Убедитесь, что `DATABASE_URL` корректен

### Платежи не подтверждаются
- Проверьте, что админ правильно находится в базе
- Убедитесь, что статус платежа обновляется в БД

## 📞 Поддержка
Для вопросов и предложений создавайте issues в репозитории.

## 📄 Лицензия
MIT License — свободно используйте для своих проектов.