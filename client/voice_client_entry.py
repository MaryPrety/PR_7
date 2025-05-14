# client/voice_client_entry.py
import sys
import os

# --- Настройка путей для корректных импортов ---
# Предполагаем, что voice_client_entry.py находится в client/voice_client/
# Корень проекта (voice-assistant-blind) будет на два уровня выше.
# Если он в client/, то на один уровень выше.
# Судя по вашему логу: C:\Users\Мария\Desktop\voice-assistant-blind\client\voice_client_entry.py
# значит, он в client/
PROJECT_ROOT_FROM_ENTRY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

if PROJECT_ROOT_FROM_ENTRY not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_FROM_ENTRY)
    print(f"[Entry] Добавлен корень проекта в sys.path: {PROJECT_ROOT_FROM_ENTRY}")

# --- Импорт config ПЕРВЫМ для его последующего изменения ---
try:
    import client.voice_client.config as app_config 
except ImportError as e_cfg:
    print(f"КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА config в 'voice_client_entry.py': {e_cfg}")
    print(f"  Текущий PROJECT_ROOT_FROM_ENTRY: {PROJECT_ROOT_FROM_ENTRY}")
    print(f"  Текущий sys.path: {sys.path}")
    sys.exit(1)

# --- Глобальная инициализация ресурсов ---
def initialize_global_resources():
    """
    Инициализирует глобальные ресурсы, такие как переводчик,
    и обновляет соответствующие флаги/переменные в модуле app_config.
    """
    print("[Entry] Инициализация глобальных ресурсов...")

    # Инициализация Переводчика
    print("[Entry] Попытка инициализации Googletrans...")
    try:
        from googletrans import Translator # type: ignore
        translator = Translator()
        app_config.translator_instance = translator
        app_config.TRANSLATION_ENABLED = True
        print("[Entry] Googletrans успешно инициализирован и настроен в config.py.")
    except ImportError:
        print("[Entry] Библиотека googletrans не найдена. Перевод будет недоступен.")
        # app_config.TRANSLATION_ENABLED и translator_instance остаются False/None (из config.py)
    except Exception as e_trans_init:
        print(f"[Entry] Ошибка при инициализации Googletrans: {e_trans_init}")
        # app_config.TRANSLATION_ENABLED и translator_instance остаются False/None

    # Создание необходимых директорий
    required_dirs = [app_config.USERS_DIR, app_config.MUSIC_FOLDER]
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"[Entry] Директория '{dir_path}' проверена/создана.")
            except OSError as e:
                print(f"[Entry ОШИБКА] Не удалось создать директорию '{dir_path}': {e}")
    
    print("[Entry] Инициализация глобальных ресурсов завершена.")

# --- Основная логика запуска ---
if __name__ == "__main__":
    print(f"--- Запуск Голосового Клиента (Точка входа: {__file__}) ---")

    initialize_global_resources() # Шаг 1: Инициализируем ресурсы, обновляем app_config

    # Шаг 2: Теперь, ПОСЛЕ инициализации, импортируем main_loop
    try:
        from client.voice_client.main_loop import run_voice_assistant
    except ImportError as e_ml:
        print(f"КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА main_loop в 'voice_client_entry.py': {e_ml}")
        print(f"  Это обычно означает, что sys.path настроен неверно или есть циклические импорты, мешающие main_loop.")
        print(f"  Текущий sys.path: {sys.path}")
        sys.exit(1)
        
    print(f"[Entry] Запуск основного цикла голосового ассистента...")
    try:
        run_voice_assistant()
    except Exception as e_main_run:
        print(f"[Entry КРИТИЧЕСКАЯ ОШИБКА] Необработанное исключение в run_voice_assistant: {e_main_run}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"--- Голосовой Клиент Завершил Работу (Точка входа: {__file__}) ---")