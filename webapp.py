# webapp.py
import asyncio
import uvicorn
import json
import os
import logging
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, FSInputFile, InputMediaDocument

# Импортируем наши настройки и генераторы
from config import TELEGRAM_TOKEN
from pdf_generator import generate_pdf as generate_kp
from estimate_generator import generate_strict_estimate

# Настройка логов
logging.basicConfig(level=logging.INFO)

# ================= НАСТРОЙКИ =================
# Сюда ты вставишь ссылку, которую даст Pinggy (шаг 2)
WEB_APP_URL = "https://septic-russia.ru"

# ================= ИНИЦИАЛИЗАЦИЯ =================
# 1. Веб-сервер (FastAPI)
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 2. Бот (Aiogram)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


# ================= ЧАСТЬ 1: ВЕБ-САЙТ (Для браузера Телеграма) =================
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Когда Телеграм открывает приложение, он стучится сюда.
    Мы отдаем ему файл templates/index.html
    """
    return templates.TemplateResponse("index.html", {"request": request})


# ================= ЧАСТЬ 2: БОТ (Для чата) =================

@dp.message(CommandStart())
async def start(message: types.Message):
    """
    По команде /start показываем кнопку для открытия приложения
    """
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Открыть смету", web_app=WebAppInfo(url=WEB_APP_URL))]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "👋 Привет! Нажми кнопку ниже, чтобы открыть конструктор сметы.",
        reply_markup=markup
    )


@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    """
    Сюда прилетают данные, когда папа нажимает "СФОРМИРОВАТЬ СМЕТУ" на сайте.
    """
    # 1. Получаем JSON от сайта
    data = json.loads(message.web_app_data.data)

    await message.answer(
        f"✅ Данные получены! \nКлиент: {data.get('client_name')}\nСептик: {data.get('product_id')}\n⏳ Генерирую PDF...")

    # 2. Генерируем файлы (используем твои готовые скрипты!)
    try:
        # КП
        kp_name = f"КП_{data.get('client_name')}.pdf"
        generate_kp(data, kp_name)

        # Смета
        smeta_name = f"Смета_{data.get('client_name')}.pdf"
        generate_strict_estimate(data, smeta_name)

        # 3. Отправляем
        media = [
            InputMediaDocument(media=FSInputFile(kp_name), caption="✅ Коммерческое предложение"),
            InputMediaDocument(media=FSInputFile(smeta_name), caption="✅ Смета + Договор")
        ]
        await message.answer_media_group(media)

        # 4. Чистим мусор
        if os.path.exists(kp_name): os.remove(kp_name)
        if os.path.exists(smeta_name): os.remove(smeta_name)

    except Exception as e:
        await message.answer(f"❌ Ошибка генерации: {e}")


# ================= ЗАПУСК ВСЕГО ВМЕСТЕ =================
# Эта магия запускает и Бота, и Сайт в одном скрипте

async def start_bot():
    # Удаляем вебхук (на всякий случай) и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


@app.on_event("startup")
async def on_startup():
    # Запускаем бота в фоновом режиме, когда стартует сервер
    asyncio.create_task(start_bot())


if __name__ == "__main__":
    # Запускаем сервер на порту 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)

