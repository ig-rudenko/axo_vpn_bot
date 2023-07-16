from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def send_technical_error(
    callback: CallbackQuery,
    text: str = "Технические неполадки, проносим свои извинения ☹️",
):
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔝 Назад", callback_data="start"))
    await callback.message.edit_text(
        text,
        reply_markup=keyboard.as_markup(),
    )
    await callback.answer()
