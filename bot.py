import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from handlers import introduction, buy_service, confirm_payment

from db import async_db_session


async def main():
    await async_db_session.create_all()

    bot = Bot(token=os.getenv("TG_BOT_TOKEN"), parse_mode="HTML")
    dp = Dispatcher()
    dp.include_router(introduction.router)
    dp.include_router(buy_service.router)
    dp.include_router(confirm_payment.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
