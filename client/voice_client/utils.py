# client/voice_client/utils.py
import os
# Импортируем актуальные значения из config.py
# Предполагается, что config.py был обновлен в voice_client_entry.py ДО того,
# как этот модуль (utils.py) или модули, его использующие, были импортированы.
from .config import TRANSLATION_ENABLED, translator_instance 

# --- Утилитарные функции ---

def speak_utility(text: str):
    """Вспомогательная функция для озвучивания, если прямой импорт speak создает цикл."""
    from .tts_stt import speak as global_speak # Поздний импорт
    global_speak(text)

def validate_height(height_input: str | None) -> int | None:
    """Валидирует рост. Ожидает строку, возвращает int или None."""
    if height_input is None: return None
    try:
        h_int = int(float(height_input.replace(',', '.'))) # Сначала float для "170.0", потом int
    except (ValueError, TypeError):
        # speak_utility(f"Значение '{height_input}' некорректно для роста.") # Озвучивание лучше в вызывающем коде
        return None
    min_h, max_h = 50, 270 # Более реалистичные границы для роста в см
    if not (min_h <= h_int <= max_h):
        # speak_utility(f"Рост {h_int} см кажется нереалистичным. Допустимо от {min_h} до {max_h} см.")
        return None
    return h_int

def validate_weight(weight_input: str | None) -> float | None:
    """Валидирует вес. Ожидает строку, возвращает float или None."""
    if weight_input is None: return None
    try:
        w_float = float(weight_input.replace(',', '.'))
    except (ValueError, TypeError):
        # speak_utility(f"Значение '{weight_input}' некорректно для веса.")
        return None
    min_w, max_w = 10.0, 500.0 # Более реалистичные границы для веса в кг
    if not (min_w <= w_float <= max_w):
        # speak_utility(f"Вес {w_float:.1f} кг кажется нереалистичным. Допустимо от {min_w:.0f} до {max_w:.0f} кг.")
        return None
    return round(w_float, 1)

def validate_age(age_input: str | None) -> int | None:
    """Валидирует возраст. Ожидает строку, возвращает int или None."""
    if age_input is None: return None
    try:
        a_int = int(age_input)
    except (ValueError, TypeError):
        # speak_utility(f"Значение '{age_input}' некорректно для возраста.")
        return None
    min_a, max_a = 1, 130 # Более реалистичные границы для возраста
    if not (min_a <= a_int <= max_a):
        # speak_utility(f"Возраст {a_int} лет кажется нереалистичным. Допустимо от {min_a} до {max_a} лет.")
        return None
    return a_int

def calculate_bmi(weight_kg: float | int | None, height_cm: float | int | None) -> tuple[float, str]:
    """Рассчитывает ИМТ и возвращает значение и категорию."""
    if weight_kg is None or height_cm is None:
        return 0.0, "Вес или рост не указаны."
    if not isinstance(height_cm, (int, float)) or float(height_cm) == 0: # Проверка на float(height_cm)
        return 0.0, "Рост не указан корректно или равен нулю."
    if not isinstance(weight_kg, (int, float)):
        return 0.0, "Вес не указан корректно."

    height_m = float(height_cm) / 100.0
    try:
        bmi = float(weight_kg) / (height_m**2)
    except ZeroDivisionError: # На случай, если height_m каким-то образом стал 0 после проверок
        return 0.0, "Рост не может быть равен нулю при расчете ИМТ."
    
    cats = {
        (0, 16): "Выраженный дефицит массы тела",
        (16, 18.5): "Недостаточная (дефицит) масса тела",
        (18.5, 24.99): "Норма",
        (25, 29.99): "Избыточная масса тела (предожирение)",
        (30, 34.99): "Ожирение 1 степени",
        (35, 39.99): "Ожирение 2 степени",
        (40, float('inf')): "Ожирение 3 степени (морбидное)"
    }
    for (l_bmi, h_bmi), cat_text in cats.items():
        if l_bmi <= bmi < h_bmi:
            return round(bmi, 1), cat_text
    return round(bmi, 1), "Категория ИМТ не определена" # На случай выхода за пределы известных категорий

def translate_text_if_needed(text: str, target_language: str = "ru") -> str:
    """Переводит текст, если перевод включен и необходим."""
    if not TRANSLATION_ENABLED or not text or not translator_instance:
        return text
    if not isinstance(text, str): # Доп. проверка, если вдруг передали не строку
        print(f"[Перевод Utils Warning] Ожидалась строка, получен {type(text)}.")
        return str(text) 

    # Простая эвристика для определения, нужно ли переводить на русский
    if target_language == "ru":
        alpha_chars = [char for char in text if char.isalpha()]
        if not alpha_chars: return text # Строка без букв (числа, символы и т.д.)
        russian_chars_count = sum(1 for char in alpha_chars if 'а' <= char.lower() <= 'я')
        # Если значительная часть текста уже на кириллице, не переводим
        if len(alpha_chars) > 0 and (russian_chars_count / len(alpha_chars) > 0.6):
            return text
            
    try:
        # googletrans может сам обрабатывать длинные тексты, разбивая их.
        # Ограничение длины здесь может быть излишним или даже вредным, если API изменится.
        # text_to_translate = text[:4500] if len(text) > 4500 else text # Ограничение длины (опционально)
        translated = translator_instance.translate(text, dest=target_language)
        return translated.text if translated and translated.text else text
    except Exception as e:
        print(f"[Перевод Ошибка Utils] При переводе текста '{str(text)[:50]}...': {e}")
        return f"{text} (ошибка перевода)" # Возвращаем оригинал с пометкой

def translate_city_for_public_api(city_name_original: str, target_lang: str ="en") -> str:
    """Переводит название города для использования с публичными API."""
    if not city_name_original or not isinstance(city_name_original, str):
        return "Moscow" # Дефолтное значение при некорректном вводе
    
    # Если уже на английском и не содержит кириллицы, не трогаем
    is_cyrillic = any('а' <= char.lower() <= 'я' for char in city_name_original)
    if not is_cyrillic and target_lang.lower() == "en":
        return city_name_original 
        
    translated_city = translate_text_if_needed(city_name_original, target_language=target_lang)
    
    # Опциональная постобработка для английского языка
    if target_lang.lower() == "en" and translated_city != city_name_original:
        # Удаляем общие суффиксы, которые могут добавляться при переводе
        common_suffixes_to_remove = [" City", ", Russia", " Oblast", " Krai", " Republic"]
        for suffix in common_suffixes_to_remove:
            if translated_city.endswith(suffix):
                translated_city = translated_city[:-len(suffix)]
        translated_city = translated_city.strip(", ")
        # print(f"[Перевод Города Utils] '{city_name_original}' -> '{translated_city}' (для API)")
    
    return translated_city

def find_best_match_command(text_input: str, keywords_map: dict[str, str]) -> str | None:
    """Находит наилучшее соответствие команды в словаре ключевых слов."""
    if not text_input or not isinstance(text_input, str): 
        return None
    
    text_input_lower = text_input.lower().strip()
    if not text_input_lower: # Если строка пуста после strip
        return None

    # 1. Точное совпадение
    if text_input_lower in keywords_map: 
        return keywords_map[text_input_lower]
    
    # 2. Частичное совпадение (более длинные ключи имеют приоритет)
    # Ключи в keywords_map должны быть в нижнем регистре для корректной работы
    sorted_keywords = sorted(keywords_map.keys(), key=len, reverse=True)
    
    for keyword_from_map in sorted_keywords:
        # Убедимся, что и ключ из карты приводится к нижнему регистру для сравнения
        if keyword_from_map.lower() in text_input_lower:
            return keywords_map[keyword_from_map] # Возвращаем значение по оригинальному ключу из карты
            
    return None