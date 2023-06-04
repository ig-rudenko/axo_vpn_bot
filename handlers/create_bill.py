from magic_filter import F
from aiogram import Router
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import update

from qiwi_payment import QIWIPayment
from .callback_factories import ConfirmPaymentCallbackFactory as ConfirmPaymentCF
from db import VPNConnection, async_db_session, ActiveBills, User

router = Router()


async def payment_answer(callback: CallbackQuery, data: dict):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="Оплатить", url=data["payUrl"]))
    keyboard.row(InlineKeyboardButton(text="🔝 Назад", callback_data="start"))

    text = (
        "Ссылка на оплату через платежную систему Qiwi доступна в течение 10 минут!\n\n"
        "Реквизиты банковской карты и регистрационные данные передаются по <b>защищенным протоколам</b> и не "
        "попадут в интернет-магазин и третьим лицам.\nПлатежи обрабатываются на защищенной странице процессинга "
        'по стандарту <a href="https://ru.wikipedia.org/wiki/PCI_DSS">'
        "<b>PCI DSS – Payment Card Industry Data Security Standard.</b></a>"
    )

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()


@router.callback_query(ConfirmPaymentCF.filter(F.type_ == "new"))
async def create_bill_for_new_rent(
    callback: CallbackQuery, callback_data: ConfirmPaymentCF
):
    """
    СОЗДАНИЕ ФОРМЫ ОПЛАТЫ НА QIWI | КУПИТЬ НОВЫЕ ПОДКЛЮЧЕНИЯ
    """

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔝 Назад", callback_data="start"))

    user = await User.get_or_create(tg_id=callback.from_user.id)

    if not callback_data.server_id:
        await callback.message.edit_text(
            "❗️Вы не выбрали VPN сервер для подключения❗️",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()
        return

    # Получаем свободные подключения на данном сервере в необходимом кол-ве.
    free_connection = list(
        await VPNConnection.get_free(
            server_id=callback_data.server_id, limit=callback_data.count
        )
    )

    # Если нет свободных подключений на этом сервере
    if not free_connection:
        await callback.message.edit_text(
            "☹️ Извините, на данном сервере подключения закончились, пожалуйста, выберите другой",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()
        return
    if len(free_connection) < callback_data.count:
        await callback.message.edit_text(
            f"☹️ Извините, на выбранном сервере недостаточно свободных подключений,"
            f' осталось: "{len(free_connection)}"\n',
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()
        return

    # На время оплаты указанное пользователем кол-во устройств необходимо заморозить, чтобы не заняли другие
    async with async_db_session() as session:
        await session.execute(
            update(VPNConnection),
            [
                {"id": conn.id, "user_id": user.id, "available": False}
                for conn in free_connection
            ],
        )
        await session.commit()

    # Пользователь
    user: User = await User.get_or_create(tg_id=callback.from_user.id)

    qiwi_payment = QIWIPayment()
    if data := await qiwi_payment.create_bill(value=callback_data.cost):
        # Добавляем счет об оплате
        await ActiveBills.add(
            bill_id=data["billId"],
            user=user.id,
            available_to=qiwi_payment.available_to,
            type="new",
            rent_month=callback_data.month,
            pay_url=data["payUrl"],
            vpn_connections=free_connection,
        )

        # Формируем ответ по оплате
        await payment_answer(callback, data)

    else:
        # Если не удалось создать форму оплаты, тогда освобождаем забронированные устройства
        async with async_db_session() as session:
            await session.execute(
                update(VPNConnection),
                [
                    {"id": conn.id, "user_id": None, "available": False}
                    for conn in free_connection
                ],
            )
            await session.commit()

        await callback.message.edit_text(
            "Технические неполадки, проносим свои извинения ☹️",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()


@router.callback_query(ConfirmPaymentCF.filter(F.type_ == "extend"))
async def create_bill_for_exist_rent(
    callback: CallbackQuery, callback_data: ConfirmPaymentCF
):
    """
    СОЗДАНИЕ ФОРМЫ ОПЛАТЫ НА QIWI | ПРОДЛИТЬ АРЕНДУ ПОДКЛЮЧЕНИЯ
    """

    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(
            text="🔝 Вернуться в профиль", callback_data=f"show_profile"
        )
    )

    user = await User.get_or_create(tg_id=callback.from_user.id)

    if not callback_data.connection_id:
        await callback.message.edit_text(
            f"❗️Вы не выбрали подключение❗️",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()
        return

    qiwi_payment = QIWIPayment()
    if data := await qiwi_payment.create_bill(value=callback_data.cost):
        # Добавляем счет об оплате
        await ActiveBills.add(
            bill_id=data["billId"],
            user=user.id,
            available_to=qiwi_payment.available_to,
            type="extend",
            rent_month=callback_data.month,
            pay_url=data["payUrl"],
            vpn_connections=[await VPNConnection.get(id=callback_data.connection_id)],
        )

        # Формируем ответ по оплате
        await payment_answer(callback, data)

    else:
        # Если не удалось создать форму оплаты, тогда освобождаем забронированные устройства
        # await unpause_devs(user_devs_ids)
        await callback.message.edit_text(
            "Технические неполадки, проносим свои извинения ☹️",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()
