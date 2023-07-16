import asyncio

from db import Server, VPNConnection
from .base import BaseManager
from ..configuration.base import BaseConfigBuilder
from ..server import ServerConnection


class ConfigManager(BaseManager):
    """Сборщик VPN конфигураций"""

    timeout = 60 * 10

    async def run(self):
        print("=== Запущен сборщик VPN конфигураций ===")
        while True:
            await self.task()
            await asyncio.sleep(self.timeout)

    async def task(self):
        all_servers: list[Server] = await Server.all()

        for server in all_servers:
            self.logger.info(f"Смотрим сервер {server.name} {server.location}")
            try:
                config_files = await self._get_server_config_files(server)
                for config_manager in config_files:
                    # Пытаемся найти в базе текущую конфигурацию
                    connection: VPNConnection = await VPNConnection.get(
                        server_id=server.id, local_ip=config_manager.config.client_ip_v4
                    )

                    if connection is None:
                        await self._create_new_connection(server, config_manager)

                    # Если нашли конфигурацию, то проверяем её с текущей на сервере.
                    elif connection.config != config_manager.config.config_text:
                        await self._update_connection(
                            server, connection, config_manager
                        )

            except Exception as exc:
                self.logger.error(
                    f"Сборщик VPN конфигураций | Сервер {server.name} | Ошибка {exc}",
                    exc_info=exc,
                )

    @staticmethod
    async def _get_server_config_files(server: Server) -> list[BaseConfigBuilder]:
        sc = ServerConnection(server)
        await sc.connect()

        # Собираем с сервера конфигурации
        await sc.collect_configs(folder="/root")
        return sc.config_files

    async def _create_new_connection(
        self, server: Server, config_manager: BaseConfigBuilder
    ):
        # Если в базе нет такой конфигурации, то добавляем
        self.logger.info(
            f"# Север: {server.name:<15} | "
            f"Добавляем конфигурацию для {config_manager.config.client_ip_v4}"
        )
        await VPNConnection.create(
            server_id=server.id,
            user_id=None,
            available=False,
            local_ip=config_manager.config.client_ip_v4,
            available_to=None,
            config=config_manager.create_config(),
            client_name=config_manager.config.name,
        )

    async def _update_connection(
        self, server: Server, conn: VPNConnection, config_manager: BaseConfigBuilder
    ):
        self.logger.info(
            f"# Север: {server.name:<15} | "
            f"Изменяем конфигурацию для {config_manager.config.client_ip_v4}"
        )
        # Если они отличаются, значит надо изменить конфиг в базе.
        await conn.update(config=config_manager.config.config_text)
