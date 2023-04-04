import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from qiwi_payment import QIWIPayment
from db import ActiveBills, VPNConnection, Server, async_db_session
from .base import ServerConnection


async def payment_manager(period: int = 5):
    """
    Обработчик QIWI платежей
    :param period: Период опроса (default 5 сек)
    """

    print("=== Запущен обработчик QIWI платежей ===")

    qiwi = QIWIPayment(currency="RUB")

    while True:

        async with async_db_session() as session:
            query = select(ActiveBills).options(
                selectinload(ActiveBills.vpn_connections)
            )
            all_bills = await session.execute(query)

        for bill in all_bills.scalars():
            bill: ActiveBills
            try:
                status = await qiwi.check_bill_status(bill.bill_id)

                if status is None:
                    # Слишком много запросов на QIWI
                    await asyncio.sleep(10)

                # Счет отклонен или истек срок действия формы и это новое подключение.
                elif status in ["REJECTED", "EXPIRED"] and bill.type == "new":
                    print(f"# Пользователь {bill.user:<5} | Счет отклонен")
                    # Забронированные за пользователем подключения надо освободить.
                    for conn in bill.vpn_connections:
                        await conn.update(
                            user_id=None, available_to=None, available=False
                        )

                    await bill.delete()

                # Счет был оплачен
                elif status == "PAID":
                    # Активируем подключения
                    print(f"# Пользователь {bill.user:<5} | Счет был оплачен")

                    for conn in bill.vpn_connections:
                        conn: VPNConnection
                        # Выбираем сервер, на котором необходимо активировать подключения
                        sc = ServerConnection(await Server.get(id=conn.server_id))
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
                        new_rent_to = rent_time_from + timedelta(
                            days=31 * bill.rent_month
                        )

                        print(
                            f"# Пользователь {bill.user:<5} | {rent_type}"
                            f" {conn.local_ip} на {bill.rent_month} мес. до {new_rent_to}"
                        )

                        await conn.update(
                            available=True,
                            user_id=bill.user,
                            available_to=new_rent_to,
                        )

                    await bill.delete()

                # Задержка перед запросами на QIWI
                await asyncio.sleep(3)

            except Exception as exc:
                print(f"Обработчик QIWI платежей | Счет {bill} | Ошибка {exc}")
                await asyncio.sleep(5)

        await asyncio.sleep(period)
