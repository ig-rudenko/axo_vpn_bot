from aiogram import Router
from aiogram.types import InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from helpers.bot_answers_shortcuts import send_technical_error
from .callback_factories import ExtendRentCallbackFactory as ExtendRentCF
from db import VPNConnection, ActiveBills, User, Server
from .buy_service import month_verbose
from .callback_factories import GetConfigCallbackFactory as GetConfigCF

router = Router()


class UserProfile:
    """
    Для управления пользовательским профилем и просмотром состояния его подключений.
    """

    def __init__(self, user: User):
        self._user = user

        # Доступные пользователю VPN подключения
        self._vpn_connections: list[VPNConnection] = []

        # Текущие неоплаченные счета
        self._active_bills: list[ActiveBills] = []

        self._keyboard = InlineKeyboardBuilder()
        self._text_lines = []

    async def collect_vpn_connections(self):
        self._vpn_connections = await self._user.get_connections()

    async def collect_active_bills(self):
        self._active_bills = await self._user.get_active_bills()

    def get_keyboard(self) -> InlineKeyboardBuilder:
        """
        Возвращает набор кнопок для отправки.
        :return:
        """
        return self._keyboard

    def get_text(self) -> str:
        """
        Возвращает текст профиля для отправки.
        """
        return "\n".join(self._text_lines)

    async def create_profile(self) -> None:
        """
        Создаем информацию о профиле пользователя.
        """
        if self._user_has_no_data():
            self._create_empty_user_profile()

        else:
            await self._create_new_active_bills_info_text()
            await self._create_text_and_add_buttons_for_users_connections()
            self._add_button_to_start()

    def _user_has_no_data(self) -> bool:
        return not len(self._vpn_connections) and not len(self._active_bills)

    def _create_empty_user_profile(self) -> None:
        self._keyboard.row(
            InlineKeyboardButton(text="Купить", callback_data="choose_location")
        )
        self._add_button_to_start()
        self._text_lines = ["🟠 У вас нет доступных подключений"]

    def _add_button_to_start(self):
        self._keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="start"))

    async def _create_new_active_bills_info_text(self) -> None:
        """
        Создает описание для новых счетов ожидающих подключение.
        """
        for bill in self._active_bills:
            if bill.type == "new":
                try:
                    server = await Server.get(id=bill.vpn_connections[0].server_id)
                except Server.DoesNotExists:
                    continue

                self._text_lines.append(
                    f"⏳ Ожидается оплата:\n"
                    f"На длительность {bill.rent_month} {month_verbose(bill.rent_month)} "
                    f"{server.verbose_location}\n"
                    f"Количество устройств: {len(bill.vpn_connections)}\n"
                    f'<a href="{bill.pay_url}">Форма оплаты</a>'
                    f' доступна до {bill.available_to.strftime("%H:%M:%S")}\n'
                )

    async def _create_text_and_add_buttons_for_users_connections(self) -> None:
        """
        Создает информацию обо всех подключениях имеющихся у пользователя.
        """
        self._text_lines.append(
            f"\nУ вас имеется: {len(self._vpn_connections)} подключений\n"
        )

        # Смотрим по очереди подключения
        for i, connection in enumerate(self._vpn_connections, 1):
            buttons_row: list[InlineKeyboardButton] = []

            await self._create_info_for_connection(
                connection, conn_number=i, buttons_row=buttons_row
            )

            self._create_text_for_extended_connection(
                connection, conn_number=i, buttons_row=buttons_row
            )

            if buttons_row:
                # Формируем кнопки для данного подключения
                self._keyboard.row(*buttons_row)

    async def _create_info_for_connection(
        self,
        connection: VPNConnection,
        conn_number: int,
        buttons_row: list[InlineKeyboardButton],
    ) -> None:
        """
        Добавляет информацию об одном подключении.
        :param connection: Объект подключения.
        :param conn_number: Номер в списке по порядку.
        :param buttons_row: Список для вставки кнопки.
        """

        # Определяем местоположение подключения
        try:
            server = await Server.get(id=connection.server_id)
        except Server.DoesNotExists:
            return

        # Информация подключения (состояние)
        self._text_lines.append(
            f"# {conn_number}: {'🟢' if connection.available else '🔴'}  {server.verbose_location}\n"
            f"{connection.local_ip}"
        )
        if connection.available:
            self._text_lines.append(
                f"Доступно до {connection.available_to.strftime('%Y.%m.%d %H:%M')}"
            )
            buttons_row.append(
                InlineKeyboardButton(
                    text=f"# {conn_number} - ⚙️ Конфиг",
                    callback_data=GetConfigCF(connection_id=connection.id).pack(),
                )
            )
        self._text_lines.append("\n")

    def _create_text_for_extended_connection(
        self,
        connection: VPNConnection,
        conn_number: int,
        buttons_row: list[InlineKeyboardButton],
    ) -> None:
        # Имеется ли информация о продлении данного подключения
        for bill in self._active_bills:
            conn_ids = [conn.id for conn in bill.vpn_connections]
            if bill.type == "extend" and connection.id in conn_ids:
                self._text_lines.append(
                    f"Вы уже запросили продление услуги на {bill.rent_month} {month_verbose(bill.rent_month)}\n"
                    f' <a href="{bill.pay_url}">Форма оплаты</a>'
                    f' доступна до {bill.available_to.strftime("%H:%M:%S")}'
                )
                break
        else:
            self._create_button_for_extend(
                connection, conn_number=conn_number, buttons_row=buttons_row
            )

    def _create_button_for_extend(
        self,
        connection: VPNConnection,
        conn_number: int,
        buttons_row: list[InlineKeyboardButton],
    ) -> None:
        if not len(self._active_bills):
            # Формируем callback data для продления услуги VPN
            extend_rent_callback = ExtendRentCF(
                connection_id=connection.id,
                server_id=connection.server_id,
            )

            # Если нет зарегистрированных форм оплаты для данного подключения,
            # то добавляем кнопку продления
            buttons_row.append(
                InlineKeyboardButton(
                    text=f"# {conn_number} - продлить",
                    callback_data=extend_rent_callback.pack(),
                )
            )


@router.callback_query(text="show_profile")
async def show_profile(callback: CallbackQuery):
    user = await User.get_or_create(tg_id=callback.from_user.id)

    user_profile = UserProfile(user)
    await user_profile.collect_vpn_connections()
    await user_profile.collect_active_bills()
    await user_profile.create_profile()

    await callback.message.edit_text(
        text=user_profile.get_text(),
        reply_markup=user_profile.get_keyboard().as_markup(),
    )
    await callback.answer()


@router.callback_query(GetConfigCF.filter())
async def get_user_config(callback: CallbackQuery, callback_data: GetConfigCF):
    try:
        user = await User.get(tg_id=callback.from_user.id)
    except User.DoesNotExists:
        # Не существует пользователя
        await send_technical_error(callback, "❗️У вас нет доступных конфигурации❗️")
        return

    try:
        # Смотрим запрашиваемое подключение
        connection: VPNConnection = await VPNConnection.get(
            id=callback_data.connection_id, user_id=user.id
        )
        if not connection.available or not connection.available_to:
            await send_technical_error(
                callback, "❗️Данное подключение вам недоступно❗️"
            )
            return
    except VPNConnection.DoesNotExists:
        await send_technical_error(callback, "❗Неверная конфигурация❗️")
        return

    try:
        server = await Server.get(id=connection.server_id)
    except Server.DoesNotExists:
        await send_technical_error(callback, "❗Сервер больше не существует❗️")
        return

    # Конфигурация пользователя найдена.
    # Формируем текст конфигурации и её имя как название сервера.
    config = connection.config.encode()
    file_name = server.name + ".conf"

    # Удаляем предыдущее сообщение от бота.
    # await callback.message.delete()

    # Отправляем конфигурационный файл пользователю.
    await callback.message.answer_document(
        BufferedInputFile(bytes(config), filename=file_name),
        caption=f"Не изменяйте содержимое файла, во избежание нестабильной работы",
    )
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="show_profile"))
    await callback.message.answer(
        text=f"Вернуться в профиль", reply_markup=keyboard.as_markup()
    )
    await callback.answer()
