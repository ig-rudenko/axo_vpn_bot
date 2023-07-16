import asyncio
from datetime import datetime, timedelta

from sqlalchemy import inspect

from payment.base import AbstractPayment
from payment.qiwi_payment import QIWIPayment
from db import ActiveBills, VPNConnection, Server
from ..server import ServerConnection
from .base import BaseManager


class PaymentManager(BaseManager):
    timeout = 10
    payment_class: AbstractPayment = QIWIPayment

    def __init__(self):
        super().__init__()
        self._qiwi = self.payment_class(currency="RUB")

    async def run(self):
        print("=== Запущен обработчик QIWI платежей ===")
        while True:
            await self.task()
            await asyncio.sleep(self.timeout)

    async def task(self):
        all_bills: list[ActiveBills] = await ActiveBills.all(
            select_in_load="vpn_connections"
        )

        for bill in all_bills:
            try:
                await self._processing_bill(bill)
            except Exception as exc:
                self.logger.error(
                    f"Обработчик QIWI платежей | Счет {bill} | Ошибка {exc}",
                    exc_info=exc,
                )
                await asyncio.sleep(5)

    async def _processing_bill(self, bill: ActiveBills):
        status = await self._qiwi.check_bill_status(bill.bill_id)

        if status is None:
            # Слишком много запросов на QIWI
            await asyncio.sleep(10)

        # Счет отклонен или истек срок действия формы и это новое подключение.
        elif status in ["REJECTED", "EXPIRED"] and bill.type == "new":
            await self._reject_bill(bill)

        # Счет был оплачен
        elif status == "PAID":
            await self._activate_connections(bill)
            await bill.delete()

        # Задержка перед запросами на QIWI
        await asyncio.sleep(3)

    async def _reject_bill(self, bill: ActiveBills):
        self.logger.info(f"# Пользователь {bill.user:<5} | Счет отклонен")
        # Забронированные за пользователем подключения надо освободить.
        for conn in bill.vpn_connections:
            conn: VPNConnection
            await conn.update(user_id=None, available_to=None, available=False)

        await bill.delete()

    async def _activate_connections(self, bill: ActiveBills):
        # Активируем подключения
        self.logger.info(f"# Пользователь {bill.user:<5} | Счет был оплачен")

        for conn in bill.vpn_connections:
            conn: VPNConnection

            # Выбираем сервер, на котором необходимо активировать подключения
            try:
                sc = ServerConnection(await Server.get(id=conn.server_id))
            except Server.DoesNotExists:
                continue

            await sc.connect()
            # Размораживаем подключение на сервере
            await sc.unfreeze_connection(conn.local_ip)

            if bill.type == "new":
                # Если новое подключение
                rent_type = "Новое подключение"

            elif bill.type == "extend":
                # Добавляем к текущему времени
                rent_type = "Продление подключения"

            else:
                continue

            # Либо продление, либо новое
            rent_time_from = conn.available_to or datetime.now()

            # Новое время окончания аренды
            new_rent_to = rent_time_from + timedelta(days=31 * bill.rent_month)

            self.logger.info(
                f"# Пользователь {bill.user:<5} | {rent_type}"
                f" {conn.local_ip} на {bill.rent_month} мес. до {new_rent_to}"
            )

            await conn.update(
                available=True,
                user_id=bill.user,
                available_to=new_rent_to,
            )
