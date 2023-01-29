import os
import uuid
from datetime import datetime, timedelta

import aiohttp


class QIWIPayment:
    _token = os.getenv("QIWI_TOKEN")

    def __init__(self, currency="RUB", expiration_minutes=10):
        self.currency = currency
        self.available_to = datetime.now() + timedelta(minutes=expiration_minutes)

    async def create_bill(self, value: int) -> dict:

        # Время жизни формы оплаты 10 мин
        async with aiohttp.ClientSession() as session:
            response = await session.put(
                url=f"https://api.qiwi.com/partner/bill/v1/bills/{uuid.uuid4()}",
                headers={
                    "accept": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
                json={
                    "amount": {"currency": self.currency, "value": value},
                    "comment": "Axo VPN",
                    "expirationDateTime": f"{self.available_to.strftime('%Y-%m-%dT%H:%M:%S+03:00')}",
                },
            )
        if response.status == 200:
            return await response.json()

        return {}

    async def check_bill_status(self, bill_id: str) -> str:
        async with aiohttp.ClientSession() as session:
            response = await session.get(
                url=f"https://api.qiwi.com/partner/bill/v1/bills/{bill_id}",
                headers={
                    "accept": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
            )
        if response.status == 200:
            result = await response.json()
            return result["status"]["value"]

        return "None"
