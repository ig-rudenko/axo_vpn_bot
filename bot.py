import logging

from aiogram.dispatcher.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types.input_file import FSInputFile
from aiogram.client.session.aiohttp import AiohttpSession
from handlers import introduction, buy_service, create_bill, profile, user_agreement

import settings


async def on_startup(dispatcher: Dispatcher, bot: Bot):
    await bot.set_webhook(
        f"{settings.BASE_URL}{settings.BOT_PATH}",
        certificate=FSInputFile(settings.CERTIFICATE_PATH),
        ip_address=settings.PUBLIC_IP,
        drop_pending_updates=True,
    )
    webhook = await bot.get_webhook_info()
    print("======== SET WEBHOOK ========")
    print(webhook)


async def on_shutdown(dispatcher: Dispatcher, bot: Bot):
    webhook = await bot.delete_webhook()
    print("======== DELETE WEBHOOK ======== ->", webhook)


def add_routes(dispatcher: Dispatcher):
    dispatcher.include_router(introduction.router)
    dispatcher.include_router(buy_service.router)
    dispatcher.include_router(profile.router)
    dispatcher.include_router(create_bill.router)
    dispatcher.include_router(user_agreement.router)


def main():
    session = AiohttpSession()
    bot_settings = {"session": session, "parse_mode": "HTML"}

    bot = Bot(token=settings.TOKEN, **bot_settings)
    dp = Dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Добавляем роуты
    add_routes(dp)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=settings.BOT_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host=settings.WEB_SERVER_HOST, port=settings.WEB_SERVER_PORT)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
