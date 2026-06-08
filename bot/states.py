"""
FSM (Finite State Machine) состояния для Telegram-бота
"""
from aiogram.fsm.state import State, StatesGroup


class ClientStates(StatesGroup):
    """Состояния для клиентского взаимодействия"""
    main_menu = State()

    # Покупка подписки
    select_sub_type = State()  # Выбор типа подписки (normal/antiblock)
    select_duration = State()  # Выбор длительности
    entering_custom_days = State()  # Ввод кол-ва дней вручную
    confirming_payment = State()  # Подтверждение покупки

    # Пополнение баланса
    entering_top_up_amount = State()  # Ввод суммы пополнения
    # confirming_payment уже есть выше

    # Промокоды
    entering_promo_code = State()  # Ввод промокода


class AdminStates(StatesGroup):
    """Состояния для администратора"""
    admin_menu = State()

    # Управление серверами
    entering_normal_config = State()  # Ввод обычных серверов
    entering_antiblock_config = State()  # Ввод серверов обхода

    # Управление профилем
    entering_profile_title = State()  # Ввод заголовка профиля
    entering_profile_announce = State()  # Ввод объявления

    # Управление скидками
    entering_discount = State()  # Ввод глобальной скидки

    # Промокоды
    entering_promo_code_text = State()  # Ввод текста промокода
    entering_promo_reward = State()  # Ввод награды промокода
    entering_promo_uses = State()  # Ввод кол-ва активаций промокода

    # Команды
    processing_command = State()  # Обработка текстовых команд (add/remove admin)
