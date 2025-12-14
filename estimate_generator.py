# estimate_generator.py
import os
from datetime import datetime
from fpdf import FPDF
from pypdf import PdfWriter, PdfReader  # Библиотека для склейки PDF

# Импортируем базу товаров и услуг
from config import PRODUCTS
from services import PRICE_LIST, get_pipe_service


class StrictEstimatePDF(FPDF):
    def header(self):
        # Строгий заголовок для каждой страницы
        try:
            self.set_font('MyFont', 'B', 12)
        except:
            pass  # Если шрифт еще не загружен
        self.cell(0, 10, 'Смета на выполнение монтажных работ (Приложение №1)', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        try:
            self.set_font('MyFont', '', 8)
        except:
            pass
        self.cell(0, 10, 'Подпись Заказчика: _______________   Подпись Подрядчика: _______________', 0, 0, 'C')


def generate_strict_estimate(data, filename="strict_smeta.pdf"):
    pdf = StrictEstimatePDF()

    # 1. Подключаем русский шрифт (ОБЯЗАТЕЛЬНО)
    font_path = "assets/font.ttf"
    if not os.path.exists(font_path):
        print(f"ОШИБКА: Не найден шрифт {font_path}")
        return None

    pdf.add_font('MyFont', '', font_path, uni=True)
    pdf.add_font('MyFont', 'B', font_path, uni=True)

    pdf.add_page()

    # 2. ШАПКА ДОКУМЕНТА
    pdf.set_font("MyFont", '', 10)
    date_str = datetime.now().strftime("%d.%m.%Y")

    pdf.cell(0, 5, f"Дата составления: {date_str}", 0, 1, 'R')
    pdf.ln(5)

    # Данные клиента
    pdf.set_font("MyFont", 'B', 10)
    pdf.cell(20, 5, "Заказчик:", 0, 0)
    pdf.set_font("MyFont", '', 10)
    pdf.cell(0, 5, data.get('client_name', 'Не указан'), 0, 1)

    pdf.set_font("MyFont", 'B', 10)
    pdf.cell(20, 5, "Адрес:", 0, 0)
    pdf.set_font("MyFont", '', 10)
    pdf.cell(0, 5, data.get('address', 'Не указан'), 0, 1)
    pdf.ln(10)

    # 3. ТАБЛИЦА
    # Настройка колонок: №, Наименование, Ед, Кол, Цена, Сумма
    cols = [10, 100, 15, 20, 25, 25]
    headers = ["№", "Наименование работ / Материалов", "Ед.", "Кол.", "Цена", "Сумма"]

    pdf.set_font("MyFont", 'B', 9)
    pdf.set_fill_color(230, 230, 230)  # Серый фон заголовка

    # Рисуем заголовки
    for i in range(len(headers)):
        pdf.cell(cols[i], 8, headers[i], 1, 0, 'C', True)
    pdf.ln()

    pdf.set_font("MyFont", '', 9)

    # --- СБОР ПОЗИЦИЙ ДЛЯ СМЕТЫ ---
    items = []

    # А) ОСНОВНОЕ ОБОРУДОВАНИЕ (СЕПТИК)
    p_key = data.get('product_id', 'tver_08')
    product = PRODUCTS.get(p_key, PRODUCTS['tver_08'])
    items.append({
        "name": f"Станция очистки {product['name']}",
        "unit": "шт.",
        "qty": 1,
        "price": product['price']
    })

    # Б) МОНТАЖ (БАЗОВЫЙ)
    # Берем цену монтажа из конфига продукта или базовую из services
    montage_price = product.get('montage_price', PRICE_LIST['montage_base']['price'])
    items.append({
        "name": PRICE_LIST['montage_base']['name'],
        "unit": PRICE_LIST['montage_base']['unit'],
        "qty": 1,
        "price": montage_price
    })

    # В) ТРУБОПРОВОД (Умный расчет из services.py)
    soil = data.get('soil', 'sand')
    pipe_len = int(data.get('pipe_length', 5))
    # Выбираем правильную позицию прайса (глина/песок)
    pipe_service = get_pipe_service(soil, 1.0)

    items.append({
        "name": pipe_service['name'],
        "unit": pipe_service['unit'],
        "qty": pipe_len,
        "price": pipe_service['price']
    })

    # Г) ДОСТАВКА
    deliv = PRICE_LIST['delivery_fix']
    items.append({"name": deliv['name'], "unit": deliv['unit'], "qty": 1, "price": deliv['price']})

    # Д) СПЕЦ. РАБОТЫ (Бурение фундамента)
    # Если AI поставил флаг diamond_drilling
    if data.get('diamond_drilling'):
        drl = PRICE_LIST['diamond_drilling_40']
        items.append({"name": drl['name'], "unit": drl['unit'], "qty": 1, "price": drl['price']})

    # Е) ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ (Custom Items от AI)
    # AI может вернуть два типа допов:
    # 1. Из нашего прайс-листа (есть ключ service_key)
    # 2. Произвольный текст (нет ключа, просто name и price)

    if data.get('custom_items'):
        for custom in data['custom_items']:
            service_key = custom.get('service_key')

            # Вариант 1: Услуга из базы services.py
            if service_key and service_key in PRICE_LIST:
                service = PRICE_LIST[service_key]
                items.append({
                    "name": service['name'],
                    "unit": service['unit'],
                    "qty": custom.get('qty', 1),
                    "price": service['price']
                })
            # Вариант 2: Произвольная услуга ("Сломать сарай")
            else:
                items.append({
                    "name": custom.get('name', 'Доп. услуга'),
                    "unit": "шт.",
                    "qty": custom.get('qty', 1),
                    "price": int(custom.get('price', 0))
                })

    # --- ОТРИСОВКА СТРОК ТАБЛИЦЫ ---
    total_sum = 0
    n = 1

    for item in items:
        sum_item = item['price'] * item['qty']
        total_sum += sum_item

        # Хак для красивой отрисовки длинных названий (MultiCell)
        x_start = pdf.get_x()
        y_start = pdf.get_y()

        # 1. Номер
        pdf.cell(cols[0], 6, str(n), "L R", 0, 'C')

        # 2. Название (может быть многострочным)
        pdf.set_xy(x_start + cols[0], y_start)
        pdf.multi_cell(cols[1], 6, item['name'], "L R", 'L')

        # Вычисляем высоту, которую заняло название
        y_end = pdf.get_y()
        h_row = y_end - y_start

        # Возвращаемся наверх рисовать остальные ячейки
        pdf.set_xy(x_start + cols[0] + cols[1], y_start)

        pdf.cell(cols[2], h_row, item['unit'], 1, 0, 'C')
        pdf.cell(cols[3], h_row, str(item['qty']), 1, 0, 'C')
        pdf.cell(cols[4], h_row, str(item['price']), 1, 0, 'R')
        pdf.cell(cols[5], h_row, str(sum_item), 1, 1, 'R')

        # Рисуем нижнюю линию для всей строки
        pdf.set_xy(x_start, y_end)
        pdf.cell(sum(cols), 0, "", "T")

        # Перенос на новую строку
        pdf.set_xy(x_start, y_end)
        n += 1

    # 4. ИТОГО
    pdf.ln(5)
    pdf.set_font("MyFont", 'B', 11)
    pdf.cell(0, 10, f"ИТОГО: {total_sum} руб.", 0, 1, 'R')

    # Сохраняем временный файл (только таблица)
    temp_filename = "temp_" + filename
    pdf.output(temp_filename)

    # === 5. СКЛЕЙКА С ИНСТРУКЦИЯМИ (Appendix) ===
    # Если файла appendix.pdf нет, отдадим просто смету
    appendix_path = "assets/appendix.pdf"

    if os.path.exists(appendix_path):
        try:
            merger = PdfWriter()

            # Добавляем нашу свежую смету
            reader_smeta = PdfReader(temp_filename)
            for page in reader_smeta.pages:
                merger.add_page(page)

            # Добавляем инструкции из файла
            reader_app = PdfReader(appendix_path)
            for page in reader_app.pages:
                merger.add_page(page)

            # Сохраняем итог
            with open(filename, "wb") as f_out:
                merger.write(f_out)

            # Удаляем временный файл
            os.remove(temp_filename)
            return filename

        except Exception as e:
            print(f"Ошибка склейки PDF: {e}")
            return temp_filename  # Возвращаем хотя бы смету
    else:
        print("Внимание: Файл appendix.pdf не найден в папке assets!")
        os.rename(temp_filename, filename)
        return filename

