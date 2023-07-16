from abc import ABC, abstractmethod

from db import VPNConnection, User, Server


class AbstractNotifier(ABC):

    @abstractmethod
    async def notify_connection_expired(
        self, user: User, server: Server, connection: VPNConnection, days_left: int
    ):
        pass

    @abstractmethod
    async def notify_soon_expired(
        self, user: User, server: Server, connection: VPNConnection, days_left: int
    ):
        pass
