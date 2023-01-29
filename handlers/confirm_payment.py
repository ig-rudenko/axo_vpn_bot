import os
import uuid

import aiohttp
from datetime import datetime, timedelta

from magic_filter import F
from aiogram import Router
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, update

from qiwi_payment import QIWIPayment
from .callback_factories import ConfirmPaymentCallbackFactory as ConfirmPaymentCF
from db import Server, VPNConnection, async_db_session, ActiveBills, User

router = Router()


@router.callback_query(ConfirmPaymentCF.filter(F.type_ == "new"))
async def create_bill_for_new_rent(
    callback: CallbackQuery, callback_data: ConfirmPaymentCF
):

    # Получаем свободные подключения на данном сервере в необходимом кол-ве.
    free_connection = list(
        await VPNConnection.get_free(
            server_id=callback_data.server_id, limit=callback_data.count
        )
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔝 Назад", callback_data="start"))

    if not free_connection:
        await callback.message.edit_text(
            "Устройства закончились", reply_markup=keyboard.as_markup()
        )
        await callback.answer()
        return
    if len(free_connection) < callback_data.count:
        await callback.message.edit_text(
            f"Укажите меньшее кол-во устройств\nДоступно {len(free_connection)}",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()
        return

    # На время оплаты указанное пользователем кол-во устройств необходимо заморозить, чтобы не заняли другие
    async with async_db_session() as session:
        await session.execute(
            update(VPNConnection),
            [{"id": conn.id, "free": 2} for conn in free_connection],
        )
        await session.commit()

    # Пользователь
    if user := await User.get(tg_id=callback.from_user.id):
        user_id = user.id
    else:
        # Если нет, то создаем
        user_id = await User.create(tg_id=callback.from_user.id)

    qiwi_payment = QIWIPayment()
    if data := await qiwi_payment.create_bill(value=callback_data.cost):

        # Добавляем счет об оплате
        await ActiveBills.add(
            bill_id=data["billId"],
            user=user_id,
            available_to=qiwi_payment.available_to,
            type="new",
            rent_month=callback_data.month,
            pay_url=data["payUrl"],
            vpn_connections=free_connection,
        )

        await callback.message.edit_text(
            f"Ссылка на оплату через платежную систему Qiwi: "
            f'<a href="{data["payUrl"]}">Оплатить</a>\nДоступна в течение 10 минут!\n\n'
            f"Реквизиты банковской карты и регистрационные данные передаются по <b>защищенным протоколам</b> и не "
            f"попадут в интернет-магазин и третьим лицам.\nПлатежи обрабатываются на защищенной странице процессинга "
            f'по стандарту <a href="https://ru.wikipedia.org/wiki/PCI_DSS">'
            f"<b>PCI DSS – Payment Card Industry Data Security Standard.</b></a>",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()

    else:
        # Если не удалось создать форму оплаты, тогда освобождаем забронированные устройства
        # await unpause_devs(user_devs_ids)
        await callback.message.edit_text(
            "Технические неполадки, проносим свои извинения :(",
            reply_markup=keyboard.as_markup(),
        )
