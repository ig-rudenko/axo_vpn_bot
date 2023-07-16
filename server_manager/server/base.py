from abc import ABC, abstractmethod

import asyncssh
from asyncssh import SSHClientConnection

from db.models import Server
from ..configuration.base import BaseConfigBuilder


class ServerConnectionBase(ABC):
    config_file_prefix = "wg0-client"
    config_builder = None

    def __init__(self, server: Server):
        self.auth = {
            "host": server.ip,
            "port": server.port,
            "username": server.login,
            "password": server.password,
            "known_hosts": None,
        }
        self._configs: list[BaseConfigBuilder] = []

        self._conn: SSHClientConnection | None = None

    async def connect(self):
        self._conn = await asyncssh.connect(**self.auth)

    @property
    def config_files(self):
        return self._configs

    @abstractmethod
    async def collect_configs(self, folder="/root"):
        pass

    @abstractmethod
    async def unfreeze_connection(self, connection_ip: str):
        pass

    @abstractmethod
    async def freeze_connection(self, connection_ip: str):
        pass

    @abstractmethod
    async def regenerate_config(
        self, config_manager: BaseConfigBuilder
    ) -> BaseConfigBuilder:
        pass

    def __del__(self, **kwargs):
        self._conn.close()
        del self
