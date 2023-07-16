import logging
from abc import ABC, abstractmethod


class BaseManager(ABC):
    timeout: int = 60

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def task(self):
        pass

    @abstractmethod
    async def run(self):
        pass
