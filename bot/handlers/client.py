"""
Клиентские хэндлеры для Telegram-бота
"""
import io
import logging
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, BufferedInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command

from bot.states import ClientStates
from bot.utils.helpers import (
    get_or_create_user, get_user_profile, add_days_to_subscription,
    get_subscription_url, format_subscription_info, add_balance,
    subtract_balance, create_payment_request, use_promo_code,
    create_referral_link, process_referral, give_referral_reward,
    get_config, format_currency, calculate_price, get_recommended_durations,
    get_user_stats, generate_referral_link, build_user_config_text
)
from shared.database import SessionLocal
from shared.models import User, Payment
from shared.config import (
    BANNER_PATH, CHANNEL_ID, SUPPORT_PHONE, API_URL,
    BASE_PRICE_PER_MONTH, REFERRAL_REWARD, FREE_TRIAL_DAYS,
    TELEGRAM_CHANNEL, API_BASE_URL, TEST_PERIOD_DAYS,
    SBP_PHONE, DONATION_ALERTS_URL
)

logger = logging.getLogger(__name__)
router = Router()

purchase_data = {}

SUB_TYPE_LABELS = {
    "normal": "📡 VLESS",
    "antiblock": "🛡️ Обход глушилок",
    "both": "🚀 VLESS + Обход глушилок"
}


# === KEYBOARDS ===

def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню (inline-кнопки под сообщением)"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="menu_buy")],
            [InlineKeyboardButton(text="🎁 Бесплатная подписка", callback_data="menu_free")],
            [InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu_profile")],
            [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="menu_referral")],
            [InlineKeyboardButton(text="📢 Наш канал", callback_data="menu_channel")],
            [InlineKeyboardButton(text="ℹ️ Поддержка", callback_data="menu_support")],
        ]
    )


def subscription_type_kb() -> InlineKeyboardMarkup:
    """Выбор типа подписки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📡 VLESS (100₽/мес)", callback_data="sub_normal")],
            [InlineKeyboardButton(text="🛡️ Обход глушилок (100₽/мес)", callback_data="sub_antiblock")],
            [InlineKeyboardButton(text="🚀 VLESS + Обход глушилок (100₽/мес)", callback_data="sub_both")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )


def duration_kb() -> InlineKeyboardMarkup:
    """Выбор длительности подписки"""
    durations = get_recommended_durations()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"📅 1 месяц ({format_currency(durations[1])})", callback_data="dur_1m")],
            [InlineKeyboardButton(text=f"📅 3 месяца ({format_currency(durations[3])})", callback_data="dur_3m")],
            [InlineKeyboardButton(text=f"📅 6 месяцев ({format_currency(durations[6])})", callback_data="dur_6m")],
            [InlineKeyboardButton(text=f"📅 1 год ({format_currency(durations[12])})", callback_data="dur_12m")],
            [InlineKeyboardButton(text="✍️ Указать срок вручную", callback_data="dur_custom")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )


# === COMMANDS ===

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    db = SessionLocal()
    try:
        args = message.text.split()
        referrer_id = None
        if len(args) > 1 and args[1].startswith("ref_"):
            try:
                referrer_id = int(args[1].replace("ref_", ""))
            except ValueError:
                pass

        user = get_or_create_user(db, message.from_user.id, message.from_user.username)

        if referrer_id and referrer_id != message.from_user.id:
            if user.created_at and (datetime.utcnow() - user.created_at).seconds < 60:
                process_referral(db, str(referrer_id), str(message.from_user.id))
                user.referrer_id = str(referrer_id)
                db.commit()
                logger.info(f"👥 Реферал: {referrer_id} -> {message.from_user.id}")
    finally:
        db.close()

    welcome_text = (
        "👋 Добро пожаловать в MaxiNet VPN!\n\n"
        "Здесь вы можете:\n"
        "• 💳 Купить VPN подписку\n"
        "• 🎁 Получить 5 дней бесплатного доступа\n"
        "• 👥 Приглашать друзей и зарабатывать\n"
        "• 📊 Отслеживать активность подписки\n\n"
        "Выберите действие ниже 👇"
    )

    try:
        await message.answer_photo(
            photo=FSInputFile(BANNER_PATH),
            caption=welcome_text,
            reply_markup=main_menu_kb()
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить баннер: {e}")
        await message.answer(welcome_text, reply_markup=main_menu_kb())

    await state.set_state(ClientStates.main_menu)


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    await show_profile(message)


@router.message(Command("buy"))
async def cmd_buy(message: Message, state: FSMContext):
    await message.answer("Выберите тип доступа:", reply_markup=subscription_type_kb())
    await state.set_state(ClientStates.select_sub_type)


# === MAIN MENU CALLBACKS ===

@router.callback_query(F.data == "menu_buy")
async def menu_buy(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Выберите тип доступа:", reply_markup=subscription_type_kb())
    await state.set_state(ClientStates.select_sub_type)


@router.callback_query(F.data == "menu_free")
async def menu_free(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    msg = callback.message
    msg.from_user = callback.from_user
    msg.text = "🎁 Бесплатная подписка"
    await handle_free_trial(msg, state)


@router.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery):
    await callback.answer()
    await show_profile(callback.message)


@router.callback_query(F.data == "menu_referral")
async def menu_referral(callback: CallbackQuery):
    await callback.answer()
    bot_info = await callback.bot.get_me()
    referral_link = generate_referral_link(callback.from_user.id, bot_info.username)
    await callback.message.edit_text(
        "👥 Реферальная система:\n\n"
        "📌 Приглашайте друзей по ссылке ниже и получайте 50₽ за каждого, "
        "кто активирует бесплатный период!\n\n"
        f"🔗 Ваша ссылка:\n`{referral_link}`\n\n"
        "⚠️ Друг должен быть новым пользователем бота и активировать 5-дневный "
        "тестовый период, чтобы вы получили бонус.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]]
        )
    )


@router.callback_query(F.data == "menu_channel")
async def menu_channel(callback: CallbackQuery):
    await callback.answer()
    channel_username = TELEGRAM_CHANNEL.lstrip("@")
    await callback.message.edit_text(
        f"📢 Наш канал: {TELEGRAM_CHANNEL}\n\nПодпишитесь, чтобы получать новости и обновления!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Перейти в канал", url=f"https://t.me/{channel_username}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
            ]
        )
    )


@router.callback_query(F.data == "menu_support")
async def menu_support(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "ℹ️ Поддержка\n\n❓ Возникли вопросы? Напишите нам!\n\n"
        "💬 Telegram: @maximikvpn\n\nМы ответим в течение 24 часов.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]]
        )
    )


# === PROFILE ===

async def show_profile(message: Message):
    """Показать профиль пользователя"""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, message.from_user.id, message.from_user.username)
        stats = get_user_stats(user)

        profile_text = f"""
👤 Ваш профиль:

🔐 Telegram ID: {stats['telegram_id']}
💰 Баланс: {format_currency(stats['balance'])}
📊 Тип подписки: {stats['sub_type']}
⏰ Активная: {'✅ Да' if stats['is_active'] else '❌ Нет'}
📅 Истекает: {stats['expires_at'].strftime('%d.%m.%Y') if stats['expires_at'] else 'Не активна'}
🔗 URL подписки: `{API_BASE_URL}/sub/{stats['subscription_token']}`
"""

        profile_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📄 Скачать конфиг", callback_data="download_config")],
                [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="add_balance")],
                [InlineKeyboardButton(text="⏳ Продлить подписку", callback_data="extend_sub")],
                [InlineKeyboardButton(text="🎟️ Активировать промокод", callback_data="activate_promo")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
            ]
        )

        await message.answer(profile_text, reply_markup=profile_kb, parse_mode="Markdown")
    finally:
        db.close()


# === FREE TRIAL ===

async def handle_free_trial(message: Message, state: FSMContext):
    """Обработка бесплатной подписки"""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, message.from_user.id, message.from_user.username)
        if user.is_test_used:
            await message.answer("❌ Вы уже использовали бесплатный период!")
            return

        try:
            chat_member = await message.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=message.from_user.id)
            is_subscribed = chat_member.status in ("member", "administrator", "creator")
        except Exception:
            is_subscribed = True

        if not is_subscribed:
            channel_username = TELEGRAM_CHANNEL.lstrip("@")
            await message.answer(
                f"❌ Чтобы получить бесплатную подписку, подпишитесь на наш канал:\n\n{TELEGRAM_CHANNEL}",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📢 Подписаться", url=f"https://t.me/{channel_username}")],
                        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")]
                    ]
                )
            )
            return

        success, msg = add_days_to_subscription(user, TEST_PERIOD_DAYS, "both", db)
        user.is_test_used = True
        db.commit()

        if success:
            await message.answer(
                f"✅ Вам активирована {TEST_PERIOD_DAYS}-дневная бесплатная подписка (оба варианта)!\n\n"
                f"🔗 Ваша ссылка: `{API_BASE_URL}/sub/{user.subscription_token}`\n\n🎉 Приятного использования!",
                parse_mode="Markdown"
            )

            if user.referrer_id:
                from shared.models import Referral
                referral = db.query(Referral).filter(
                    Referral.referred_id == str(message.from_user.id), Referral.reward_given == False
                ).first()
                if referral:
                    give_referral_reward(db, user.referrer_id)
                    try:
                        await message.bot.send_message(
                            int(user.referrer_id),
                            f"🎉 Ваш друг @{message.from_user.username or message.from_user.id} "
                            f"активировал тестовый период!\n💰 Вам начислено {format_currency(REFERRAL_REWARD)}!"
                        )
                    except Exception as e:
                        logger.error(f"Не удалось уведомить реферера: {e}")
            logger.info(f"🎁 Тестовая подписка активирована для {message.from_user.id}")
        else:
            await message.answer(f"❌ Ошибка: {msg}")
    finally:
        db.close()


@router.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        chat_member = await callback.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=callback.from_user.id)
        is_subscribed = chat_member.status in ("member", "administrator", "creator")
    except Exception:
        is_subscribed = True

    if is_subscribed:
        await callback.message.delete()
        msg = callback.message
        msg.from_user = callback.from_user
        msg.text = "🎁 Бесплатная подписка"
        await handle_free_trial(msg, state)
    else:
        await callback.answer("❌ Вы еще не подписались на канал!", show_alert=True)


# === SUBSCRIPTION PURCHASE ===

@router.callback_query(F.data.startswith("sub_"))
async def select_subscription_type(callback: CallbackQuery, state: FSMContext):
    sub_type = callback.data.replace("sub_", "")
    if sub_type == "cancel":
        await callback.message.delete()
        await callback.message.answer("❌ Отменено", reply_markup=main_menu_kb())
        await state.set_state(ClientStates.main_menu)
        return

    purchase_data[callback.from_user.id] = {"sub_type": sub_type}
    await callback.message.edit_text("Выберите длительность подписки:", reply_markup=duration_kb())
    await state.set_state(ClientStates.select_duration)


@router.callback_query(F.data.startswith("dur_"))
async def select_duration(callback: CallbackQuery, state: FSMContext):
    duration_str = callback.data.replace("dur_", "")

    if duration_str == "custom":
        await callback.message.edit_text(
            "✍️ Введите количество дней для подписки:\n\nЦена рассчитывается: 100₽ / 30 дней = 3.33₽ за день"
        )
        await state.set_state(ClientStates.entering_custom_days)
        return

    duration_map = {"1m": (30, 0), "3m": (90, 5), "6m": (180, 10), "12m": (365, 20)}
    days, discount = duration_map[duration_str]
    price = calculate_price(days, discount)

    if callback.from_user.id not in purchase_data:
        purchase_data[callback.from_user.id] = {}
    purchase_data[callback.from_user.id].update({"days": days, "price": price})

    sub_type = purchase_data[callback.from_user.id]["sub_type"]
    confirm_text = f"""
✅ Подтверждение покупки:

📊 Тип: {SUB_TYPE_LABELS.get(sub_type, sub_type)}
📅 На период: {days} дней
💰 Цена: {format_currency(price)}

Нажмите кнопку ниже для подтверждения.
"""

    confirm_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_purchase")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_purchase")]
        ]
    )
    await callback.message.edit_text(confirm_text, reply_markup=confirm_kb)
    await state.set_state(ClientStates.confirming_payment)


@router.message(ClientStates.entering_custom_days)
async def enter_custom_days(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        if days <= 0:
            await message.answer("❌ Введите положительное число дней!")
            return
        if days > 3650:
            await message.answer("❌ Максимум 3650 дней (10 лет)!")
            return

        price = calculate_price(days)
        if message.from_user.id not in purchase_data:
            purchase_data[message.from_user.id] = {}
        purchase_data[message.from_user.id].update({"days": days, "price": price})

        sub_type = purchase_data[message.from_user.id]["sub_type"]
        confirm_text = f"""
✅ Подтверждение покупки:

📊 Тип: {SUB_TYPE_LABELS.get(sub_type, sub_type)}
📅 На период: {days} дней
💰 Цена: {format_currency(price)}

Нажмите кнопку ниже для подтверждения.
"""
        confirm_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_purchase")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_purchase")]
            ]
        )
        await message.answer(confirm_text, reply_markup=confirm_kb)
        await state.set_state(ClientStates.confirming_payment)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число!")


@router.callback_query(F.data == "confirm_purchase")
async def confirm_purchase(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in purchase_data:
        await callback.answer("❌ Ошибка: данные покупки потеряны", show_alert=True)
        return

    purchase = purchase_data[user_id]
    price = purchase["price"]

    db = SessionLocal()
    try:
        user = get_or_create_user(db, user_id, callback.from_user.username)
        if user.balance < price:
            await callback.message.edit_text(
                f"❌ Недостаточно средств!\n\n💰 Нужно: {format_currency(price)}\n"
                f"💰 У вас: {format_currency(user.balance)}\n"
                f"💰 Не хватает: {format_currency(price - user.balance)}\n\nПополните баланс, чтобы завершить покупку.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="add_balance")],
                        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_purchase")]
                    ]
                )
            )
            return

        user.balance -= price
        success, msg = add_days_to_subscription(user, purchase["days"], purchase["sub_type"], db)

        if success:
            sub_label = SUB_TYPE_LABELS.get(purchase['sub_type'], purchase['sub_type'].upper())
            await callback.message.edit_text(
                f"✅ Покупка успешна!\n\n📊 Тип: {sub_label}\n"
                f"📅 На период: {purchase['days']} дней\n💰 Списано: {format_currency(price)}\n"
                f"💳 Оставшийся баланс: {format_currency(user.balance)}\n\n"
                f"🔗 Ваша ссылка:\n`{API_BASE_URL}/sub/{user.subscription_token}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]]
                )
            )
            logger.info(f"✅ Покупка: user={user_id}, price={price}, days={purchase['days']}")
        else:
            await callback.message.edit_text(f"❌ Ошибка при добавлении подписки!\n\n{msg}")
    finally:
        db.close()
        if user_id in purchase_data:
            del purchase_data[user_id]

    await state.set_state(ClientStates.main_menu)


@router.callback_query(F.data.in_(["cancel_purchase", "cancel"]))
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in purchase_data:
        del purchase_data[callback.from_user.id]
    await callback.message.delete()
    await callback.message.answer("❌ Отменено", reply_markup=main_menu_kb())
    await state.set_state(ClientStates.main_menu)


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("👋 Выберите действие:", reply_markup=main_menu_kb())
    await state.set_state(ClientStates.main_menu)


# === BALANCE MANAGEMENT ===

@router.callback_query(F.data == "add_balance")
async def add_balance_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💳 Пополнение баланса\n\nВведите сумму в рублях, которую вы хотите добавить на счет:")
    await state.set_state(ClientStates.entering_top_up_amount)


@router.message(ClientStates.entering_top_up_amount)
async def enter_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля!")
            return
        if amount > 100000:
            await message.answer("❌ Максимальная сумма пополнения — 100 000 ₽")
            return

        purchase_data[message.from_user.id] = {"payment_amount": amount}

        await message.answer(
            f"✅ Сумма: {format_currency(amount)}\n\n"
            f"💳 Оплатите донат по ссылке:\n\n🔗 {DONATION_ALERTS_URL}\n\n"
            "После оплаты нажмите кнопку ниже. Администратор проверит и пополнит баланс.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 Перейти к оплате", url=DONATION_ALERTS_URL)],
                    [InlineKeyboardButton(text="✅ Я оплатил", callback_data="confirm_payment")],
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
                ]
            )
        )
        await state.set_state(ClientStates.confirming_payment)
    except ValueError:
        await message.answer("❌ Введите корректную сумму!")


@router.callback_query(F.data == "confirm_payment")
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in purchase_data or "payment_amount" not in purchase_data[user_id]:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    amount = purchase_data[user_id]["payment_amount"]
    db = SessionLocal()
    try:
        user = get_or_create_user(db, user_id, callback.from_user.username)
        payment = create_payment_request(db, user, amount)

        await callback.message.edit_text(
            f"✅ Заявка на пополнение создана!\n\n💰 Сумма: {format_currency(amount)}\n"
            f"📊 Статус: ⏳ Ожидание подтверждения\n\n"
            "Администратор подтвердит платеж в ближайшее время.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]]
            )
        )

        from bot.handlers.admin import notify_admin_payment
        await notify_admin_payment(callback.bot, payment, user)
        logger.info(f"💳 Заявка на оплату: user={user_id}, amount={amount}")
    finally:
        db.close()
        if user_id in purchase_data:
            del purchase_data[user_id]

    await state.set_state(ClientStates.main_menu)


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in purchase_data:
        del purchase_data[callback.from_user.id]
    await callback.message.delete()
    await callback.message.answer("❌ Отменено", reply_markup=main_menu_kb())
    await state.set_state(ClientStates.main_menu)


@router.callback_query(F.data == "download_config")
async def download_config(callback: CallbackQuery):
    await callback.answer("⏳ Генерирую конфиг...")
    db = SessionLocal()
    try:
        user = get_or_create_user(db, callback.from_user.id, callback.from_user.username)
        config_text = build_user_config_text(user, db)
        file_data = io.BytesIO(config_text.encode("utf-8"))
        filename = f"vpn_config_{user.subscription_token[:8]}.txt"

        await callback.message.answer_document(
            document=BufferedInputFile(file_data.read(), filename=filename),
            caption="📄 Ваш конфиг подписки\n\nℹ️ Если подписка истекла — продлите её в меню «⏳ Продлить»"
        )
        logger.info(f"📄 Конфиг отправлен пользователю {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке конфига: {e}")
        await callback.message.answer("❌ Ошибка при генерации конфига")
    finally:
        db.close()


@router.callback_query(F.data == "extend_sub")
async def extend_subscription(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⏳ Продление подписки\n\nВыберите тип доступа для продления:", reply_markup=subscription_type_kb())
    await state.set_state(ClientStates.select_sub_type)


@router.callback_query(F.data == "activate_promo")
async def activate_promo(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎟️ Введите промокод:")
    await state.set_state(ClientStates.entering_promo_code)


@router.message(ClientStates.entering_promo_code)
async def process_promo_code(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_or_create_user(db, message.from_user.id, message.from_user.username)
        success, msg = use_promo_code(db, user, message.text.strip())
        await message.answer(msg, reply_markup=main_menu_kb())
    finally:
        db.close()
    await state.set_state(ClientStates.main_menu)