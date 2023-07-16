import asyncio
import logging

from db import async_db_session
from server_manager.managers import ConfigManager, PaymentManager, VPNControlManager


async def main():
    await asyncio.gather(
        asyncio.Task(async_db_session.create_all(), name="create_db_tables"),
        asyncio.Task(ConfigManager().run(), name="config_manager"),
        asyncio.Task(VPNControlManager().run(), name="vpn_connections_manager"),
        asyncio.Task(PaymentManager().run(), name="payment_manager"),
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    asyncio.run(main())
