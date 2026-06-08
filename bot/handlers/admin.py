"""
Хэндлеры администраторской части Telegram бота
"""
import logging
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from sqlalchemy.orm import Session
from sqlalchemy import func

from shared.database import SessionLocal
from shared.models import User, Admin, GlobalConfig, PromoCode, Payment, Referral
from bot.states import AdminStates
from bot.utils.helpers import (
    format_currency, add_days_to_subscription, get_statistics,
    get_config, set_config, add_admin, remove_admin
)
from shared.config import OWNER_ID

logger = logging.getLogger(__name__)
router = Router()

# Временное хранилище для админ-данных
admin_data = {}


# === UTILS ===

def is_admin(telegram_id: int) -> bool:
    """Проверка является ли пользователь администратором"""
    if telegram_id == OWNER_ID:
        return True

    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.telegram_id == str(telegram_id)).first()
        return admin is not None
    finally:
        db.close()


def is_owner(telegram_id: int) -> bool:
    """Проверка является ли пользователь оунером"""
    return telegram_id == OWNER_ID


def admin_menu_kb() -> ReplyKeyboardMarkup:
    """Клавиатура админ-меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🖥️ Управление серверами")],
            [KeyboardButton(text="👤 Профиль и объявления")],
            [KeyboardButton(text="💰 Скидки")],
            [KeyboardButton(text="🎟️ Промокоды")],
            [KeyboardButton(text="💰 Заявки на оплату")],
            [KeyboardButton(text="🔐 Управление администраторами")],
            [KeyboardButton(text="🔙 Выход")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


async def notify_admin_payment(bot: Bot, payment: Payment, user: User):
    """Уведомить администратора о новой заявке на оплату"""
    db = SessionLocal()
    try:
        admins = db.query(Admin).all()

        text = f"""
💳 Новая заявка на пополнение баланса!

👤 Пользователь: {user.username or user.telegram_id}
💰 Сумма: {format_currency(payment.amount)}
🆔 ID платежа: {payment.id}
⏰ Время: {payment.created_at.strftime('%d.%m.%Y %H:%M')}

Подтвердите или отклоните заявку:
"""

        confirm_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить",
                        callback_data=f"approve_payment_{payment.id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"reject_payment_{payment.id}"
                    )
                ]
            ]
        )

        # Уведомляем OWNER
        try:
            await bot.send_message(OWNER_ID, text, reply_markup=confirm_kb)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление owner: {e}")

        # Уведомляем всех админов
        for admin in admins:
            try:
                await bot.send_message(
                    int(admin.telegram_id),
                    text,
                    reply_markup=confirm_kb
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление админу {admin.telegram_id}: {e}")

    finally:
        db.close()


# === COMMANDS ===

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Вход в админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели!")
        return

    await message.answer(
        "⚙️ Админ-панель\n\n"
        "Выберите действие:",
        reply_markup=admin_menu_kb()
    )
    await state.set_state(AdminStates.admin_menu)


@router.message(AdminStates.admin_menu)
async def handle_admin_menu(message: Message, state: FSMContext):
    """Обработка админ-меню"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен!")
        return

    text = message.text

    if text == "📊 Статистика":
        await show_statistics(message)

    elif text == "🖥️ Управление серверами":
        await show_server_management(message)

    elif text == "👤 Профиль и объявления":
        await show_profile_management(message)

    elif text == "💰 Скидки":
        await show_discount_management(message, state)

    elif text == "🎟️ Промокоды":
        await show_promo_management(message)

    elif text == "💰 Заявки на оплату":
        await show_payment_requests(message)

    elif text == "🔐 Управление администраторами":
        if not is_owner(message.from_user.id):
            await message.answer("❌ Только владелец может управлять администраторами!")
            return
        await show_admin_management(message)

    elif text == "🔙 Выход":
        await message.answer("👋 Вы вышли из админ-панели")
        await state.clear()


# === STATISTICS ===

async def show_statistics(message: Message):
    """Показать статистику"""
    db = SessionLocal()
    try:
        stats = get_statistics(db)

        stats_text = f"""
📊 Статистика системы

📈 За последние 30 дней:
💰 Продажи: {format_currency(stats['monthly_sales'])}
👥 Новых пользователей: {stats['new_users_month']}

📅 Всего:
👤 Активных подписок: {stats['active_users']}
📋 Всего пользователей: {stats['total_users']}
👥 Привлечено рефералами: {stats['referrals']}
💵 Общая сумма пополнений: {format_currency(stats['total_topup'])}
"""

        await message.answer(stats_text)

    finally:
        db.close()


# === SERVER MANAGEMENT ===

async def show_server_management(message: Message):
    """Показать меню управления серверами"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Обычные сервера", callback_data="edit_normal_servers")],
            [InlineKeyboardButton(text="🟣 Сервера обхода", callback_data="edit_antiblock_servers")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin")]
        ]
    )

    await message.answer("🖥️ Управление серверами\n\nВыберите, что хотите отредактировать:", reply_markup=kb)


@router.callback_query(F.data == "edit_normal_servers")
async def edit_normal_servers(callback: CallbackQuery, state: FSMContext):
    """Редактирование обычных серверов"""
    await callback.message.edit_text(
        "🟢 Обычные сервера\n\n"
        "Отправьте список VLESS-ссылок (каждая на новой строке):"
    )
    admin_data[callback.from_user.id] = "normal_config"
    await state.set_state(AdminStates.entering_normal_config)


@router.message(AdminStates.entering_normal_config)
async def save_normal_config(message: Message, state: FSMContext):
    """Сохранение конфига обычных серверов"""
    db = SessionLocal()
    try:
        set_config(db, "base_config_normal", message.text)

        await message.answer(
            "✅ Конфигурация обычных серверов сохранена!",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⚙️ Админ-панель")]],
                resize_keyboard=True
            )
        )

        logger.info("🟢 Normal config updated")
    except Exception as e:
        logger.error(f"Error saving normal config: {e}")
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        db.close()
        if message.from_user.id in admin_data:
            del admin_data[message.from_user.id]
        await state.clear()


@router.callback_query(F.data == "edit_antiblock_servers")
async def edit_antiblock_servers(callback: CallbackQuery, state: FSMContext):
    """Редактирование серверов обхода"""
    await callback.message.edit_text(
        "🟣 Сервера обхода глушилок\n\n"
        "Отправьте список VLESS-ссылок (каждая на новой строке):"
    )
    admin_data[callback.from_user.id] = "antiblock_config"
    await state.set_state(AdminStates.entering_antiblock_config)


@router.message(AdminStates.entering_antiblock_config)
async def save_antiblock_config(message: Message, state: FSMContext):
    """Сохранение конфига серверов обхода"""
    db = SessionLocal()
    try:
        set_config(db, "base_config_antiblock", message.text)

        await message.answer(
            "✅ Конфигурация серверов обхода сохранена!",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⚙️ Админ-панель")]],
                resize_keyboard=True
            )
        )

        logger.info("🟣 Antiblock config updated")
    except Exception as e:
        logger.error(f"Error saving antiblock config: {e}")
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        db.close()
        if message.from_user.id in admin_data:
            del admin_data[message.from_user.id]
        await state.clear()


# === PROFILE MANAGEMENT ===

async def show_profile_management(message: Message):
    """Показать меню управления профилем"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Заголовок профиля", callback_data="edit_profile_title")],
            [InlineKeyboardButton(text="📢 Объявление", callback_data="edit_announce")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin")]
        ]
    )

    await message.answer("👤 Управление профилем\n\nВыберите, что хотите изменить:", reply_markup=kb)


@router.callback_query(F.data == "edit_profile_title")
async def edit_profile_title(callback: CallbackQuery, state: FSMContext):
    """Редактирование заголовка профиля"""
    await callback.message.edit_text(
        "📝 Введите новый заголовок профиля (profile-title):"
    )
    admin_data[callback.from_user.id] = "profile_title"
    await state.set_state(AdminStates.entering_profile_title)


@router.message(AdminStates.entering_profile_title)
async def save_profile_title(message: Message, state: FSMContext):
    """Сохранение заголовка профиля"""
    db = SessionLocal()
    try:
        set_config(db, "profile-title", message.text)

        await message.answer(
            f"✅ Заголовок профиля изменен на:\n\n{message.text}",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⚙️ Админ-панель")]],
                resize_keyboard=True
            )
        )
    finally:
        db.close()
        await state.clear()


@router.callback_query(F.data == "edit_announce")
async def edit_announce(callback: CallbackQuery, state: FSMContext):
    """Редактирование объявления"""
    await callback.message.edit_text(
        "📢 Введите новое объявление (announce):"
    )
    admin_data[callback.from_user.id] = "announce"
    await state.set_state(AdminStates.entering_profile_announce)


@router.message(AdminStates.entering_profile_announce)
async def save_announce(message: Message, state: FSMContext):
    """Сохранение объявления"""
    db = SessionLocal()
    try:
        set_config(db, "announce", message.text)

        await message.answer(
            f"✅ Объявление изменено на:\n\n{message.text}",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⚙️ Админ-панель")]],
                resize_keyboard=True
            )
        )
    finally:
        db.close()
        await state.clear()


# === DISCOUNT MANAGEMENT ===

async def show_discount_management(message: Message, state: FSMContext):
    """Показать меню управления скидками"""
    db = SessionLocal()
    try:
        current_discount = get_config(db, "global_discount", "0")
        await message.answer(
            f"💰 Управление скидками\n\n"
            f"Текущая глобальная скидка: {current_discount}%\n\n"
            "Введите новое значение скидки (0-100):"
        )
        await state.set_state(AdminStates.entering_discount)
    finally:
        db.close()


@router.message(AdminStates.entering_discount)
async def save_discount(message: Message, state: FSMContext):
    """Сохранение глобальной скидки"""
    try:
        discount = float(message.text)
        if discount < 0 or discount > 100:
            await message.answer("❌ Скидка должна быть от 0 до 100!")
            return

        db = SessionLocal()
        try:
            set_config(db, "global_discount", str(discount))
            # Also update the in-memory config
            from shared.config import GLOBAL_DISCOUNT
            # Note: GLOBAL_DISCOUNT is loaded from env, but we store in DB
            # The actual discount will be read from DB in helpers.py

            await message.answer(
                f"✅ Глобальная скидка установлена: {discount}%",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⚙️ Админ-панель")]],
                    resize_keyboard=True
                )
            )
            logger.info(f"💰 Global discount set to {discount}%")
        finally:
            db.close()
            await state.clear()

    except ValueError:
        await message.answer("❌ Введите число!")


# === PROMO CODES ===

async def show_promo_management(message: Message):
    """Показать меню управления промокодами"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать промокод", callback_data="create_promo")],
            [InlineKeyboardButton(text="📋 Список промокодов", callback_data="list_promos")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin")]
        ]
    )

    await message.answer("🎟️ Управление промокодами", reply_markup=kb)


@router.callback_query(F.data == "create_promo")
async def create_promo(callback: CallbackQuery, state: FSMContext):
    """Создание промокода"""
    await callback.message.edit_text(
        "🎟️ Создание промокода\n\n"
        "Введите текст промокода (без пробелов, латиница/цифры):"
    )
    admin_data[callback.from_user.id] = {}
    await state.set_state(AdminStates.entering_promo_code_text)


@router.message(AdminStates.entering_promo_code_text)
async def enter_promo_text(message: Message, state: FSMContext):
    """Ввод текста промокода"""
    if message.from_user.id not in admin_data:
        admin_data[message.from_user.id] = {}

    admin_data[message.from_user.id]["code"] = message.text.strip().upper()

    await message.answer("Введите размер бонуса в рублях:")
    await state.set_state(AdminStates.entering_promo_reward)


@router.message(AdminStates.entering_promo_reward)
async def enter_promo_reward(message: Message, state: FSMContext):
    """Ввод размера бонуса"""
    try:
        reward = float(message.text)
        if reward <= 0:
            await message.answer("❌ Бонус должен быть больше нуля!")
            return

        admin_data[message.from_user.id]["reward"] = reward

        await message.answer("Введите количество активаций:")
        await state.set_state(AdminStates.entering_promo_uses)

    except ValueError:
        await message.answer("❌ Введите число!")


@router.message(AdminStates.entering_promo_uses)
async def enter_promo_uses(message: Message, state: FSMContext):
    """Ввод количества активаций"""
    try:
        uses = int(message.text)
        if uses <= 0:
            await message.answer("❌ Количество должно быть больше нуля!")
            return

        user_id = message.from_user.id

        db = SessionLocal()
        try:
            promo = PromoCode(
                code=admin_data[user_id]["code"],
                reward=admin_data[user_id]["reward"],
                uses_left=uses
            )
            db.add(promo)
            db.commit()

            await message.answer(
                f"✅ Промокод создан!\n\n"
                f"Код: `{admin_data[user_id]['code']}`\n"
                f"Бонус: {format_currency(admin_data[user_id]['reward'])}\n"
                f"Активаций: {uses}",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⚙️ Админ-панель")]],
                    resize_keyboard=True
                )
            )

            logger.info(f"🎟️ Промокод создан: {admin_data[user_id]['code']}")

        finally:
            db.close()
            del admin_data[user_id]
            await state.clear()

    except ValueError:
        await message.answer("❌ Введите целое число!")


@router.callback_query(F.data == "list_promos")
async def list_promos(callback: CallbackQuery):
    """Список промокодов"""
    db = SessionLocal()
    try:
        promos = db.query(PromoCode).all()

        if not promos:
            await callback.message.edit_text("📋 Нет активных промокодов")
            return

        text = "📋 Активные промокоды:\n\n"
        for promo in promos:
            text += (
                f"🎟️ `{promo.code}`\n"
                f"💰 Бонус: {format_currency(promo.reward)}\n"
                f"📊 Осталось: {promo.uses_left}\n\n"
            )

        await callback.message.edit_text(text, parse_mode="Markdown")

    finally:
        db.close()


# === PAYMENT REQUESTS ===

async def show_payment_requests(message: Message):
    """Показать заявки на оплату"""
    db = SessionLocal()
    try:
        pending_payments = db.query(Payment).filter(
            Payment.status == "pending"
        ).all()

        if not pending_payments:
            await message.answer("💰 Нет ожидающих заявок на оплату")
            return

        text = "💰 Заявки на оплату:\n\n"

        kb_buttons = []
        for payment in pending_payments:
            user = db.query(User).filter(User.telegram_id == payment.user_id).first()
            text += (
                f"🆔 #{payment.id}\n"
                f"👤 {user.username or user.telegram_id}\n"
                f"💰 {format_currency(payment.amount)}\n"
                f"⏰ {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )

            kb_buttons.append([
                InlineKeyboardButton(
                    text=f"✅ #{payment.id}",
                    callback_data=f"approve_payment_{payment.id}"
                ),
                InlineKeyboardButton(
                    text=f"❌ #{payment.id}",
                    callback_data=f"reject_payment_{payment.id}"
                )
            ])

        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

        await message.answer(text, reply_markup=kb)

    finally:
        db.close()


@router.callback_query(F.data.startswith("approve_payment_"))
async def approve_payment(callback: CallbackQuery):
    """Подтверждение платежа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    payment_id = int(callback.data.split("_")[2])

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()

        if not payment:
            await callback.answer("❌ Платеж не найден", show_alert=True)
            return

        if payment.status != "pending":
            await callback.answer("❌ Платеж уже обработан", show_alert=True)
            return

        # Обновляем статус платежа
        payment.status = "approved"
        payment.updated_at = datetime.utcnow()

        # Пополняем баланс пользователя
        user = db.query(User).filter(User.telegram_id == payment.user_id).first()
        if user:
            user.balance += payment.amount
            user.updated_at = datetime.utcnow()

        db.commit()

        await callback.message.edit_text(
            f"✅ Платеж #{payment_id} подтвержден!\n"
            f"Баланс пользователя пополнен на {format_currency(payment.amount)}"
        )

        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                int(payment.user_id),
                f"✅ Ваше пополнение на сумму {format_currency(payment.amount)} подтверждено!\n\n"
                f"💳 Новый баланс: {format_currency(user.balance if user else payment.amount)}"
            )
        except Exception as e:
            logger.error(f"Error notifying user {payment.user_id}: {e}")

        logger.info(f"✅ Платеж #{payment_id} подтвержден админом {callback.from_user.id}")

    finally:
        db.close()


@router.callback_query(F.data.startswith("reject_payment_"))
async def reject_payment(callback: CallbackQuery):
    """Отклонение платежа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    payment_id = int(callback.data.split("_")[2])

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()

        if not payment:
            await callback.answer("❌ Платеж не найден", show_alert=True)
            return

        if payment.status != "pending":
            await callback.answer("❌ Платеж уже обработан", show_alert=True)
            return

        payment.status = "rejected"
        payment.updated_at = datetime.utcnow()
        db.commit()

        await callback.message.edit_text(
            f"❌ Платеж #{payment_id} отклонен!"
        )

        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                int(payment.user_id),
                f"❌ Ваша заявка на пополнение #{payment_id} на сумму {format_currency(payment.amount)} отклонена.\n\n"
                f"Попробуйте позже или свяжитесь с поддержкой."
            )
        except Exception as e:
            logger.error(f"Error notifying user {payment.user_id}: {e}")

        logger.info(f"❌ Платеж #{payment_id} отклонен админом {callback.from_user.id}")

    finally:
        db.close()


# === ADMIN MANAGEMENT ===

async def show_admin_management(message: Message):
    """Показать меню управления администраторами"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить администратора", callback_data="add_admin_prompt")],
            [InlineKeyboardButton(text="➖ Удалить администратора", callback_data="remove_admin_prompt")],
            [InlineKeyboardButton(text="📋 Список администраторов", callback_data="list_admins")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin")]
        ]
    )

    await message.answer("🔐 Управление администраторами", reply_markup=kb)


@router.callback_query(F.data == "list_admins")
async def list_admins(callback: CallbackQuery):
    """Список администраторов"""
    db = SessionLocal()
    try:
        admins = db.query(Admin).all()

        text = "🔐 Администраторы:\n\n"
        text += f"👑 Владелец: {OWNER_ID}\n\n"

        if admins:
            for admin in admins:
                text += f"👤 ID: {admin.telegram_id} (роль: {admin.role})\n"
        else:
            text += "Нет дополнительных администраторов"

        await callback.message.edit_text(text)

    finally:
        db.close()


@router.callback_query(F.data == "add_admin_prompt")
async def add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос ID для добавления админа"""
    await callback.message.edit_text(
        "➕ Добавление администратора\n\n"
        "Введите Telegram ID пользователя, которого хотите сделать администратором:"
    )
    admin_data[callback.from_user.id] = {"action": "add_admin"}
    await state.set_state(AdminStates.processing_command)


@router.callback_query(F.data == "remove_admin_prompt")
async def remove_admin_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос ID для удаления админа"""
    await callback.message.edit_text(
        "➖ Удаление администратора\n\n"
        "Введите Telegram ID администратора, которого хотите удалить:"
    )
    admin_data[callback.from_user.id] = {"action": "remove_admin"}
    await state.set_state(AdminStates.processing_command)


@router.message(AdminStates.processing_command)
async def process_admin_management(message: Message, state: FSMContext):
    """Обработка ввода ID для добавления/удаления админа"""
    user_id = message.from_user.id

    if user_id not in admin_data:
        await message.answer("❌ Ошибка: данные потеряны")
        await state.clear()
        return

    action = admin_data[user_id].get("action")

    try:
        target_id = int(message.text.strip())

        if target_id == OWNER_ID:
            await message.answer("❌ Нельзя управлять владельцем!")
            return

        db = SessionLocal()
        try:
            if action == "add_admin":
                # Проверяем, не админ ли уже
                existing = db.query(Admin).filter(Admin.telegram_id == str(target_id)).first()
                if existing:
                    await message.answer("❌ Этот пользователь уже администратор!")
                    return

                # Создаем пользователя если его нет
                user = db.query(User).filter(User.telegram_id == str(target_id)).first()
                if not user:
                    user = User(telegram_id=str(target_id))
                    db.add(user)
                    db.commit()

                add_admin(db, target_id, "admin")

                await message.answer(
                    f"✅ Пользователь {target_id} добавлен в администраторы!",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard=[[KeyboardButton(text="⚙️ Админ-панель")]],
                        resize_keyboard=True
                    )
                )

                # Уведомляем нового админа
                try:
                    await message.bot.send_message(
                        target_id,
                        "🎉 Вас назначили администратором!\n\n"
                        "Используйте /admin для входа в админ-панель."
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить нового админа {target_id}: {e}")

                logger.info(f"➕ Админ добавлен: {target_id}")

            elif action == "remove_admin":
                existing = db.query(Admin).filter(Admin.telegram_id == str(target_id)).first()
                if not existing:
                    await message.answer("❌ Этот пользователь не является администратором!")
                    return

                remove_admin(db, target_id)

                await message.answer(
                    f"✅ Пользователь {target_id} удален из администраторов!",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard=[[KeyboardButton(text="⚙️ Админ-панель")]],
                        resize_keyboard=True
                    )
                )

                logger.info(f"➖ Админ удален: {target_id}")

        finally:
            db.close()

    except ValueError:
        await message.answer("❌ Введите корректный Telegram ID (число)!")
    finally:
        if user_id in admin_data:
            del admin_data[user_id]
        await state.clear()


@router.callback_query(F.data == "back_admin")
async def back_admin(callback: CallbackQuery, state: FSMContext):
    """Вернуться в админ-меню"""
    await callback.message.delete()
    await callback.message.answer(
        "⚙️ Админ-панель\n\nВыберите действие:",
        reply_markup=admin_menu_kb()
    )
    await state.set_state(AdminStates.admin_menu)


# === ADMIN COMMANDS ===

@router.message(Command("give_days"))
async def give_days_command(message: Message):
    """Команда: /give_days {user_id} {дни}"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("❌ Использование: /give_days {user_id} {дни}")
            return

        user_id = int(parts[1])
        days = int(parts[2])

        if days <= 0:
            await message.answer("❌ Количество дней должно быть положительным!")
            return

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == str(user_id)).first()

            if not user:
                await message.answer(f"❌ Пользователь {user_id} не найден")
                return

            success, msg = add_days_to_subscription(user, days, user.sub_type or "both", db)

            await message.answer(f"✅ Добавлено {days} дней пользователю {user_id}\n\n{msg}")

            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    user_id,
                    f"✅ Администратор добавил вам {days} дней подписки!\n\n{msg}"
                )
            except Exception:
                pass

        finally:
            db.close()

    except ValueError:
        await message.answer("❌ Неверный формат команды!")


@router.message(Command("take_days"))
async def take_days_command(message: Message):
    """Команда: /take_days {user_id} {дни}"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("❌ Использование: /take_days {user_id} {дни}")
            return

        user_id = int(parts[1])
        days = int(parts[2])

        if days <= 0:
            await message.answer("❌ Количество дней должно быть положительным!")
            return

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == str(user_id)).first()

            if not user:
                await message.answer(f"❌ Пользователь {user_id} не найден")
                return

            if user.sub_expires_at:
                new_expiry = user.sub_expires_at - timedelta(days=days)
                user.sub_expires_at = new_expiry

                if new_expiry <= datetime.utcnow():
                    user.sub_type = "none"
                    user.sub_expires_at = None

                user.updated_at = datetime.utcnow()
                db.commit()

                await message.answer(f"✅ Убрано {days} дней у пользователя {user_id}")
            else:
                await message.answer("❌ У пользователя нет активной подписки")

        finally:
            db.close()

    except ValueError:
        await message.answer("❌ Неверный формат команды!")


@router.message(Command("give_money"))
async def give_money_command(message: Message):
    """Команда: /give_money {user_id} {сумма}"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("❌ Использование: /give_money {user_id} {сумма}")
            return

        user_id = int(parts[1])
        amount = float(parts[2])

        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной!")
            return

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == str(user_id)).first()

            if not user:
                await message.answer(f"❌ Пользователь {user_id} не найден")
                return

            user.balance += amount
            user.updated_at = datetime.utcnow()
            db.commit()

            await message.answer(f"✅ Добавлено {format_currency(amount)} пользователю {user_id}")

            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    user_id,
                    f"💰 Вам начислено {format_currency(amount)}!\n"
                    f"💳 Новый баланс: {format_currency(user.balance)}"
                )
            except Exception:
                pass

        finally:
            db.close()

    except ValueError:
        await message.answer("❌ Неверный формат команды!")


@router.message(Command("take_money"))
async def take_money_command(message: Message):
    """Команда: /take_money {user_id} {сумма}"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("❌ Использование: /take_money {user_id} {сумма}")
            return

        user_id = int(parts[1])
        amount = float(parts[2])

        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной!")
            return

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == str(user_id)).first()

            if not user:
                await message.answer(f"❌ Пользователь {user_id} не найден")
                return

            user.balance = max(0, user.balance - amount)
            user.updated_at = datetime.utcnow()
            db.commit()

            await message.answer(f"✅ Списано {format_currency(amount)} у пользователя {user_id}")

            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    user_id,
                    f"💳 С вашего счета списано {format_currency(amount)}!\n"
                    f"💳 Новый баланс: {format_currency(user.balance)}"
                )
            except Exception:
                pass

        finally:
            db.close()

    except ValueError:
        await message.answer("❌ Неверный формат команды!")


@router.message(Command("add_admin"))
async def add_admin_command(message: Message):
    """Команда: /add_admin {user_id} (только для Owner)"""
    if not is_owner(message.from_user.id):
        await message.answer("❌ Только владелец может добавлять администраторов!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Использование: /add_admin {user_id}")
            return

        user_id = int(parts[1])

        if user_id == OWNER_ID:
            await message.answer("❌ Это владелец!")
            return

        db = SessionLocal()
        try:
            # Проверяем, не админ ли уже
            existing_admin = db.query(Admin).filter(Admin.telegram_id == str(user_id)).first()
            if existing_admin:
                await message.answer("❌ Этот пользователь уже администратор!")
                return

            # Создаем пользователя если его нет
            user = db.query(User).filter(User.telegram_id == str(user_id)).first()
            if not user:
                user = User(telegram_id=str(user_id))
                db.add(user)
                db.commit()

            # Добавляем администратора
            admin = Admin(telegram_id=str(user_id), role="admin")
            db.add(admin)
            db.commit()

            await message.answer(f"✅ Пользователь {user_id} добавлен в администраторы!")

            # Уведомляем нового админа
            try:
                await message.bot.send_message(
                    user_id,
                    "🎉 Вас назначили администратором!\n\n"
                    "Используйте /admin для входа в админ-панель."
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить нового админа: {e}")

        finally:
            db.close()

    except ValueError:
        await message.answer("❌ Неверный формат команды!")


@router.message(Command("remove_admin"))
async def remove_admin_command(message: Message):
    """Команда: /remove_admin {user_id} (только для Owner)"""
    if not is_owner(message.from_user.id):
        await message.answer("❌ Только владелец может удалять администраторов!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Использование: /remove_admin {user_id}")
            return

        user_id = int(parts[1])

        if user_id == OWNER_ID:
            await message.answer("❌ Нельзя удалить владельца!")
            return

        db = SessionLocal()
        try:
            admin = db.query(Admin).filter(Admin.telegram_id == str(user_id)).first()

            if not admin:
                await message.answer("❌ Этот пользователь не является администратором!")
                return

            db.delete(admin)
            db.commit()

            await message.answer(f"✅ Пользователь {user_id} удален из администраторов!")

        finally:
            db.close()

    except ValueError:
        await message.answer("❌ Неверный формат команды!")
