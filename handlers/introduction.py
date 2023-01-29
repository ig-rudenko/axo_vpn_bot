import flag
from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import Server
from .callback_factories import DeviceCountCallbackFactory as DevCountCF

router = Router()


@router.callback_query(text="start")
async def home(callback: CallbackQuery):
    await welcome(callback.message.edit_text)
    await callback.answer()


@router.message(commands="start")
async def home(message: Message):
    await welcome(message.answer)


async def welcome(message_type):
    text = f"""
👋🏽 Добро пожаловать

                <b>🌐             AXO VPN            🌐</b>

<b>🔥 У нас самые низкие цены на рынке!</b>

<b>Мы используем Wireguard</b>

                          <b>❎ Блокируем: ❎</b>

<b>Запросы на рекламу на всех устройствах💻📱🖥 </b>

<b>🪲 Запросы на вредоносные сайты </b>

<b>📊 Аналитические запросы </b>

<b>🚰 Защищаем от утечки DNS ⛓</b>

<b>📝 Не пишем логи 🗑</b>
    """
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🌍 Доступные страны", callback_data="show_countries"),
        InlineKeyboardButton(text="❔ Как пользоваться", callback_data="how_to_use"),
    )
    keyboard.row(
        InlineKeyboardButton(
            text="💱 Купить подключение", callback_data="choose_location"
        )
    )
    keyboard.row(InlineKeyboardButton(text="🔹 Профиль 🔹", callback_data="show_profile"))
    await message_type(text, reply_markup=keyboard.as_markup())


@router.callback_query(text="how_to_use")
async def how_to_use(call: CallbackQuery):
    text = f"""
1️⃣ Скачиваем клиент <a href='https://www.wireguard.com/'>Wireguard</a>:

📱 Android: [<a href='https://play.google.com/store/apps/details?id=com.wireguard.android'>PlayStore</a>] [<a href='https://f-droid.org/repo/com.wireguard.android_491.apk'>F-Droid</a>]

📱 iOS: [<a href='https://itunes.apple.com/us/app/wireguard/id1451685025?ls=1&mt=12'>AppStore</a>]

💻 Windows: [<a href='https://download.wireguard.com/windows-client/wireguard-installer.exe'>С официального сайта</a>]

💻 Linux: [<a href='https://www.wireguard.com/install/'>На сайте</a>]

2️⃣ Покупаем подключение, скачиваем файл для подключения в Профиле

3️⃣ Открываем приложение и добавляем скачанный файл

"""
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="start"))
    await call.message.edit_text(text, reply_markup=keyboard.as_markup())


@router.callback_query(text="show_countries")
async def show_countries(callback: CallbackQuery):
    """
    Список доступных стран
    """

    countries = ""
    # Смотрим список VPN серверов
    for server in await Server.all(values=["country_code", "location"]):
        # Добавляем флаг страны и местоположение VPN сервера
        countries += flag.flagize(
            f":{server.country_code}: {server.location}\n", subregions=True
        )

    keyboard = InlineKeyboardBuilder(
        [[InlineKeyboardButton(text="🔙 Назад", callback_data=f"start")]]
    )
    await callback.message.edit_text(
        text="Список стран\n" + countries,
        reply_markup=keyboard.as_markup(),
    )
    await callback.answer()
