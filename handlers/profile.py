import flag
from magic_filter import F
from aiogram import Router
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import update, select
from sqlalchemy.orm import selectinload

from qiwi_payment import QIWIPayment
from .callback_factories import ExtendRentCallbackFactory as ExtendRentCF
from db import VPNConnection, async_db_session, ActiveBills, User, Server
from .buy_service import month_verbose

router = Router()


@router.callback_query(text="show_profile")
async def show_profile(callback: CallbackQuery):

    # Пользователь
    user: User = await User.get_or_create(tg_id=callback.from_user.id)

    # Доступные пользователю VPN подключения
    vpn_connections = await user.get_connections()

    # Текущие неоплаченные счета
    active_bills = await user.get_active_bills()

    text = ""
    for bill in active_bills:
        if bill.type == "new":
            bill: ActiveBills
            text += (
                f"⏳ Ожидается оплата:\n"
                f"Новое подключение "
                f'<a href="{bill.pay_url}">Форма оплаты</a>'
                f' доступна до {bill.available_to.strftime("%H:%M:%S")}\n\n'
            )

    keyboard = InlineKeyboardBuilder()

    # Если нет подключений у пользователя
    if not len(vpn_connections):
        keyboard.add(InlineKeyboardButton(text="Купить", callback_data="show_prices:1"))
        keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="start"))
        await callback.message.edit_text(
            text + "🟠 У вас нет доступных подключений",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()
        return

    # Имеются подключения
    text += f"У вас имеется {len(vpn_connections)}\n\n"

    # Смотрим по очереди подключения
    for i, connection in enumerate(vpn_connections, 1):
        connection: VPNConnection

        # Определяем местоположение подключения
        if server := await Server.get(id=connection.server_id):
            connection_location = f"{flag.flag(server.country_code)} {server.location}"
        else:
            connection_location = "Локация не определена!"

        # Формируем callback data для продления услуги VPN
        extend_rent_callback = ExtendRentCF(
            connection_id=connection.id, server_id=connection.server_id
        )

        # Информация подключения (состояние)
        text += f"Подключение {i}: {'🟢' if connection.available else '🔴'}  {connection_location}\n"
        if connection.available:
            text += (
                f"Доступно до {connection.available_to.strftime('%Y.%m.%d %H:%M')}\n"
            )

        # Имеется ли информация о продлении данного подключения
        for bill in active_bills:
            conn_ids = [conn.id for conn in bill.vpn_connections]
            if bill.type == "extend" and connection.id in conn_ids:
                text += (
                    f"\nПродление услуги на {bill.rent_month} {month_verbose(bill.rent_month)}"
                    f' <a href="{bill.pay_url}">Форма оплаты</a>'
                    f' доступна до {bill.available_to.strftime("%H:%M:%S")}\n\n'
                )

        keyboard.row(
            InlineKeyboardButton(text=f"Подключение {i}", callback_data="show_profile"),
            InlineKeyboardButton(
                text="Продлить",
                callback_data=extend_rent_callback.pack(),
            ),
            InlineKeyboardButton(
                text="Конфиг",
                callback_data=f"get_config:{callback.from_user.id}:dev[0]:{i}",
            ),
        )

    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="start"))
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()
