import hashlib
import io

import flag

from aiogram import Router
from aiogram.types import InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .callback_factories import ExtendRentCallbackFactory as ExtendRentCF
from db import VPNConnection, ActiveBills, User, Server
from .buy_service import month_verbose
from .callback_factories import GetConfigCallbackFactory as GetConfigCF

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
        keyboard.add(
            InlineKeyboardButton(text="Купить", callback_data="choose_location")
        )
        keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="start"))
        await callback.message.edit_text(
            text + "🟠 У вас нет доступных подключений",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()
        return

    # Имеются подключения
    text += f"У вас имеется: {len(vpn_connections)} подключений\n\n"

    # Смотрим по очереди подключения
    for i, connection in enumerate(vpn_connections, 1):
        connection: VPNConnection
        connection_buttons = []

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
            connection_buttons.append(
                InlineKeyboardButton(
                    text=f"Подключение {i} - ⚙️ Конфиг",
                    callback_data=GetConfigCF(connection_id=connection.id).pack(),
                )
            )

        # Имеется ли информация о продлении данного подключения
        for bill in active_bills:
            conn_ids = [conn.id for conn in bill.vpn_connections]
            if bill.type == "extend" and connection.id in conn_ids:
                text += (
                    f"Вы уже запросили продление услуги на {bill.rent_month} {month_verbose(bill.rent_month)}\n"
                    f' <a href="{bill.pay_url}">Форма оплаты</a>'
                    f' доступна до {bill.available_to.strftime("%H:%M:%S")}\n'
                )
                break
        else:
            # Если нет зарегистрированных форм оплаты для данного подключения,
            # то добавляем кнопку продления
            connection_buttons.append(
                InlineKeyboardButton(
                    text=f"Подключение {i} - продлить",
                    callback_data=extend_rent_callback.pack(),
                )
            )

        text += "\n"

        if connection_buttons:
            # Формируем кнопки для данного подключения
            keyboard.row(*connection_buttons)

    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="start"))
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()


@router.callback_query(GetConfigCF.filter())
async def get_user_config(callback: CallbackQuery, callback_data: GetConfigCF):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🔝 На главную", callback_data="start"))

    user = await User.get(tg_id=callback.from_user.id)
    if user is None:
        # Не существует пользователя
        await callback.message.edit_text(
            "❗️У вас нет доступных конфигурации❗️", reply_markup=keyboard.as_markup()
        )
        await callback.answer()
        return

    # Смотрим запрашиваемое подключение
    connection = await VPNConnection.get(
        id=callback_data.connection_id, user_id=user.id
    )
    if connection is None or not connection.available or not connection.available_to:
        # Не существует такого подключения у данного пользователя или оно недоступно
        await callback.message.edit_text(
            "❗Неверная конфигурация❗️", reply_markup=keyboard.as_markup()
        )
        await callback.answer()
        return

    # Конфигурация пользователя найдена
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="show_profile"))

    # Формируем текст конфигурации и её имя как хэш.
    config = connection.config.encode()
    file_name = hashlib.md5(config).hexdigest()

    # Удаляем предыдущее сообщение от бота.
    await callback.message.delete()

    # Отправляем конфигурационный файл пользователю.
    await callback.message.answer_document(
        BufferedInputFile(bytes(config), filename=file_name),
        caption=f"Не изменяйте содержимое файла, во избежание нестабильной работы",
    )
    await callback.message.answer(
        text=f"Вернуться в профиль", reply_markup=keyboard.as_markup()
    )
    await callback.answer()
