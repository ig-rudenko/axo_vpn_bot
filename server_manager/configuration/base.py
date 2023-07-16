import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Config:
    rows: list[str]
    name: str = ""
    client_name: str = ""
    client_ip_v4: str = ""
    client_ip_v6: str = ""
    endpoint_ip: str = ""
    endpoint_port: str = ""
    dns: list[str] = field(default_factory=list)

    @property
    def config_text(self):
        return "\n".join(self.rows)


class BaseConfigBuilder(ABC):
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
        self.config = self._parse_config(config, name)

    @staticmethod
    def _parse_config(config_text: str, name: str) -> Config:
        rows = config_text.split("\n")
        config = Config(name=name, rows=rows)
        if match := re.match(r"wg0-client-(\d+?)\.conf", name):
            config.client_name = match.group(1)

        for line in config.rows:
            if line.startswith("Address = "):
                if match := re.match(r"Address = (\S+)/32,(\S+)/128", line):
                    config.client_ip_v4 = match.group(1)
                    config.client_ip_v6 = match.group(2)
            if line.startswith("Endpoint = "):
                if match := re.match(r"Endpoint = (\S+):(\S+)", line):
                    config.endpoint_ip = match.group(1)
                    config.endpoint_port = match.group(2)
            if line.startswith("DNS = "):
                if match := re.match(r"DNS = (\S+)", line):
                    config.dns = match.group(1).split(",")

        return config

    @abstractmethod
    def create_config(self) -> str:
        pass

    @abstractmethod
    def add_allowed_ips(self, allowed_ips: list[str]):
        pass
