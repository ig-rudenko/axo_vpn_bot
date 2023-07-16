from abc import ABC, abstractmethod


class AbstractPayment(ABC):
    @abstractmethod
    def create_bill(self, *args, **kwargs):
        pass

    @abstractmethod
    def check_bill_status(self, *args, **kwargs):
        pass
