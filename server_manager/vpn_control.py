import asyncio
from datetime import datetime, timedelta

from asyncssh.process import ProcessError

from qiwi_payment import QIWIPayment
from db import VPNConnection, Server
from .base import ServerConnection, ConfigManager


async def vpn_connections_manager():
    while True:
        all_connections: list[VPNConnection] = await VPNConnection.all(
            values=["server_id", "user_id", "available", "local_ip", "available_to"]
        )

        for connection in all_connections:
            try:
                if (
                    not connection.available_to
                    or connection.available_to > datetime.now()
                ):
                    # Подключение не назначено или еще активно.
                    continue

                # Если поле available_to меньше текущего времени на 5 дней
                # и статус подключения активный.
                if (
                    connection.available_to < datetime.now() - timedelta(days=5)
                    and connection.available
                ):
                    sc = ServerConnection(await Server.get(id=connection.server_id))
                    try:
                        # Замораживаем подключение, на всякий случай.
                        await sc.freeze_connection(connection.local_ip)
                        # Пересоздаем конфигурацию
                        config_obj = await VPNConnection.get(id=connection.id)
                        new_config = await sc.regenerate_config(
                            ConfigManager(config_obj.config)
                        )
                        # Обновляем конфигурацию в базе.
                        await config_obj.update(config=new_config.create_config())

                    except (ConnectionError, ProcessError):
                        # В случае ошибки на стороне сервера, будет попытка на следующей итерации.
                        pass
                    else:
                        # Освобождаем подключение от пользователя.
                        await connection.update(user_id=None, available_to=None, available=False)

                else:
                    # Вышел строк аренды подключения.
                    # Замораживаем.
                    sc = ServerConnection(await Server.get(id=connection.server_id))
                    await sc.freeze_connection(connection.local_ip)
                    # Подключение недоступно.
                    await connection.update(available=False)

            except Exception as exc:
                print(exc)

        await asyncio.sleep(10)
