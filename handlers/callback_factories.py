"""
Описывает классы фабрик callback запросов при нажатии кнопок.
"""


from aiogram.dispatcher.filters.callback_data import CallbackData


class DeviceCountCallbackFactory(CallbackData, prefix="devcount"):
    """
    Используется для выбора кол-ва новых VPN подключений к конкретному серверу.

    Класс содержит атрибуты:
     - count (int) - количество устройств.
     - server_id (int) - идентификатор VPN сервера.
    """

    count: int
    server_id: int


class ExtendRentCallbackFactory(CallbackData, prefix="extend_rent"):
    """
    Используется для продления текущего VPN подключения к конкретному серверу.

    Класс содержит атрибуты:
     - connection_id (int) - идентификатор VPN подключения.
     - server_id (int) - идентификатор сервера.
    """

    connection_id: int
    server_id: int


class BuyCallbackFactory(CallbackData, prefix="buy"):
    """
    Используется для формирования покупки:
    указания выбора кол-ва VPN подключений к серверу, период аренды в зависимости
    от типа аренды (новая, либо продление существующей).

    Класс содержит атрибуты:
     - type_ (str) - тип аренды ("new", "extend") - новое, либо продление.
     - month (int) - кол-во месяцев.
     - cost (int) - стоимость аренды.
     - server_id (int) - идентификатор сервера VPN.
     - count (int) - опционально, кол-во устройств для аренды (если аренда новых).
     - connection_id (int) - опционально, идентификатор существующего подключения.
    """
    type_: str
    month: int
    cost: int
    server_id: int
    count: int | None
    connection_id: int | None


class ConfirmPaymentCallbackFactory(CallbackData, prefix="submit_buy"):
    """
    Используется для подтвержденного выбора VPN аренды и покупки.

    Класс содержит атрибуты:
     - type_ (str) - тип аренды (`new`, `extend`) - новое, либо продление.
     - cost (int) - стоимость аренды.
     - count (int) - кол-во устройств для аренды.
     - month (int) - кол-во месяцев.
     - server_id (int) - опционально, идентификатор сервера VPN (если продление существующего подключения).
     - connection_id (int) - опционально, идентификатор существующего подключения.
    """
    type_: str
    cost: int
    count: int
    month: int
    server_id: int | None
    connection_id: int | None


class GetConfigCallbackFactory(CallbackData, prefix="config"):
    """
    Используется для указания идентификатора VPN подключения.

    Класс содержит один атрибут:
     - connection_id
    """
    connection_id: int
