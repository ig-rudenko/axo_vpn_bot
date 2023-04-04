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

    print("=== Запущен обработчик аренды VPN подключений ===")

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
                if connection.available_to < datetime.now() - timedelta(days=5):

                    server = await Server.get(id=connection.server_id)
                    sc = ServerConnection(server)

                    print(
                        f"# Сервер: {server.name:<15} | "
                        f"Подключение {connection.local_ip} необходимо пересоздать"
                    )

                    try:
                        # Замораживаем подключение, на всякий случай.
                        await sc.freeze_connection(connection.local_ip)
                        # Вытягиваем из базы объект VPN подключения со всеми полями.
                        config_obj = await VPNConnection.get(id=connection.id)

                        # Пересоздаем конфигурацию.
                        new_config: ConfigManager = await sc.regenerate_config(
                            ConfigManager(
                                config=config_obj.config, name=config_obj.client_name
                            )
                        )
                        # Обновляем конфигурацию в базе.
                        await config_obj.update(config=new_config.create_config())

                    except (ConnectionError, ProcessError) as exc:
                        exc: ProcessError
                        # В случае ошибки на стороне сервера, будет попытка на следующей итерации.
                        print(
                            f"# Сервер: {server.name:<15} | "
                            f"Подключение: {connection.local_ip} | Ошибка: {exc.stderr}"
                        )

                    else:
                        # Освобождаем подключение от пользователя.
                        await connection.update(
                            user_id=None, available_to=None, available=False
                        )

                else:
                    # Вышел строк аренды подключения.
                    # Замораживаем.
                    server = await Server.get(id=connection.server_id)
                    sc = ServerConnection(server)
                    print(
                        f"# Сервер: {server.name:<15} | "
                        f"Подключение {connection.local_ip} необходимо заморозить"
                    )
                    await sc.freeze_connection(connection.local_ip)
                    # Подключение недоступно.
                    await connection.update(available=False)

            except Exception as exc:
                print(
                    f"Обработчик аренды VPN подключений |"
                    f" Подключение: {connection.local_ip} | Ошибка: {exc}"
                )

        await asyncio.sleep(period)
