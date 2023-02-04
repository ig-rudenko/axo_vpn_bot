import asyncio
from datetime import datetime, timedelta

from asyncssh.process import ProcessError

from db import VPNConnection, Server
from .base import ServerConnection, ConfigManager


async def vpn_connections_manager(period: int = 60 * 10):
    """
    Обработчик аренды VPN подключений
    :param period: Период опроса (default 10 мин)
    """

    while True:

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
                        # Вытягиваем из базы объект VPN подключения со всеми полями.
                        config_obj = await VPNConnection.get(id=connection.id)
                        # Пересоздаем конфигурацию.
                        new_config = await sc.regenerate_config(
                            ConfigManager(
                                config=config_obj.config, name=config_obj.client_name
                            )
                        )
                        # Обновляем конфигурацию в базе.
                        await config_obj.update(config=new_config.create_config())

                    except (ConnectionError, ProcessError) as exc:
                        exc: ProcessError
                        # В случае ошибки на стороне сервера, будет попытка на следующей итерации.
                        pass
                    else:
                        # Освобождаем подключение от пользователя.
                        await connection.update(
                            user_id=None, available_to=None, available=False
                        )

                else:
                    # Вышел строк аренды подключения.
                    # Замораживаем.
                    sc = ServerConnection(await Server.get(id=connection.server_id))
                    await sc.freeze_connection(connection.local_ip)
                    # Подключение недоступно.
                    await connection.update(available=False)

            except Exception as exc:
                print(exc)

        await asyncio.sleep(period)
