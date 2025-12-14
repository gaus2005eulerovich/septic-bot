# main.py
import asyncio
import os
import json
import logging
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, \
    InputMediaDocument
from aiogram.filters import CommandStart
from openai import OpenAI

# Импорт настроек
from config import TELEGRAM_TOKEN

AI_API_KEY = os.getenv("AI_API_KEY")
# Настройки для DeepSeek
AI_BASE_URL = "https://api.deepseek.com"
AI_MODEL = "deepseek-chat"

# Импорт ГЕНЕРАТОРОВ (Оба файла должны лежать рядом)
from pdf_generator import generate_pdf as generate_kp  # Красивое КП
from estimate_generator import generate_strict_estimate  # Строгая Смета + Инструкции

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Настройка нейросети
ai_client = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)

# Настройка бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# === ПАМЯТЬ БОТА ===
# Здесь мы храним текущий заказ, пока папа его редактирует
# Структура: { user_id: {json_data} }
user_orders = {}


# --- ХЕЛПЕР: Вытаскиваем JSON из ответа ---
def extract_json_from_response(text):
    try:
        # Ищем блок кода ```json ... ``` или просто { ... }
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return None
    except Exception as e:
        print(f"JSON Parse Error: {e}")
        return None


# --- ПЛАН Б: РУЧНОЙ ПОИСК (Если AI сломался) ---
def parse_order_manually(text):
    logging.info("⚠️ Использую ручной режим (Regex)...")
    original_text = text
    text = text.lower()
    data = {}

    # 1. Имя
    name_match = re.search(r'(клиент|заказчик|зовут)\s+([А-Яа-яA-Za-z]+)', original_text, re.IGNORECASE)
    data['client_name'] = name_match.group(2).capitalize() if name_match else "Клиент"

    # 2. Товар
    if any(w in text for w in ['1.1', 'большая', 'единичка', 'один и один']):
        data['product_id'] = 'tver_11'
    elif 'евролос' in text:
        data['product_id'] = 'eurolos'
    else:
        data['product_id'] = 'tver_08'

    # 3. Грунт
    if any(w in text for w in ['глина', 'суглинок', 'тяжело', 'твердый']):
        data['soil'] = 'clay'
    else:
        data['soil'] = 'sand'

    # 4. Труба (число)
    meters_match = re.search(r'(\d+)\s*(м|метр)', text)
    data['pipe_length'] = int(meters_match.group(1)) if meters_match else 5

    # 5. Бурение
    if any(w in text for w in ['бур', 'прокол', 'фундамент', 'дырк', 'алмаз']):
        data['diamond_drilling'] = True
    else:
        data['diamond_drilling'] = False

    # 6. Адрес
    address_match = re.search(r'(адрес|снт|улица|ул\.|поселок|г\.|город)\s+([А-Яа-я0-9\s\.\-]{3,20})', original_text,
                              re.IGNORECASE)
    data['address'] = f"{address_match.group(1)} {address_match.group(2)}".strip() if address_match else "Не указан"

    # 7. Custom items (простой поиск ключевых слов для демо)
    data['custom_items'] = []
    if "вывоз" in text:
        data['custom_items'].append({"name": "Вывоз грунта", "price": 5000})

    return data


# --- ФУНКЦИЯ 1: МОЗГИ (DEEPSEEK С ПОНИМАНИЕМ ПРАЙСА) ---
def analyze_request_ai(text, current_data=None):
    # Подсказка для нейросети по услугам (из services.py)
    # Мы учим AI использовать правильные ключи
    services_hint = """
    СПИСОК ДОП. УСЛУГ (Используй эти ключи в поле "service_key" для custom_items):
    - "manual_sand_transport": если надо таскать песок вручную или далеко (>10м).
    - "manual_soil_transport": вывоз грунта вручную/тачкой.
    - "cable_laying": прокладка электрического кабеля (в гофре).
    - "socket_install": установка розетки.
    - "diamond_drilling_40": алмазное бурение (если толстый бетон/фундамент).
    - "opalubka_t4": если упомянут плывун, осыпающийся грунт или нужна опалубка.
    - "hole_in_ring": прокол кольца жби.
    - "shakhtersky_podkop": шахтерский подкоп.
    """

    # 1. СЦЕНАРИЙ: НОВЫЙ ЗАКАЗ
    if not current_data:
        system_prompt = f"""
        Ты - калькулятор смет. Твоя цель: превратить текст прораба в JSON.

        {services_hint}

        СТРУКТУРА JSON:
        {{
            "client_name": "Имя (или Заказчик)",
            "address": "Адрес (или Не указан)",
            "product_id": "tver_08" (по умолч) или "tver_11",
            "soil": "sand" (по умолч) или "clay",
            "pipe_length": int (метров, по умолч 5),
            "diamond_drilling": bool (обычное бурение),

            "custom_items": [
                // Если фраза совпадает с услугой из списка выше -> пиши service_key и qty (кол-во)
                {{ "service_key": "manual_sand_transport", "qty": 5 }},
                // Если услуги нет в списке -> пиши просто name и price (цену придумай адекватную или возьми из текста)
                {{ "name": "Демонтаж старого туалета", "price": 3000, "qty": 1 }}
            ]
        }}
        """
        user_content = f"Заказ: {text}"

    # 2. СЦЕНАРИЙ: ПРАВКА СУЩЕСТВУЮЩЕГО
    else:
        system_prompt = f"""
        Ты - редактор JSON данных. 
        {services_hint}

        ПРАВИЛА ОБНОВЛЕНИЯ:
        1. ОТРИЦАНИЯ: Если написано "не нужно бурить" -> ставь "diamond_drilling": false.
        2. ИЗМЕНЕНИЯ: Если меняют имя/адрес/метры -> перезапиши поле.
        3. ДОБАВЛЕНИЯ: Добавляй услуги в массив "custom_items" (используй ключи service_key, если подходит).
           НЕ удаляй старые услуги из списка, если не просили!

        ВЕРНИ ТОЛЬКО ПОЛНЫЙ ОБНОВЛЕННЫЙ JSON.
        """
        # Передаем текущее состояние и просьбу пользователя
        user_content = f"ТЕКУЩИЙ JSON:\n{json.dumps(current_data, ensure_ascii=False)}\n\nПРАВКА ПОЛЬЗОВАТЕЛЯ:\n{text}"

    # Отправляем запрос
    try:
        response = ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,  # Низкая температура для точности
            stream=False,
            timeout=40.0
        )
        content = response.choices[0].message.content
        print(f"AI Response: {content}")  # Лог для отладки

        return extract_json_from_response(content)

    except Exception as e:
        print(f"API Error: {e}")
        # ЕСЛИ AI УПАЛ (Timeout/Error) -> ВКЛЮЧАЕМ ПЛАН Б (Regex), но только для новых заказов
        if not current_data:
            return parse_order_manually(text)
        return None


# --- КЛАВИАТУРА ---
def get_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖨 Печать документов", callback_data="print_docs")],
        [InlineKeyboardButton(text="❌ Сброс", callback_data="cancel")]
    ])


# --- ОПИСАНИЕ ЗАКАЗА (ДЛЯ ЧАТА) ---
def format_order_text(data):
    p_name = "Тверь 0.8" if data.get('product_id') == 'tver_08' else "Тверь 1.1"
    soil = "Глина" if data.get('soil') == 'clay' else "Песок"

    # Формируем список допов для предпросмотра
    custom_text = ""
    if data.get('custom_items'):
        custom_text = "\n➕ **Доп. услуги:**\n"
        for item in data['custom_items']:
            # Если есть ключ сервиса, мы покажем его код (или можно сделать маппинг имен, но для теста сойдет)
            name = item.get('name', item.get('service_key', 'Услуга'))
            price = item.get('price', 'по прайсу')
            qty = item.get('qty', 1)
            custom_text += f"🔸 {name} (x{qty}) — {price} руб.\n"

    return (
        f"📋 **ИТОГОВЫЕ ДАННЫЕ:**\n"
        f"👤 {data.get('client_name')} | 📍 {data.get('address')}\n"
        f"📦 {p_name}\n"
        f"🌍 {soil} | 📏 Труба: {data.get('pipe_length')} м\n"
        f"🛠 Бурение: {'✅ ДА' if data.get('diamond_drilling') else '❌ НЕТ'}\n"
        f"{custom_text}\n"
        f"👇 Если всё верно — печатай. Если нет — пиши правку (например: *'убери бурение'*)."
    )


# ================= ХЕНДЛЕРЫ =================

@dp.message(CommandStart())
async def start(message: Message):
    user_orders.pop(message.from_user.id, None)
    await message.answer(
        "👋 **Привет! Я бот-сметчик v3.0.**\n\n"
        "Я знаю весь прайс-лист. Диктуй условия:\n"
        "🗣 *'Иван, Тверь 0.8, песок. Придется таскать песок вручную далеко, метров 15.'*"
    )


@dp.message(F.text)
async def handle_text(message: Message):
    uid = message.from_user.id
    user_text = message.text

    msg = await message.answer("🧠 Думаю...")

    current_data = user_orders.get(uid)
    new_data = analyze_request_ai(user_text, current_data)

    # Удаляем сообщение "Думаю..."
    try:
        await bot.delete_message(message.chat.id, msg.message_id)
    except:
        pass

    if new_data:
        user_orders[uid] = new_data
        await message.answer(format_order_text(new_data), reply_markup=get_keyboard())
    else:
        await message.answer("⚠️ Не понял. Попробуй переформулировать.")


@dp.callback_query()
async def handle_buttons(call: CallbackQuery):
    uid = call.from_user.id
    data = user_orders.get(uid)

    if call.data == "cancel":
        user_orders.pop(uid, None)
        await call.message.edit_text("❌ Заказ сброшен.")

    elif call.data == "print_docs":
        if not data:
            await call.answer("Нет данных.")
            return

        await call.message.edit_text("⏳ Генерирую документы (Смета + Инструкции)...")

        try:
            # 1. КП (Красивое)
            kp_name = f"КП_{data.get('client_name')}.pdf"
            generate_kp(data, kp_name)

            # 2. Смета (Строгая + Инструкции)
            smeta_name = f"Смета_{data.get('client_name')}.pdf"
            generate_strict_estimate(data, smeta_name)

            # 3. Отправка
            media = [
                InputMediaDocument(media=FSInputFile(kp_name), caption="✅ Коммерческое предложение"),
                InputMediaDocument(media=FSInputFile(smeta_name), caption="✅ Смета + Инструкции")
            ]
            await call.message.answer_media_group(media)

            # Чистка
            if os.path.exists(kp_name): os.remove(kp_name)
            if os.path.exists(smeta_name): os.remove(smeta_name)

            user_orders.pop(uid, None)
            await call.message.answer("Готово! Жду следующий заказ.")

        except Exception as e:
            await call.message.answer(f"Ошибка при создании файлов: {e}")


# ================= ЗАПУСК =================
async def main():
    print("Бот v3.0 запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

