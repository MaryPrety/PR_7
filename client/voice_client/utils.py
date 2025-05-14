# client/voice_client/utils.py
import os
from .config import TRANSLATION_ENABLED, translator_instance as global_translator_instance

# Если googletrans установлен, инициализируем его здесь
if not TRANSLATION_ENABLED: # Попытка инициализации, если еще не было
    try:
        from googletrans import Translator # type: ignore
        translator_local = Translator() # Используем локальную переменную для проверки
        if translator_local: # Проверка, что объект создался
            # Обновляем глобальные переменные в config, если они оттуда импортируются и используются напрямую,
            # или лучше передавать translator_instance в функции, которые его используют.
            # Для простоты, здесь обновим, если config это позволяет (не лучшая практика).
            # import client.voice_client.config as cfg # Не очень хорошо изменять так
            # cfg.TRANSLATION_ENABLED = True
            # cfg.translator_instance = translator_local
            # Вместо этого, функции, которым нужен перевод, будут импортировать его из config
            # А config.TRANSLATION_ENABLED будет true если импорт удался в tts_stt.py или здесь
            print("[Utils] Googletrans инициализирован в utils.")
            # Этот модуль будет использовать global_translator_instance из config
    except ImportError:
        print("[Utils] Googletrans не найден в utils, перевод недоступен.")
        pass # Оставляем TRANSLATION_ENABLED и translator_instance как они были в config


def validate_height(h: int | None) -> int:
    return 170 if h is None else (170 if not (100 <= h <= 250) else h)

def validate_weight(w: int | None) -> int:
    return 60 if w is None else (60 if not (20 <= w <= 300) else w)

def validate_age(a: int | None) -> int:
    return 30 if a is None else (30 if not (5 <= a <= 120) else a)

def calculate_bmi(weight_kg: float | int, height_cm: float | int) -> tuple[float, str]:
    if not height_cm or height_cm == 0:
        return 0.0, "Рост не указан или равен нулю."
    height_m = float(height_cm) / 100.0
    try:
        bmi = float(weight_kg) / (height_m**2)
    except ZeroDivisionError:
        return 0.0, "Рост не может быть равен нулю."
    
    cats = {
        (0, 16): "Выраженный дефицит массы тела",
        (16, 18.5): "Дефицит массы тела",
        (18.5, 25): "Норма",
        (25, 30): "Избыточная масса тела (предожирение)",
        (30, 35): "Ожирение 1 степени",
        (35, 40): "Ожирение 2 степени",
        (40, float('inf')): "Ожирение 3 степени (морбидное)"
    }
    for (l_bmi, h_bmi), cat_text in cats.items():
        if l_bmi <= bmi < h_bmi:
            return bmi, cat_text
    return bmi, "Категория ИМТ не определена"


def translate_text_if_needed(text: str, target_language: str = "ru") -> str:
    # Используем глобальный instance из config, который должен быть инициализирован в tts_stt.py
    from .config import TRANSLATION_ENABLED as TC_ENABLED, translator_instance as TC_INSTANCE 
    # Переименовал, чтобы не конфликтовать с локальными переменными модуля, если они есть
    
    if not TC_ENABLED or not text or not TC_INSTANCE:
        return text
    
    # Простая проверка на то, является ли текст уже целевым языком (если это русский)
    if target_language == "ru":
        alpha_chars = [char for char in text if char.isalpha()]
        if not alpha_chars: return text # Строка без букв
        russian_chars_count = sum(1 for char in alpha_chars if 'а' <= char.lower() <= 'я')
        # Если более 60% букв русские, считаем, что текст уже на русском
        if len(alpha_chars) > 0 and (russian_chars_count / len(alpha_chars) > 0.6):
            return text
    try:
        translated = TC_INSTANCE.translate(text, dest=target_language)
        return translated.text if translated and translated.text else text
    except Exception as e:
        print(f"[Перевод] Ошибка перевода текста '{text[:30]}...': {e}")
        return f"{text} (перевод не удался)"

def translate_city_for_public_api(city_name_original: str, target_lang: str ="en") -> str:
    """Переводит название города для использования с ПУБЛИЧНЫМИ API, если это необходимо."""
    # Используем translate_text_if_needed, который в свою очередь использует глобальный TC_INSTANCE
    # Нет нужды проверять TC_ENABLED снова, это сделает translate_text_if_needed
    
    # Некоторые API лучше понимают английские названия
    # Если язык уже английский и нет кириллицы, или перевод не нужен/невозможен, вернем оригинал
    is_cyrillic = any('а' <= char.lower() <= 'я' for char in city_name_original)
    if not is_cyrillic and target_lang == "en":
        return city_name_original # Уже не кириллица, для en API скорее всего подойдет

    translated = translate_text_if_needed(city_name_original, target_language=target_lang)
    if translated != city_name_original: # Если перевод что-то изменил
         print(f"[Перевод Города для Публ. API] '{city_name_original}' -> '{translated}'")
    return translated

def find_best_match_command(text_input: str, keywords_map: dict) -> str | None:
    if not text_input: 
        return None
    text_input_lower = text_input.lower()
    
    if text_input_lower in keywords_map: 
        return keywords_map[text_input_lower]
    
    # Сортируем ключи по длине (от самого длинного) для более точного частичного совпадения
    sorted_keywords = sorted(keywords_map.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword in text_input_lower: # Проверяем, содержится ли ключ в введенном тексте
            return keywords_map[keyword]
    return None

# Глобальные переменные для приватных серверов (загружаются в main_loop.py)
loaded_servers_vc: dict = {}          
active_server_config_vc: dict | None = None  
active_session_id_vc: str | None = None   