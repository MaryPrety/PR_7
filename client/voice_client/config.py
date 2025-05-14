# client/voice_client/config.py
import os
import sys # Нужен для os.pathsep и os.environ

# ========================
# Project Root
# ========================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# ========================
# FFmpeg Инициализация и Флаг
# ========================
FFMPEG_DIR = os.path.join(PROJECT_ROOT, "ffmpeg", "bin") # Путь к директории с ffmpeg.exe и ffprobe.exe
FFMPEG_CONFIGURED_SUCCESSFULLY = False # Изначально False

# Эта логика должна выполняться при импорте модуля config
try:
    from pydub import AudioSegment # type: ignore # pydub нужен для установки путей конвертера

    ffmpeg_exe_path_check = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
    ffprobe_exe_path_check = os.path.join(FFMPEG_DIR, "ffprobe.exe")

    if os.path.isdir(FFMPEG_DIR) and \
       os.path.isfile(ffmpeg_exe_path_check) and \
       os.path.isfile(ffprobe_exe_path_check):
        
        # Добавляем путь к ffmpeg в PATH, если он еще не там
        if FFMPEG_DIR not in os.environ["PATH"]:
             os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
        
        AudioSegment.converter = ffmpeg_exe_path_check # type: ignore
        AudioSegment.ffprobe = ffprobe_exe_path_check # type: ignore
        FFMPEG_CONFIGURED_SUCCESSFULLY = True
        print(f"[Config FFmpeg] FFmpeg успешно настроен из пути: {FFMPEG_DIR}")
    else:
        print(f"[Config FFmpeg ПРЕДУПРЕЖДЕНИЕ] FFmpeg не найден или некорректно настроен по пути: {FFMPEG_DIR}")
        print(f"  Проверено ffmpeg.exe: {ffmpeg_exe_path_check} (существует: {os.path.isfile(ffmpeg_exe_path_check)})")
        print(f"  Проверено ffprobe.exe: {ffprobe_exe_path_check} (существует: {os.path.isfile(ffprobe_exe_path_check)})")

except ImportError:
    print("[Config FFmpeg ОШИБКА] Библиотека pydub не найдена. FFmpeg не может быть настроен.")
except Exception as e_ffmpeg_config:
    print(f"[Config FFmpeg ОШИБКА] При настройке FFmpeg произошла ошибка: {e_ffmpeg_config}")


# ========================
# API Ключи (ДЛЯ ПУБЛИЧНЫХ API)
# ========================
PUBLIC_WEATHER_API_KEY = os.getenv("PUBLIC_WEATHER_API_KEY", "64c49e75848c480995f132927251105") 
PUBLIC_ALPHA_VANTAGE_API_KEY = os.getenv("PUBLIC_ALPHA_VANTAGE_API_KEY", "7BJE0VQWFMV5ZM0E")      
PUBLIC_GRAPH_HOPPER_API_KEY = os.getenv("PUBLIC_GRAPH_HOPPER_API_KEY", "5ea9557f-7f9b-47bf-8b9a-bb3b919961e2")
PUBLIC_OWM_API_KEY = os.getenv("PUBLIC_OWM_API_KEY", "9451997f-980a-4c1b-b1f6-94ffdaed3402") 

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
# Пути к директориям и файлам конфигурации
# ========================
USERS_DIR = os.path.join(PROJECT_ROOT, "shared", "users")
MUSIC_FOLDER = os.path.join(PROJECT_ROOT, "music")
# FFMPEG_DIR уже определен выше
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
    "профиль": "manage_profile", "мой профиль": "manage_profile",
    "изменить профиль": "edit_profile_details", "редактировать профиль": "edit_profile_details",
    "удалить профиль": "delete_profile_interactive",
    "новый пользователь": "add_user_profile", "добавить пользователя": "add_user_profile", 
    "маршрут": "get_route", "получить маршрут": "get_route",
    "выйти": "exit", "пока": "exit", "до свидания": "exit"
}
DAYS_MAPPING = {
    "понедельник": 0, "пон":0, "пн":0, "вторник": 1, "вто":1, "вт":1, "среда": 2, "сре":2, "ср":2,
    "четверг": 3, "чет":3, "чт":3, "пятница": 4, "пят":4, "пт":4, "суббота": 5, "суб":5, "сб":5,
    "воскресенье": 6, "вос":6, "вс":6
}
EXERCISES = {
    "прыжки_на_месте": "Прыжки на месте: Легко подпрыгивайте на носках, имитируя бег на месте. Колени слегка согнуты.",
    "приседания_классические": "Приседания: Встаньте прямо, ноги на ширине плеч. Присядьте, отводя таз назад, спина прямая. Колени не выходят за носки.",
    "отжимания_классические": "Отжимания от пола: Примите упор лежа, руки чуть шире плеч. Опускайтесь, сгибая локти, затем выпрямляйтесь. Тело прямое.",
    "планка_классическая": "Планка: Упор на предплечья и носки. Тело от макушки до пяток – прямая линия. Напрягите пресс и ягодицы.",
    # Упражнения для низкой интенсивности
    "приседания_с_опорой_на_стул": "Приседания с опорой: Сядьте на край стула, затем встаньте, минимально опираясь на руки. Повторите.",
    "отжимания_от_стены": "Отжимания от стены: Встаньте лицом к стене, упритесь в нее руками. Сгибайте и разгибайте руки в локтях, приближаясь и отдаляясь от стены.",
    "планка_на_коленях_и_предплечьях": "Планка на коленях: Упор на предплечья и колени. Тело от головы до колен – прямая линия. Напрягите пресс.",
    "отжимания_с_колен": "Отжимания с колен: Примите упор лежа на коленях и руках. Опускайтесь, сгибая локти, затем выпрямляйтесь. Тело прямое от головы до колен."
}

# ========================
# Состояние перевода (будет инициализировано в tts_stt.py или utils.py при импорте googletrans)
# ========================
TRANSLATION_ENABLED = False 
translator_instance = None   