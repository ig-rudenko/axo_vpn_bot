from aiogram.dispatcher.filters.callback_data import CallbackData


class DeviceCountCallbackFactory(CallbackData, prefix="devcount"):
    count: int
    server_id: int


class ExtendRentCallbackFactory(CallbackData, prefix="extend_rent"):
    connection_id: int
    server_id: int


class BuyCallbackFactory(CallbackData, prefix="buy"):
    type_: str
    month: int
    cost: int
    server_id: int
    count: int | None
    connection_id: int | None


class ConfirmPaymentCallbackFactory(CallbackData, prefix="submit_buy"):
    type_: str
    cost: int
    count: int
    month: int
    server_id: int | None
    connection_id: int | None


class GetConfigCallbackFactory(CallbackData, prefix="config"):
    connection_id: int
