# pdf_generator.py
import os
from fpdf import FPDF
from config import PRODUCTS, SERVICES


class SepticPDF(FPDF):
    def header(self):
        # 1. Логотип (слева)
        if os.path.exists("assets/logo.png"):
            # x=10, y=8, w=40 (чуть больше, чем раньше)
            self.image("assets/logo.png", 10, 8, 40)

        # 2. Контакты компании (справа вверху)
        # Пробуем установить шрифт, если он уже добавлен
        try:
            self.set_font('MyFont', '', 9)
        except:
            pass

        self.set_text_color(100, 100, 100)  # Серый цвет
        self.set_xy(120, 10)
        # Многострочный блок контактов
        self.multi_cell(80, 4, "Тел: +7(960)879-13-62\nEmail: vlg-septik@yandex.ru\nСайт: www.vlg-septik.ru", align='R')

        # 3. Заголовок документа
        self.set_y(30)
        try:
            self.set_font('MyFont', 'B', 16)
        except:
            pass
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, 'Коммерческое предложение', 0, 1, 'C')
        self.ln(2)

    def footer(self):
        # Номер страницы внизу
        self.set_y(-20)
        try:
            self.set_font('MyFont', 'I', 8)
        except:
            pass
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, 'Страница ' + str(self.page_no()), 0, 0, 'C')


def generate_pdf(data, filename="smeta.pdf"):
    pdf = SepticPDF()

    # === 1. ПОДКЛЮЧЕНИЕ ШРИФТА (КРИТИЧНО) ===
    # Шрифт должен лежать в папке assets/font.ttf
    font_path = "assets/font.ttf"
    if not os.path.exists(font_path):
        print(f"ОШИБКА: Нет шрифта {font_path}")
        return None

    pdf.add_font('MyFont', '', font_path, uni=True)
    pdf.add_font('MyFont', 'B', font_path, uni=True)
    pdf.add_font('MyFont', 'I', font_path, uni=True)

    pdf.add_page()

    # === 2. БЛОК КЛИЕНТА (СЕРЫЙ ФОН) ===
    pdf.set_fill_color(245, 245, 245)  # Очень светло-серый
    # Рисуем прямоугольник-подложку
    pdf.rect(10, pdf.get_y(), 190, 25, 'F')

    pdf.set_xy(15, pdf.get_y() + 5)

    # Строка 1: Заказчик
    pdf.set_font("MyFont", 'B', 10)
    pdf.cell(20, 5, "Заказчик:", 0, 0)
    pdf.set_font("MyFont", '', 10)
    pdf.cell(100, 5, data.get('client_name', 'Не указан'), 0, 1)

    # Строка 2: Адрес
    pdf.set_x(15)
    pdf.set_font("MyFont", 'B', 10)
    pdf.cell(20, 5, "Адрес:", 0, 0)
    pdf.set_font("MyFont", '', 10)
    pdf.cell(100, 5, data.get('address', 'Не указан'), 0, 1)

    # Строка 3: Технические детали
    soil_text = "Глина/Суглинок (Сложный грунт)" if data.get('soil') == 'clay' else "Песок (Стандарт)"
    pdf.set_x(15)
    pdf.cell(100, 5, f"Грунт: {soil_text}  |  Трасса: {data.get('pipe_length')} м", 0, 1)

    pdf.ln(10)  # Отступ после блока клиента

    # === 3. ПРЕЗЕНТАЦИЯ СЕПТИКА (ДВЕ КОЛОНКИ) ===
    # Получаем данные товара
    p_key = data.get('product_id', 'tver_08')
    product = PRODUCTS.get(p_key, PRODUCTS['tver_08'])

    # Заголовок товара (Синий)
    pdf.set_font("MyFont", 'B', 14)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(0, 8, product['name'], 0, 1)

    # Подзаголовок (Маркетинговый)
    pdf.set_font("MyFont", 'I', 10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 6, product.get('marketing_title', 'Надежное решение'), 0, 1)
    pdf.ln(4)

    # Запоминаем Y позицию начала колонок
    y_start = pdf.get_y()

    # --- КОЛОНКА 1 (ЛЕВАЯ): КАРТИНКА ---
    if os.path.exists(product['image']):
        # Рисуем картинку шириной 80 мм
        pdf.image(product['image'], x=10, y=y_start, w=80)

    # --- КОЛОНКА 2 (ПРАВАЯ): ХАРАКТЕРИСТИКИ ---
    # Сдвигаем курсор вправо (x=95)
    pdf.set_xy(95, y_start)

    # Блок "Характеристики"
    pdf.set_font("MyFont", 'B', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 6, "Технические характеристики:", 0, 1)

    pdf.set_font("MyFont", '', 9)
    # Берем список из config.py
    for spec in product.get('specs_list', []):
        pdf.set_x(95)  # Каждый раз возвращаем курсор в правую колонку
        pdf.cell(0, 5, f"- {spec}", 0, 1)

    pdf.ln(3)

    # Блок "Преимущества" (Маркетинг)
    pdf.set_xy(95, pdf.get_y())
    pdf.set_font("MyFont", 'B', 10)
    pdf.cell(0, 6, "Почему выбирают эту модель:", 0, 1)

    pdf.set_font("MyFont", '', 9)
    for feat in product.get('features', []):
        pdf.set_x(95)
        # Используем multi_cell для длинных строк
        pdf.multi_cell(100, 5, feat)

    # Возвращаем курсор ниже самой длинной колонки (картинки или текста) + запас
    pdf.set_y(y_start + 65)

    # === 4. ДЕТАЛЬНАЯ СМЕТА (ТАБЛИЦА) ===
    pdf.set_font("MyFont", 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, "Расчет стоимости под ключ:", 0, 1)

    # Шапка таблицы (Темная)
    pdf.set_font("MyFont", 'B', 9)
    pdf.set_fill_color(50, 50, 50)
    pdf.set_text_color(255, 255, 255)

    # Заголовки колонок
    pdf.cell(110, 8, "Наименование работ и материалов", 1, 0, 'C', True)
    pdf.cell(30, 8, "Цена", 1, 0, 'C', True)
    pdf.cell(20, 8, "Кол-во", 1, 0, 'C', True)
    pdf.cell(30, 8, "Сумма", 1, 1, 'C', True)
    pdf.ln()

    # Сбрасываем цвета для тела таблицы
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("MyFont", '', 10)

    # --- СБОРКА СТРОК СМЕТЫ ---
    items = []

    # 1. Товар
    items.append({
        "name": f"Станция очистки {product['name']}",
        "desc": "Полная комплектация (корпус, крышки, ершовая загрузка).",
        "price": product['price'],
        "qty": 1,
        "total": product['price']
    })

    # 2. Доставка
    items.append({
        "name": "Транспортные расходы",
        "desc": "Доставка оборудования и монтажной бригады до объекта.",
        "price": SERVICES['delivery_fix'],
        "qty": 1,
        "total": SERVICES['delivery_fix']
    })

    # 3. Монтаж (с красивым описанием)
    items.append({
        "name": "Монтаж станции (Стандарт)",
        "desc": SERVICES.get('montage_description', 'Стандартный монтаж'),
        "price": product['montage_price'],
        "qty": 1,
        "total": product['montage_price']
    })

    # 4. Труба (Умный расчет)
    pipe_len = int(data.get('pipe_length', 5))
    if data.get('soil') == 'clay':
        soil_price = SERVICES['clay_price_per_meter']
        soil_desc = "Грунт: Глина/Суглинок (до 1.6м). Копка, укладка, засыпка."
    else:
        soil_price = SERVICES['sand_price_per_meter']
        soil_desc = "Грунт: Песок (до 1м). Копка, укладка, засыпка."

    items.append({
        "name": "Прокладка трубопровода ПВХ 110мм",
        "desc": soil_desc,
        "price": soil_price,
        "qty": f"{pipe_len} м",
        "total": pipe_len * soil_price
    })

    # 5. Бурение (Опционально)
    if data.get('diamond_drilling'):
        items.append({
            "name": "Алмазное бурение фундамента",
            "desc": "Прокол отверстия под 110 трубу (бетон до 40 см).",
            "price": SERVICES['diamond_drilling'],
            "qty": 1,
            "total": SERVICES['diamond_drilling']
        })

    # --- ОТРИСОВКА СТРОК ТАБЛИЦЫ ---
    total_sum = 0

    for item in items:
        # Хитрость: Чтобы нарисовать "Имя" жирным, а "Описание" обычным в одной ячейке,
        # мы рисуем их по очереди, управляя курсором.

        # 1. Запоминаем координаты начала строки
        x_start = pdf.get_x()
        y_start = pdf.get_y()

        # 2. Рисуем Название (Жирным)
        pdf.set_font("MyFont", 'B', 10)
        # border="L R" (только бока), ln=2 (курсор вниз)
        pdf.cell(110, 6, item['name'], "L R", 2)

        # 3. Рисуем Описание (Обычным, серым)
        pdf.set_font("MyFont", '', 8)
        pdf.set_text_color(100, 100, 100)
        # MultiCell сам перенесет строки если длинно
        pdf.multi_cell(110, 4, item['desc'], "L R", 'L')

        # 4. Рисуем нижнюю границу ячейки описания
        pdf.set_text_color(0, 0, 0)  # Черный обратно
        # pdf.cell(110, 1, "", "T") # T = Top border (закрываем низ)

        # 5. Вычисляем высоту получившейся строки (Название + Описание)
        y_end = pdf.get_y()
        row_height = y_end - y_start

        # 6. Возвращаемся наверх вправо, чтобы рисовать Цены
        pdf.set_xy(x_start + 110, y_start)

        # 7. Рисуем Цену, Кол-во, Сумму одной высокой ячейкой
        pdf.set_font("MyFont", '', 10)
        pdf.cell(30, row_height, str(item['price']), 1, 0, 'R')
        pdf.cell(20, row_height, str(item['qty']), 1, 0, 'C')
        pdf.cell(30, row_height, str(item['total']), 1, 1, 'R')

        # 8. Рисуем общую нижнюю линию для всей строки
        pdf.set_xy(x_start, y_end)
        pdf.cell(190, 0, "", "T")

        # 9. Сброс курсора на новую строку
        pdf.set_xy(x_start, y_end)

        total_sum += float(item['total'])

    # === 5. ИТОГО И ВАЖНОЕ ===
    pdf.ln(5)

    # Итоговый блок
    pdf.set_fill_color(230, 255, 230)  # Зеленоватый фон
    pdf.set_font("MyFont", 'B', 14)

    # Текст "ИТОГО"
    pdf.cell(140, 12, "ИТОГО К ОПЛАТЕ:", 0, 0, 'R', True)

    # Сумма (Красным)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(50, 12, f"{int(total_sum)} руб.", 0, 1, 'R', True)

    pdf.ln(10)

    # Блок "Важная информация" (Пугалки для клиента)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("MyFont", 'B', 9)
    pdf.cell(0, 5, "ВАЖНЫЕ УСЛОВИЯ МОНТАЖА:", 0, 1)

    pdf.set_font("MyFont", '', 8)
    notes = (
        "1. Песок (4-5 кубов), вода (2-3 куба) и электричество предоставляются Заказчиком.\n"
        "2. В случае отсутствия условий (нет песка/воды) - взимается штраф за ложный выезд 5000 руб.\n"
        "3. Гарантия на монтажные работы - 1 год. Гарантия на корпус станции - 50 лет.\n"
        "4. При обнаружении скрытых грунтов (плывун, бетонная плита) цена земляных работ может быть пересчитана на месте."
    )
    # Рисуем рамку вокруг условий
    pdf.multi_cell(0, 5, notes, 1, 'L')

    # Сохраняем файл
    pdf.output(filename)
    return filename