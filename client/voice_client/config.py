# client/voice_client/config.py
import os
import sys

# ========================
# Project Root
# ========================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# ========================
# FFmpeg Инициализация и Флаг
# ========================
FFMPEG_DIR = os.path.join(PROJECT_ROOT, "ffmpeg", "bin")
FFMPEG_CONFIGURED_SUCCESSFULLY = False

try:
    from pydub import AudioSegment # type: ignore
    ffmpeg_exe_path = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
    ffprobe_exe_path = os.path.join(FFMPEG_DIR, "ffprobe.exe")

    if os.path.isdir(FFMPEG_DIR) and \
       os.path.isfile(ffmpeg_exe_path) and \
       os.path.isfile(ffprobe_exe_path):
        
        if FFMPEG_DIR not in os.environ.get("PATH", ""): # Проверяем перед добавлением
             os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
        
        AudioSegment.converter = ffmpeg_exe_path
        AudioSegment.ffprobe = ffprobe_exe_path
        FFMPEG_CONFIGURED_SUCCESSFULLY = True
        print(f"[Config FFmpeg] FFmpeg успешно настроен из пути: {FFMPEG_DIR}")
    else:
        print(f"[Config FFmpeg ПРЕДУПРЕЖДЕНИЕ] FFmpeg не найден или некорректно настроен по пути: {FFMPEG_DIR}")
        print(f"  Проверено ffmpeg.exe: {ffmpeg_exe_path} (существует: {os.path.isfile(ffmpeg_exe_path)})")
        print(f"  Проверено ffprobe.exe: {ffprobe_exe_path} (существует: {os.path.isfile(ffprobe_exe_path)})")
except ImportError:
    print("[Config FFmpeg ОШИБКА] Библиотека pydub не найдена. FFmpeg не может быть настроен.")
except Exception as e_ffmpeg_config:
    print(f"[Config FFmpeg ОШИБКА] При настройке FFmpeg: {e_ffmpeg_config}")

# ========================
# API Ключи
# ========================
PUBLIC_WEATHER_API_KEY = os.getenv("PUBLIC_WEATHER_API_KEY", "ВАШ_WEATHERAPI_KEY") # Замените на ваши ключи
PUBLIC_ALPHA_VANTAGE_API_KEY = os.getenv("PUBLIC_ALPHA_VANTAGE_API_KEY", "ВАШ_ALPHAVANTAGE_KEY")
PUBLIC_GRAPH_HOPPER_API_KEY = os.getenv("PUBLIC_GRAPH_HOPPER_API_KEY", "ВАШ_GRAPHHOPPER_KEY")
PUBLIC_OWM_API_KEY = os.getenv("PUBLIC_OWM_API_KEY", "ВАШ_OPENWEATHERMAP_KEY")

# ========================
# URL для ПУБЛИЧНЫХ API
# ========================
PUBLIC_WEATHER_API_CURRENT_URL = "https://api.weatherapi.com/v1/current.json"
PUBLIC_WEATHER_API_FORECAST_URL = "https://api.weatherapi.com/v1/forecast.json"
PUBLIC_OWM_AIR_POLLUTION_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
PUBLIC_OWM_GEOCODING_URL = "http://api.openweathermap.org/geo/1.0/direct"
PUBLIC_ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
PUBLIC_GRAPH_HOPPER_URL = "https://graphhopper.com/api/1/route"
PUBLIC_GRAPH_HOPPER_GEOCODE_URL = "https://graphhopper.com/api/1/geocode"

# ========================
# Пути
# ========================
USERS_DIR = os.path.join(PROJECT_ROOT, "shared", "users")
MUSIC_FOLDER = os.path.join(PROJECT_ROOT, "music")
SERVERS_CONFIG_FILE_VC = os.path.join(PROJECT_ROOT, "servers_config.json")

# ========================
# Константы меню и ключевые слова
# ========================
MENU_TEXT = """
Доступные команды:
- Погода (пог, узнать погоду)
- Тренировка (трен, начать тренировку)
- ИМТ (мой вес, индекс массы тела)
- Цель (моя цель, установить целевой вес)
- Прогресс (мой прогресс)
- Финансовые новости (фин новости, анализ настроений)
- Профиль (информация о профиле, изменить профиль, удалить профиль, новый пользователь)
- Маршрут (получить маршрут)
- Выйти (пока, до свидания)
"""
MENU_KEYWORDS = {
    "погода": "get_weather", "пог": "get_weather", "узнать погоду": "get_weather",
    "тренировка": "start_training", "трен": "start_training", "начать тренировку": "start_training",
    "имт": "show_bmi", "мой вес": "show_bmi", "индекс массы тела": "show_bmi",
    "цель": "set_goal", "моя цель": "set_goal", "установить целевой вес": "set_goal",
    "прогресс": "show_progress", "мой прогресс": "show_progress",
    "финансовые новости": "get_financial_news", "фин новости": "get_financial_news", "анализ настроений": "get_financial_news",
    "профиль": "manage_profile", "мой профиль": "manage_profile", "информация о профиле": "manage_profile", # Добавил "информация о профиле"
    "изменить профиль": "manage_profile", # Пусть manage_profile решает, что делать дальше
    "редактировать профиль": "manage_profile",
    "удалить профиль": "manage_profile",
    "новый пользователь": "manage_profile", "добавить пользователя": "manage_profile", 
    "маршрут": "get_route", "получить маршрут": "get_route",
    "выйти": "exit", "пока": "exit", "до свидания": "exit"
}
# DAYS_MAPPING не используется напрямую в этом файле, но может быть полезен в других модулях
DAYS_MAPPING = {
    "понедельник": 0, "пон":0, "пн":0, "вторник": 1, "вто":1, "вт":1, "среда": 2, "сре":2, "ср":2,
    "четверг": 3, "чет":3, "чт":3, "пятница": 4, "пят":4, "пт":4, "суббота": 5, "суб":5, "сб":5,
    "воскресенье": 6, "вос":6, "вс":6
}
EXERCISES = {
    # Средняя интенсивность
    "прыжки_на_месте_джек": "Прыжки 'Jumping Jacks': Ноги вместе, руки по швам. Прыжком ноги врозь, руки через стороны вверх над головой. Вернуться в и.п.",
    "приседания_классические": "Приседания: Встаньте прямо, ноги на ширине плеч. Присядьте, отводя таз назад, спина прямая. Колени не выходят за носки.",
    "отжимания_классические": "Отжимания от пола: Примите упор лежа, руки чуть шире плеч. Опускайтесь, сгибая локти, затем выпрямляйтесь. Тело прямое.",
    "планка_классическая": "Планка: Упор на предплечья и носки. Тело от макушки до пяток – прямая линия. Напрягите пресс и ягодицы.",
    # Низкая интенсивность
    "приседания_с_опорой_на_стул": "Приседания с опорой: Сядьте на край стула, затем встаньте, минимально опираясь на руки. Повторите.",
    "отжимания_от_стены": "Отжимания от стены: Встаньте лицом к стене, упритесь в нее руками. Сгибайте и разгибайте руки в локтях, приближаясь и отдаляясь от стены.",
    "планка_на_коленях_и_предплечьях": "Планка на коленях и предплечьях: Упор на предплечья и колени. Тело от головы до колен – прямая линия. Напрягите пресс.",
    "отжимания_с_колен": "Отжимания с колен: Примите упор лежа на коленях и руках. Опускайтесь, сгибая локти, затем выпрямляйтесь. Тело прямое от головы до колен.",
    "легкие_выпады_назад": "Легкие выпады назад: Сделайте шаг назад одной ногой, слегка согнув обе ноги в коленях. Вернитесь в и.п. Чередуйте ноги.",
    # Очень низкая интенсивность
    "ходьба_на_месте": "Ходьба на месте: Маршируйте на месте, высоко поднимая колени и активно работая руками.",
    "подъемы_коленей_стоя": "Подъемы коленей стоя: Стоя прямо, поочередно поднимайте согнутые колени к груди. Можно держаться за опору.",
    "вращения_руками": "Вращения руками: Выполняйте круговые движения прямыми или согнутыми руками вперед и назад."
}

# ========================
# Состояние перевода
# ========================
# Эти переменные будут ИЗМЕНЕНЫ при инициализации в voice_client_entry.py или main_loop.py
TRANSLATION_ENABLED = False 
translator_instance = None   # Здесь будет храниться объект googletrans.Translator