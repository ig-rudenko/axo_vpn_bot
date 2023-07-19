"""
Данный код представляет собой менеджер для обработки аренды VPN подключений. Он выполняет следующие задачи:

1. В бесконечном цикле получает все VPN подключения из базы данных без поля конфигурации.

2. Для каждого подключения вызывает метод _process_connection(), который обрабатывает данное подключение.

3. В методе _process_connection() проверяется, активно ли подключение.
   Если нет, то происходит одно из следующих действий:

    - Если время окончания аренды подключения меньше текущего времени на 5 дней, подключение пересоздается и
      удаляется у пользователя.
    - Если время окончания аренды подключения прошло, подключение замораживается.

4. Метод _recreate_connection() пересоздает подключение, если время окончания аренды подключения меньше
   текущего времени на 5 дней. Он выполняет следующие действия:

    - Получает объект сервера по его идентификатору из базы данных.
    - Создает подключение к серверу.
    - Замораживает текущее подключение.
    - Получает объект VPN подключения со всеми полями из базы данных.
    - Пересоздает конфигурацию подключения.
    - Обновляет конфигурацию в базе данных.

5. Метод _freeze_connection() замораживает подключение, если время окончания аренды подключения прошло.
   Он выполняет следующие действия:

    - Получает объект сервера по его идентификатору из базы данных.
    - Создает подключение к серверу.
    - Замораживает текущее подключение.
    - Обновляет статус доступности подключения в базе данных.
"""

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
        all_connections = await VPNConnection.all(
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

            elif connection.available_to < datetime.now():
                # Вышел строк аренды подключения - замораживаем.
                await self._freeze_connection(connection)

        except Exception as exc:
            self.logger.error(
                f"Обработчик аренды VPN подключений |"
                f" Подключение: {connection.local_ip} | Ошибка: {exc}",
                exc_info=exc,
            )

    async def _recreate_connection(self, connection: VPNConnection):
        try:
            server = await Server.get(id=connection.server_id)
        except Server.DoesNotExists:
            return

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
            try:
                config_obj: VPNConnection = await VPNConnection.get(id=connection.id)
            except VPNConnection.DoesNotExists:
                return

            print(config_obj.id, config_obj.client_name, config_obj.config)

            # Пересоздаем конфигурацию.
            new_config = await sc.regenerate_config(
                ConfigBuilder(config=config_obj.config, name=config_obj.client_name)
            )
            # Обновляем конфигурацию в базе.
            await config_obj.update(config=new_config.create_config())

            config_obj: VPNConnection = await VPNConnection.get(id=connection.id)
            print(config_obj.id, config_obj.client_name, config_obj.config)

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
        try:
            server = await Server.get(id=connection.server_id)
        except Server.DoesNotExists:
            return

        sc = ServerConnection(server)
        await sc.connect()

        self.logger.info(
            f"# Сервер: {server.name:<15} | "
            f"Подключение {connection.local_ip} необходимо заморозить"
        )

        await sc.freeze_connection(connection.local_ip)
        # Подключение недоступно.
        await connection.update(available=False)
