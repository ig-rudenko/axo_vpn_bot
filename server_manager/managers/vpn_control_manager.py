import asyncio
from datetime import datetime, timedelta

from asyncssh import ProcessError

from db import VPNConnection, Server
from .base import BaseManager
from .. import ServerConnection, ConfigBuilder


class VPNControlManager(BaseManager):
    timeout = 60 * 10

    async def run(self):
        print("=== Запущен обработчик аренды VPN подключений ===")
        while True:
            await self.task()
            await asyncio.sleep(self.timeout)

    async def task(self):
        # Вытягиваем из базы все VPN подключения, но без поля конфигурации.
        all_connections: list[VPNConnection] = await VPNConnection.all(
            values=[
                "server_id",
                "user_id",
                "available",
                "local_ip",
                "available_to",
                "client_name",
            ]
        )

        for connection in all_connections:
            await self._process_connection(connection)

    async def _process_connection(self, connection: VPNConnection):
        try:
            if not connection.available_to or connection.available_to > datetime.now():
                # Подключение не назначено или еще активно.
                return

            # Если поле available_to меньше текущего времени на 5 дней
            if connection.available_to < datetime.now() - timedelta(days=5):
                # Необходимо пересоздать подключение и удалить его у пользователя
                await self._recreate_connection(connection)

            else:
                # Вышел строк аренды подключения - замораживаем.
                await self._freeze_connection(connection)

        except Exception as exc:
            self.logger.error(
                f"Обработчик аренды VPN подключений |"
                f" Подключение: {connection.local_ip} | Ошибка: {exc}",
                exc_info=exc,
            )

    async def _recreate_connection(self, connection: VPNConnection):
        server = await Server.get(id=connection.server_id)
        sc = ServerConnection(server)
        await sc.connect()

        self.logger.info(
            f"# Сервер: {server.name:<15} | "
            f"Подключение {connection.local_ip} необходимо пересоздать"
        )

        try:
            # Замораживаем подключение, на всякий случай.
            await sc.freeze_connection(connection.local_ip)
            # Вытягиваем из базы объект VPN подключения со всеми полями.
            config_obj = await VPNConnection.get(id=connection.id)

            # Пересоздаем конфигурацию.
            new_config = await sc.regenerate_config(
                ConfigBuilder(config=config_obj.config, name=config_obj.client_name)
            )
            # Обновляем конфигурацию в базе.
            await config_obj.update(config=new_config.create_config())

        except (ConnectionError, ProcessError) as exc:
            exc: ProcessError
            # В случае ошибки на стороне сервера, будет попытка на следующей итерации.
            self.logger.error(
                f"# Сервер: {server.name:<15} | "
                f"Подключение: {connection.local_ip} | Ошибка: {exc.stderr}",
                exc_info=exc,
            )

        else:
            # Освобождаем подключение от пользователя.
            await connection.update(user_id=None, available_to=None, available=False)

    async def _freeze_connection(self, connection: VPNConnection):
        server = await Server.get(id=connection.server_id)
        sc = ServerConnection(server)
        await sc.connect()

        self.logger.info(
            f"# Сервер: {server.name:<15} | "
            f"Подключение {connection.local_ip} необходимо заморозить"
        )

        await sc.freeze_connection(connection.local_ip)
        # Подключение недоступно.
        await connection.update(available=False)
