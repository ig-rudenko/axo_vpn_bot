import asyncio
from db import async_db_session
from server_manager import config_manager, vpn_connections_manager, payment_manager


async def main():

    await asyncio.gather(
        asyncio.Task(async_db_session.create_all(), name="create_db_tables"),
        asyncio.Task(config_manager(), name="config_manager"),
        asyncio.Task(vpn_connections_manager(), name="vpn_connections_manager"),
        asyncio.Task(payment_manager(), name="payment_manager"),
    )


if __name__ == "__main__":
    asyncio.run(main())
