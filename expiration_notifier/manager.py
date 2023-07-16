import asyncio
from datetime import datetime, timedelta, time, date

from db import VPNConnection, User, Server
from .base import AbstractNotifier


class ExpirationManager:
    expiration_limit_timedelta = timedelta(days=5)
    notifier_time = time(hour=13, minute=0, second=0)

    def __init__(self, notifiers: list[AbstractNotifier]):
        self._notifiers = notifiers
        self._last_day_checked: date = date.today() - timedelta(days=1)

    async def run(self):
        while True:
            if self.is_time_to_check():
                await self._check_vpn_connections()
                self._last_day_checked = date.today()
            asyncio.timeout(60 * 2)

    def is_time_to_check(self) -> bool:
        if self._last_day_checked == date.today():
            return False
        return (
            (datetime.now() - timedelta(minutes=5)).time()
            <= self.notifier_time
            <= (datetime.now() + timedelta(minutes=5)).time()
        )

    async def _check_vpn_connections(self):
        for conn in await VPNConnection.all():
            conn: VPNConnection

            if not conn.user_id or not conn.available_to:
                continue

            if not conn.available:
                # Если подключение уже недоступно, но еще принадлежит пользователю
                days_to_delete = (
                    (conn.available_to + self.expiration_limit_timedelta)
                    - datetime.now()
                ).days

                await self._notify_connection_expired(conn, days_to_delete)

            elif conn.available_to <= datetime.now() + self.expiration_limit_timedelta:
                # Если подключение скоро истечет
                days_left = (conn.available_to - datetime.now()).days

                await self._notify_soon_expired(conn, days_left)

    @staticmethod
    async def get_user_and_server(conn: VPNConnection) -> tuple[User, Server]:
        user: User = await User.get(id=conn.user_id)
        server: Server = await Server.get(id=conn.server_id)

        return user, server

    async def _notify_connection_expired(self, conn: VPNConnection, days_to_delete):
        user, server = await self.get_user_and_server(conn)

        for notifier in self._notifiers:
            await notifier.notify_connection_expired(user, server, conn, days_to_delete)

    async def _notify_soon_expired(self, conn: VPNConnection, days_left):
        user, server = await self.get_user_and_server(conn)

        for notifier in self._notifiers:
            await notifier.notify_soon_expired(user, server, conn, days_left)
