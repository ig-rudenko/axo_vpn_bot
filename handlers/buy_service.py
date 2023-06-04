import flag
from aiogram import Router
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import Server
from .callback_factories import (
    DeviceCountCallbackFactory as DevCountCF,
    BuyCallbackFactory as BuyCF,
    ConfirmPaymentCallbackFactory as ConfirmPaymentCF,
    ExtendRentCallbackFactory as ExtendRentCF,
)


router = Router()


@router.callback_query(text="choose_location")
async def choose_location(callback: CallbackQuery):
    keyboard = InlineKeyboardBuilder()
    # Смотрим список VPN серверов
    for server in await Server.all(values=["country_code", "location"]):
        # Добавляем флаг страны и местоположение VPN сервера
        text = flag.flagize(
            f":{server.country_code}: {server.location}\n", subregions=True
        )
        keyboard.add(
            InlineKeyboardButton(
                text=text, callback_data=DevCountCF(count=1, server_id=server.id).pack()
            )
        )
    await callback.message.edit_text(
        text="Выберите VPN сервер", reply_markup=keyboard.as_markup()
    )
    await callback.answer()


def add_period_keyboard(keyboard: InlineKeyboardBuilder, callback_data):
    print(callback_data)
    if isinstance(callback_data, DevCountCF):
        base_cost = 50 + 100 * callback_data.count
        end_data = {"count": callback_data.count}
        type_ = "new"
    else:
        base_cost = 150
        type_ = "extend"
        end_data = {"connection_id": callback_data.connection_id}

    # Кнопки выбора периода оплаты
    # 1, 2 МЕСЯЦА
    keyboard.row(
        InlineKeyboardButton(
            text=f"1️⃣ месяц - {base_cost} ₽",
            callback_data=BuyCF(
                type_=type_,
                month=1,
                cost=base_cost,
                server_id=callback_data.server_id,
                **end_data,
            ).pack(),
        ),
        InlineKeyboardButton(
            text=f"2️⃣ месяца - {round(base_cost * 2)} ₽",
            callback_data=BuyCF(
                type_=type_,
                month=2,
                cost=round(base_cost * 2),
                server_id=callback_data.server_id,
                **end_data,
            ).pack(),
        ),
    )

    # 3, 4 МЕСЯЦА
    keyboard.row(
        InlineKeyboardButton(
            text=f"3️⃣ месяца - {round(base_cost * 3)} ₽",
            callback_data=BuyCF(
                type_=type_,
                month=3,
                cost=round(base_cost * 3),
                server_id=callback_data.server_id,
                **end_data,
            ).pack(),
        ),
        InlineKeyboardButton(
            text=f"4️⃣ месяца - {round(base_cost * 4)} ₽",
            callback_data=BuyCF(
                type_=type_,
                month=4,
                cost=round(base_cost * 4),
                server_id=callback_data.server_id,
                **end_data,
            ).pack(),
        ),
    )

    # 5, 6 МЕСЯЦЕВ
    keyboard.row(
        InlineKeyboardButton(
            text=f"5️⃣ месяцев - {round(base_cost * 5)} ₽",
            callback_data=BuyCF(
                type_=type_,
                month=5,
                cost=round(base_cost * 5),
                server_id=callback_data.server_id,
                **end_data,
            ).pack(),
        )
    )

    keyboard.row(
        InlineKeyboardButton(
            text=f"6️⃣ месяцев 🔸 -20% 🔸 - {round(base_cost * 6 * 0.8)} ₽",
            callback_data=BuyCF(
                type_=type_,
                month=6,
                cost=round(base_cost * 6 * 0.8),
                server_id=callback_data.server_id,
                **end_data,
            ).pack(),
        )
    )

    # 1 ГОД
    keyboard.row(
        InlineKeyboardButton(
            text=f"1️⃣ год 🔹 -30% 🔹 - {round(base_cost * 12 * 0.7)} ₽",
            callback_data=BuyCF(
                type_=type_,
                month=12,
                cost=round(base_cost * 12 * 0.7),
                server_id=callback_data.server_id,
                **end_data,
            ).pack(),
        )
    )


@router.callback_query(DevCountCF.filter())
async def show_prices(callback: CallbackQuery, callback_data: DevCountCF):
    """
    Выбор кол-ва подключений и периода
    """

    keyboard = InlineKeyboardBuilder()
    if callback_data.count > 1:
        keyboard.row(
            InlineKeyboardButton(
                text="➖ Убрать одно устройство",
                callback_data=DevCountCF(
                    count=callback_data.count - 1, server_id=callback_data.server_id
                ).pack(),
            )
        )
    if callback_data.count < 4:
        keyboard.row(
            InlineKeyboardButton(
                text="➕ Добавить еще одно устройство",
                callback_data=DevCountCF(
                    count=callback_data.count + 1, server_id=callback_data.server_id
                ).pack(),
            )
        )

    add_period_keyboard(keyboard, callback_data)

    keyboard.row(InlineKeyboardButton(text="🔝 На главную", callback_data="start"))

    await callback.message.edit_text(
        text=f"Подключений: <b>{callback_data.count}</b>\n" f"Выберите период аренды",
        reply_markup=keyboard.as_markup(),
    )
    await callback.answer()


# ПРОДЛИТЬ АРЕНДУ
@router.callback_query(ExtendRentCF.filter())
async def extend_rent(callback: CallbackQuery, callback_data: ExtendRentCF):
    keyboard = InlineKeyboardBuilder()

    add_period_keyboard(keyboard, callback_data)

    keyboard.add(InlineKeyboardButton(text="✖️Отмена", callback_data=f"show_profile"))
    await callback.message.edit_text(
        text="Выберите период аренды", reply_markup=keyboard.as_markup()
    )
    await callback.answer()


def month_verbose(month: int) -> str:
    if month == 1:
        return "месяц"
    elif month <= 4:
        return "месяца"
    return "месяцев"


# СОГЛАСИЕ НА ПОКУПКУ
@router.callback_query(BuyCF.filter())
async def confirm_payment(callback: CallbackQuery, callback_data: BuyCF):
    """
    Подтверждение покупки
    """

    keyboard = InlineKeyboardBuilder().row(
        InlineKeyboardButton(
            text="Пользовательское соглашение", callback_data="user_agreement"
        )
    )

    if callback_data.type_ == "extend":
        # Если это продление аренды
        confirm_callback = ConfirmPaymentCF(
            type_="extend",
            cost=callback_data.cost,
            count=1,
            month=callback_data.month,
            connection_id=callback_data.connection_id,
            server_id=callback_data.server_id,
        )

        text = (
            f"Продление аренды ⏩\n"
            f"Нажимая кнопку оплатить, Вы соглашаетесь с пользовательским соглашением \n"
        )
        keyboard.row(
            InlineKeyboardButton(
                text=f"Оплатить {callback_data.cost} ₽",
                callback_data=confirm_callback.pack(),
            ),
            InlineKeyboardButton(text="✖️Отмена", callback_data="show_profile"),
        )

    elif callback_data.type_ == "new":
        # Новое подключение
        confirm_callback = ConfirmPaymentCF(
            type_="new",
            cost=callback_data.cost,
            count=callback_data.count,
            month=callback_data.month,
            server_id=callback_data.server_id,
        )
        # Новая покупка
        text = (
            f"Ваше количество устройств: {callback_data.count} 📲\n"
            f"Длительность аренды: {callback_data.month} {month_verbose(callback_data.month)}\n"
            f"Нажимая кнопку оплатить, Вы соглашаетесь с пользовательским соглашением \n"
        )
        keyboard.row(
            InlineKeyboardButton(
                text=f"Оплатить {callback_data.cost} ₽",
                callback_data=confirm_callback.pack(),
            ),
            InlineKeyboardButton(text="✖️Отмена", callback_data="start"),
        )

    else:
        text = "❗Неверные данные❗"
        keyboard = InlineKeyboardBuilder().add(
            InlineKeyboardButton(text="✖️Отмена", callback_data="start")
        )

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()
