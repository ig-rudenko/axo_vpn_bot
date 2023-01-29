import os
import uuid

import aiohttp
from datetime import datetime, timedelta

from magic_filter import F
from aiogram import Router
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, update

from .callback_factories import ConfirmPaymentCallbackFactory as ConfirmPaymentCF
from db import Server, VPNConnection, async_db_session, ActiveBills, User

router = Router()


@router.callback_query(ConfirmPaymentCF.filter(F.type_ == "new"))
async def create_bill_for_new_rent(
    callback: CallbackQuery, callback_data: ConfirmPaymentCF
):

    # Проверяем, сколько свободно подключений на данном сервере
    free_connection = list(
        await VPNConnection.get_free(callback_data.server_id, callback_data.count)
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
    if user := await User.get_by_tg(tg_id=callback.from_user.id):
        user_id = user.id
    else:
        # Если нет, то создаем
        user_id = await User.create(tg_id=callback.from_user.id)

    available_time = datetime.now() + timedelta(minutes=10)

    # Время жизни формы оплаты 10 мин
    async with aiohttp.ClientSession() as session:
        response = await session.put(
            url=f"https://api.qiwi.com/partner/bill/v1/bills/{uuid.uuid4()}",
            headers={
                "accept": "application/json",
                "Authorization": "Bearer " + os.getenv("QIWI_TOKEN"),
            },
            json={
                "amount": {"currency": "RUB", "value": callback_data.cost},
                "comment": "Axo VPN",
                "expirationDateTime": f"{available_time.strftime('%Y-%m-%dT%H:%M:%S+03:00')}",
            },
        )
    if response.status == 200:
        data = await response.json()

        # Добавляем счет об оплате
        async with async_db_session() as session:
            new_bill = ActiveBills(
                bill_id=data["billId"],
                user=user_id,
                available_to=available_time,
                type="new",
                rent_month=callback_data.month,
                pay_url=data["payUrl"],
                vpn_connections=free_connection,
            )
            session.add(new_bill)
            await session.commit()

        # res = await ActiveBills.create(
        #     bill_id=bill_id,
        #     user=user_id
        # )
        # print(
        #     bill_id,
        #     str(available_time.timestamp()),
        #     user_id,
        #     # user_devs_ids,
        #     "new",
        #     str(rent_to.timestamp()),
        #     data["payUrl"],
        # )

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
