import asyncio

from db import Server, VPNConnection
from .base import ServerConnection, ConfigManager


async def config_manager(period: int = 60 * 10):
    """
    Сборщик VPN конфигураций
    :param period: Период опроса (default 10 мин)
    """

    while True:

        for server in await Server.all():
            server: Server
            try:
                sc = ServerConnection(server)

                # Собираем с сервера конфигурации
                await sc.collect_configs(folder="/root")

                for real_config in sc.config_files:
                    real_config: ConfigManager

                    # Пытаемся найти в базе текущую конфигурацию
                    current_config = await VPNConnection.get(
                        server_id=server.id, local_ip=real_config.client_ip_v4
                    )

                    if current_config is None:
                        # Если в базе нет такой конфигурации, то добавляем
                        await VPNConnection.create(
                            server_id=server.id,
                            user_id=None,
                            available=False,
                            local_ip=real_config.client_ip_v4,
                            available_to=None,
                            config=real_config.create_config(),
                            client_name=real_config.name,
                        )
                        continue

                    # Если нашли конфигурацию, то проверяем её с текущей на сервере.
                    if current_config.config != real_config.create_config():
                        # Если они отличаются, значит надо изменить конфиг в базе.

                        await current_config.update(config=real_config.create_config())

            except Exception as exc:
                print(exc)

        await asyncio.sleep(period)
