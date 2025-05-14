# client/voice_client_entry.py
import sys
import os

# Добавляем корень проекта в PYTHONPATH для корректных импортов внутри пакета client.voice_client
# Предполагается, что voice_client_entry.py находится в client/
# Значит, корень проекта - это на один уровень выше
project_root_runner = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root_runner not in sys.path:
    sys.path.insert(0, project_root_runner) # Вставляем в начало, чтобы имел приоритет

try:
    from client.voice_client.main_loop import run_voice_assistant
except ImportError as e:
    print(f"Критическая ошибка импорта: Не удалось импортировать 'run_voice_assistant' из 'client.voice_client.main_loop'.")
    print(f"Ошибка: {e}")
    print(f"Текущий sys.path: {sys.path}")
    print("Убедитесь, что структура папок верна и __init__.py файлы на месте.")
    sys.exit(1)

if __name__ == "__main__":
    print(f"[Точка входа VC] Запуск голосового ассистента из {__file__}...")
    run_voice_assistant()