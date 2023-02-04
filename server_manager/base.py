import re

import asyncssh
from asyncssh import ProcessError

from db.models import Server


class ConfigManager:

    default_allowed_ips = [
        "64.0.0.0/2",
        "32.0.0.0/3",
        "128.0.0.0/3",
        "16.0.0.0/4",
        "176.0.0.0/4",
        "208.0.0.0/4",
        "0.0.0.0/5",
        "160.0.0.0/5",
        "200.0.0.0/5",
        "12.0.0.0/6",
        "168.0.0.0/6",
        "196.0.0.0/6",
        "8.0.0.0/7",
        "174.0.0.0/7",
        "194.0.0.0/7",
        "11.0.0.0/8",
        "173.0.0.0/8",
        "193.0.0.0/8",
        "172.128.0.0/9",
        "192.0.0.0/9",
        "172.64.0.0/10",
        "192.192.0.0/10",
        "172.32.0.0/11",
        "192.128.0.0/11",
        "172.0.0.0/12",
        "192.176.0.0/12",
        "192.160.0.0/13",
        "192.172.0.0/14",
        "192.170.0.0/15",
        "192.169.0.0/16",
        "10.66.66.1/32",
        "::/0",
    ]

    def __init__(self, config: str, name: str = ""):
        self.name = name
        self.client_name = None
        self._config: list[str] = config.split("\n")
        self.client_ip_v4 = None
        self.client_ip_v6 = None
        self.endpoint_ip = None
        self.endpoint_port = None
        self.dns: list[str] = []

        if match := re.match(r"wg0-client-(\d+?)\.conf", name):
            self.client_name = match.group(1)

        for line in self._config:
            if line.startswith("Address = "):
                if match := re.match(r"Address = (\S+)/32,(\S+)/128", line):
                    self.client_ip_v4 = match.group(1)
                    self.client_ip_v6 = match.group(2)
            if line.startswith("Endpoint = "):
                if match := re.match(r"Endpoint = (\S+):(\S+)", line):
                    self.endpoint_ip = match.group(1)
                    self.endpoint_port = match.group(2)
            if line.startswith("DNS = "):
                if match := re.match(r"DNS = (\S+)", line):
                    self.dns = match.group(1).split(",")

    @property
    def raw_config(self):
        return "\n".join(self._config)

    def create_config(self) -> str:
        config = ""
        for line in self._config:
            if line.startswith("Address"):
                config += f"Address = {self.client_ip_v4}/32,{self.client_ip_v6}/128\n"

            elif line.startswith("DNS"):
                config += "DNS = " + ",".join(self.dns) + "\n"

            elif line.startswith("AllowedIPs"):
                config += "AllowedIPs = " + ", ".join(self.default_allowed_ips) + "\n"

            else:
                config += line + "\n"

        return config.strip()

    def add_allowed_ips(self, allowed_ips: list[str]):
        self.default_allowed_ips += allowed_ips


class ServerConnection:

    config_file_prefix = "wg0-client"

    def __init__(self, server: Server):
        self.auth = {
            "host": server.ip,
            "port": server.port,
            "username": server.login,
            "password": server.password,
            "known_hosts": None,
        }
        self._configs: list["ConfigManager"] = []

    @property
    def config_files(self):
        return self._configs

    async def collect_configs(self, folder="/root"):

        list_config_cmd = rf"ls -l {folder} | grep {self.config_file_prefix}"

        async with asyncssh.connect(**self.auth) as conn:
            result = await conn.run(list_config_cmd, timeout=3)
            config_files_names = re.findall(r"(wg0-client-\d+?\.conf)", result.stdout)
            for file_name in config_files_names:
                config = await conn.run(f"cat {folder}/{file_name}", timeout=3)
                self._configs.append(ConfigManager(config.stdout, name=file_name))

    async def unfreeze_connection(self, connection_ip: str):
        async with asyncssh.connect(**self.auth) as conn:
            try:
                await conn.run(
                    f"ip route del {connection_ip} via 127.0.0.1", check=True, timeout=3
                )
            except ProcessError as exc:
                # Если уже разморожено
                if exc.exit_status != 2:
                    raise exc

    async def freeze_connection(self, connection_ip: str):
        async with asyncssh.connect(**self.auth) as conn:
            try:
                await conn.run(
                    f"ip route add {connection_ip} via 127.0.0.1", check=True, timeout=3
                )
            except ProcessError as exc:
                # Если уже заморожено
                if exc.exit_status != 2:
                    raise exc

    async def regenerate_config(self, config: ConfigManager) -> ConfigManager:
        async with asyncssh.connect(**self.auth) as conn:
            result = await conn.run("cat /etc/wireguard/params", check=True, timeout=3)
            wg_params = {
                key: value
                for key, value in re.findall(r"([A-Z\d_]+)=(.+)\n?", result.stdout)
            }
            endpoint = wg_params["SERVER_PUB_IP"] + ":" + wg_params["SERVER_PORT"]

            # Generate key pair for the client
            result = await conn.run(r"wg genkey", check=True, timeout=3)
            client_private_key = result.stdout.strip()
            result = await conn.run(
                rf'echo "{client_private_key}" | wg pubkey', check=True, timeout=3
            )
            client_public_key = result.stdout.strip()
            result = await conn.run(r"wg genpsk", check=True, timeout=3)
            client_pre_shared_key = result.stdout.strip()

            # remove [Peer] block matching `config.client_name`
            await conn.run(
                rf'sed -i "/^### Client {config.client_name}\$/,/^$/d" "/etc/wireguard/{wg_params["SERVER_WG_NIC"]}.conf"',
                timeout=3,
                check=True,
            )

            # remove generated client file
            await conn.run(rf'rm -f "/root/{config.name}"', timeout=3)

            # restart wireguard to apply changes
            await conn.run(
                rf'wg syncconf "{wg_params["SERVER_WG_NIC"]}" <(wg-quick strip "{wg_params["SERVER_WG_NIC"]}")',
                check=True,
                timeout=3,
            )

            # Новая конфигурация
            new_config = f"""[Interface]
PrivateKey = {client_private_key}
Address = {config.client_ip_v4}/32,{config.client_ip_v6}/128
DNS = {wg_params["CLIENT_DNS_1"]},{wg_params["CLIENT_DNS_2"]}

[Peer]
PublicKey = {wg_params["SERVER_PUB_KEY"]}
PresharedKey = {client_pre_shared_key}
Endpoint = {endpoint}
AllowedIPs = 0.0.0.0/0,::/0"""

            # Create client file and add the server as a peer
            await conn.run(
                rf'''echo "{new_config}" >>"/root/{config.name}"''',
                check=True,
                timeout=3,
            )

            # Add the client as a peer to the server
            await conn.run(
                rf'''echo -e "\n### Client {config.client_name}
[Peer]
PublicKey = {client_public_key}
PresharedKey = {client_pre_shared_key}
AllowedIPs = {config.client_ip_v4}/32,{config.client_ip_v6}/128" >>"/etc/wireguard/{wg_params["SERVER_WG_NIC"]}.conf"''',
                check=True,
                timeout=3,
            )

            await conn.run(
                rf'wg syncconf "{wg_params["SERVER_WG_NIC"]}" <(wg-quick strip "{wg_params["SERVER_WG_NIC"]}")',
                check=True,
                timeout=3,
            )

            return ConfigManager(new_config, name=config.name)
