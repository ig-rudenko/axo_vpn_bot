from db import VPNConnection, User, Server
from .base import AbstractNotifier
from helpers.verbose_numbers import days_verbose


class TgBotNotifier(AbstractNotifier):
    def __init__(self, bot):
        self.bot = bot

    async def notify_connection_expired(
        self, user: User, server: Server, connection: VPNConnection, days_left: int
    ):
        if days_left == 0:
            days_left_string = "Удалится завтра"
        else:
            days_left_string = f"Удалится через {days_left} {days_verbose(days_left)}"

        await self.bot.send_message(
            chat_id=user.tg_id,
            text=f"Срок аренды вышел!\n"
            f"Подключение {connection.local_ip}\n{server.name}{server.verbose_location}\n"
            f"{days_left_string}",
        )

    async def notify_soon_expired(
        self, user: User, server: Server, connection: VPNConnection, days_left: int
    ):
        if days_left == 0:
            days_left_string = "Завтра"
        else:
            days_left_string = f"Через {days_left} {days_verbose(days_left)}"

        await self.bot.send_message(
            chat_id=user.tg_id,
            text=f"{days_left_string} закончится аренда подключения!"
            f" {connection.local_ip}\n{server.name}{server.verbose_location}",
        )
