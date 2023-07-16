from dataclasses import dataclass


@dataclass
class WGParams:
    """
    Параметры wireguard на сервере.
    """

    SERVER_PUB_IP: str
    SERVER_PUB_NIC: str
    SERVER_WG_NIC: str
    SERVER_WG_IPV4: str
    SERVER_WG_IPV6: str
    SERVER_PORT: str
    SERVER_PRIV_KEY: str
    SERVER_PUB_KEY: str
    CLIENT_DNS_1: str
    CLIENT_DNS_2: str

    @property
    def endpoint(self):
        return self.SERVER_PUB_IP + ":" + self.SERVER_PORT


@dataclass
class KeyPair:
    private_key: str
    public_key: str
    pre_shared_key: str
