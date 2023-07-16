from .base import BaseConfigBuilder


class ConfigBuilder(BaseConfigBuilder):

    @property
    def raw_config(self):
        return "\n".join(self.config)

    def create_config(self) -> str:
        config = ""
        for line in self.config.rows:
            if line.startswith("Address"):
                config += f"Address = {self.config.client_ip_v4}/32,{self.config.client_ip_v6}/128\n"

            elif line.startswith("DNS"):
                config += "DNS = " + ",".join(self.config.dns) + "\n"

            elif line.startswith("AllowedIPs"):
                config += "AllowedIPs = " + ", ".join(self.default_allowed_ips) + "\n"

            else:
                config += line + "\n"

        return config.strip()

    def add_allowed_ips(self, allowed_ips: list[str]):
        self.default_allowed_ips += allowed_ips
