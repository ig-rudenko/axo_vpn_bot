import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from qiwi_payment import QIWIPayment
from db import ActiveBills, VPNConnection, Server, async_db_session
from .base import ServerConnection


async def payment_manager():
    qiwi = QIWIPayment(currency="RUB")

    while True:

        async with async_db_session() as session:
            query = select(ActiveBills).options(
                selectinload(ActiveBills.vpn_connections)
            )
            all_bills = await session.execute(query)

        for bill in all_bills:
            bill: ActiveBills
            try:
                status = await qiwi.check_bill_status(bill.bill_id)

                if status is None:
                    # Слишком много запросов на QIWI
                    await asyncio.sleep(10)

                elif status in ["REJECTED", "EXPIRED"] and bill.type == "new":
                    # Счет отклонен или истек срок действия формы и это новое подключение.
                    # Забронированные за пользователем подключения надо освободить.
                    for conn in bill.vpn_connections:
                        await conn.update(user_id=None, available=None)

                elif status == "PAID":  # Счет был оплачен
                    # Активируем подключения

                    for conn in bill.vpn_connections:
                        conn: VPNConnection
                        # Выбираем сервер, на котором необходимо активировать подключения
                        sc = ServerConnection(await Server.get(id=conn.server_id))
                        # Размораживаем подключение на сервере
                        await sc.unfreeze_connection(conn.local_ip)

                        if bill.type == "new":
                            # Если новое подключение
                            time_from = datetime.now()
                        elif bill.type == "extend":
                            # Добавляем к текущему времени
                            time_from = conn.available_to
                        else:
                            continue

                        await conn.update(
                            available=True,
                            user_id=bill.user,
                            available_to=time_from
                            + timedelta(days=31 * bill.rent_month),
                        )

                # Задержка перед запросами на QIWI
                await asyncio.sleep(5)

            except Exception as exc:
                print(exc)
                await asyncio.sleep(10)
