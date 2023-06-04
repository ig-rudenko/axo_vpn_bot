from aiogram import Router
from aiogram.dispatcher.filters import Text
from aiogram.types import CallbackQuery

from settings import TEMPLATE_DIR

router = Router()


@router.callback_query(Text(text="user_agreement"))
async def user_agreement(callback: CallbackQuery):
    """
    Отправляем пользовательское соглашение.
    """
    with open(TEMPLATE_DIR / "user_agreement.html", encoding="utf-8") as file:
        text = file.read()

    for text_chunk in text.split("<hr>"):
        await callback.message.answer(text=text_chunk)

    await callback.message.reply("Продолжим")
    await callback.answer()
