import re

from asyncssh import ProcessError

from ..configuration.base import Config
from ..configuration.manager import ConfigBuilder
from ..server.base import ServerConnectionBase
from ..server.types import WGParams, KeyPair


class ServerConnection(ServerConnectionBase):
    config_builder = ConfigBuilder

    @property
    def config_files(self):
        return self._configs

    async def collect_configs(self, folder="/root"):
        list_config_cmd = rf"ls -l {folder} | grep {self.config_file_prefix}"

        result = await self._conn.run(list_config_cmd, timeout=3)
        config_files_names = re.findall(r"(wg0-client-\d+?\.conf)", result.stdout)
        for file_name in config_files_names:
            config = await self._conn.run(f"cat {folder}/{file_name}", timeout=3)
            config_manager = self.config_builder(config.stdout, name=file_name)
            self._configs.append(config_manager)

    async def unfreeze_connection(self, connection_ip: str):
        try:
            await self._conn.run(
                f"ip route del {connection_ip} via 127.0.0.1", check=True, timeout=3
            )
        except ProcessError as exc:
            # Если уже разморожено
            if exc.exit_status != 2:
                raise exc

    async def freeze_connection(self, connection_ip: str):
        try:
            await self._conn.run(
                f"ip route add {connection_ip} via 127.0.0.1", check=True, timeout=3
            )
        except ProcessError as exc:
            # Если уже заморожено
            if exc.exit_status != 2:
                raise exc

    async def regenerate_config(self, config_manager: config_builder) -> config_builder:
        config = config_manager.config
        wg_params = await self._get_wg_params()
        key_pair = await self._get_keypair()

        await self._remove_client(config, wg_params)
        await self._restart_wireguard(wg_params)

        # Новая конфигурация
        new_config_manager = await self._create_and_get_new_config_file_manager(
            config=config, wg_params=wg_params, key_pair=key_pair
        )

        await self._add_client(
            config=new_config_manager.config, wg_params=wg_params, key_pair=key_pair
        )
        await self._restart_wireguard(wg_params)

        return new_config_manager

    async def _get_wg_params(self) -> WGParams:
        result = await self._conn.run(
            "cat /etc/wireguard/params", check=True, timeout=3
        )
        file_lines = re.findall(r"([A-Z\d_]+)=(.+)\n?", result.stdout)
        return WGParams(**{key: value for key, value in file_lines})

    async def _get_keypair(self) -> KeyPair:
        """Generate key pair for the client"""

        result = await self._conn.run(r"wg genkey", check=True, timeout=3)
        client_private_key = result.stdout.strip()
        result = await self._conn.run(
            rf'echo "{client_private_key}" | wg pubkey', check=True, timeout=3
        )
        client_public_key = result.stdout.strip()
        result = await self._conn.run(r"wg genpsk", check=True, timeout=3)
        client_pre_shared_key = result.stdout.strip()
        return KeyPair(
            public_key=client_public_key,
            private_key=client_private_key,
            pre_shared_key=client_pre_shared_key,
        )

    async def _create_and_get_new_config_file_manager(
        self, config: Config, wg_params: WGParams, key_pair: KeyPair
    ) -> config_builder:
        # Новая конфигурация
        new_config = f"""[Interface]
PrivateKey = {key_pair.private_key}
Address = {config.client_ip_v4}/32,{config.client_ip_v6}/128
DNS = {wg_params.CLIENT_DNS_1},{wg_params.CLIENT_DNS_2}

[Peer]
PublicKey = {wg_params.SERVER_PUB_KEY}
PresharedKey = {key_pair.pre_shared_key}
Endpoint = {wg_params.endpoint}
AllowedIPs = 0.0.0.0/0,::/0"""

        # Create client file and add the server as a peer
        await self._conn.run(
            rf'''echo "{new_config}" >>"/root/{config.name}"''', check=True, timeout=3
        )

        return self.config_builder(config=new_config, name=config.name)

    async def _add_client(self, config: Config, wg_params: WGParams, key_pair: KeyPair):
        """Add the client as a peer to the server"""

        await self._conn.run(
            rf'''echo -e "\n### Client {config.client_name}
[Peer]
PublicKey = {key_pair.public_key}
PresharedKey = {key_pair.pre_shared_key}
AllowedIPs = {config.client_ip_v4}/32,{config.client_ip_v6}/128" >>"/etc/wireguard/{wg_params.SERVER_WG_NIC}.conf"''',
            check=True,
            timeout=3,
        )

    async def _remove_client(self, config: Config, wg_params: WGParams):
        """
        remove [Peer] block matching `config.client_name`.

        remove generated client file.
        """

        await self._conn.run(
            rf'sed -i "/^### Client {config.client_name}\$/,/^$/d" "/etc/wireguard/{wg_params.SERVER_WG_NIC}.conf"',
            timeout=3,
            check=True,
        )
        await self._conn.run(rf'rm -f "/root/{config.name}"', timeout=3)

    async def _restart_wireguard(self, wg_params: WGParams):
        """Restart wireguard to apply changes"""
        await self._conn.run(
            rf'wg syncconf "{wg_params.SERVER_WG_NIC}" <(wg-quick strip "{wg_params.SERVER_WG_NIC}")',
            check=True,
            timeout=3,
        )
