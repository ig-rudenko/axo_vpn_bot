import asyncio
from datetime import datetime, timedelta, time, date
from typing import Literal

from db import VPNConnection, User, Server
from db.models import ModelAdmin
from .base import AbstractNotifier


class ExpirationManager:
    expiration_limit_timedelta = timedelta(days=5)
    notifier_time = time(hour=21, minute=1, second=0)

    def __init__(self, notifiers: list[AbstractNotifier]):
        self._notifiers = notifiers
        self._last_day_checked: date = date.today() - timedelta(days=1)

    async def run(self):
        while True:
            if self.is_time_to_check():
                await self._check_vpn_connections()
                self._last_day_checked = date.today()
            await asyncio.sleep(60 * 2)

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

                await self._notify("connection_expired", conn, days_to_delete)

            elif conn.available_to <= datetime.now() + self.expiration_limit_timedelta:
                # Если подключение скоро истечет
                days_left = (conn.available_to - datetime.now()).days

                await self._notify("soon_expired", conn, days_left)

    @staticmethod
    async def get_user_and_server(conn: VPNConnection) -> tuple[User, Server]:
        user: User = await User.get(id=conn.user_id)
        server: Server = await Server.get(id=conn.server_id)

        return user, server

    async def _notify(
        self,
        mode: Literal["connection_expired", "soon_expired"],
        conn: VPNConnection,
        days_to_delete,
    ):
        try:
            user, server = await self.get_user_and_server(conn)
        except ModelAdmin.DoesNotExists:
            return

        else:
            for notifier in self._notifiers:
                await getattr(notifier, f"notify_{mode}")(
                    user, server, conn, days_to_delete
                )
