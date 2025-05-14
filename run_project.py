# run_project.py
import os
import subprocess
import sys
import time  

# Добавляем корень проекта в PYTHONPATH для корректных импортов внутри client.voice_client
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path: 
    sys.path.insert(0, BASE_DIR) 


SERVER_SCRIPT_PATH = os.path.join(BASE_DIR, "server", "all_in_one_server.py")
VOICE_CLIENT_ENTRY_SCRIPT_PATH = os.path.join(BASE_DIR, "client", "voice_client_entry.py")

# Проверяем существование файлов перед запуском
if not os.path.exists(SERVER_SCRIPT_PATH):
    print(f"ОШИБКА: Файл сервера не найден: {SERVER_SCRIPT_PATH}")
    sys.exit(1)
if not os.path.exists(VOICE_CLIENT_ENTRY_SCRIPT_PATH):
    print(f"ОШИБКА: Файл точки входа для голосового клиента не найден: {VOICE_CLIENT_ENTRY_SCRIPT_PATH}")
    print("Пожалуйста, создайте client/voice_client_entry.py или проверьте путь.")
    sys.exit(1)

print("Запускаем сервер...")
# Используем sys.executable, чтобы быть уверенным в использовании того же интерпретатора Python
server_process = subprocess.Popen([sys.executable, SERVER_SCRIPT_PATH])

# Даем серверу немного времени на запуск, особенно для WebSocket
time.sleep(3) # Увеличил для надежности

print("Запускаем голосовой клиент...")
client_process = subprocess.Popen([sys.executable, VOICE_CLIENT_ENTRY_SCRIPT_PATH])

try:
    while True:
        server_poll = server_process.poll()
        client_poll = client_process.poll()

        if server_poll is not None:
            print(f"Сервер неожиданно завершился с кодом {server_poll}.")
            if client_process.poll() is None: # Если клиент еще работает, останавливаем его
                print("Останавливаем клиент...")
                client_process.terminate()
                try: client_process.wait(timeout=3)
                except subprocess.TimeoutExpired: client_process.kill()
            break
        
        if client_poll is not None:
            print(f"Клиент неожиданно завершился с кодом {client_poll}.")
            # Если клиент упал, сервер может продолжать работать.
            # Если нужно остановить и сервер, раскомментируйте следующие строки:
            # if server_process.poll() is None:
            #     print("Останавливаем сервер из-за падения клиента...")
            #     server_process.terminate()
            #     try: server_process.wait(timeout=3)
            #     except subprocess.TimeoutExpired: server_process.kill()
            break
        
        time.sleep(1)

except KeyboardInterrupt:
    print("\nПолучен сигнал KeyboardInterrupt. Останавливаем процессы...")
except Exception as e:
    print(f"Произошла непредвиденная ошибка в скрипте run_project: {e}")
finally:
    print("Завершение работы процессов...")
    if server_process.poll() is None: 
        print("Остановка сервера...")
        server_process.terminate()
        try: server_process.wait(timeout=5) 
        except subprocess.TimeoutExpired:
            print("Сервер не завершился вовремя, принудительное завершение.")
            server_process.kill()
            try: server_process.wait(timeout=3) # Ждем после kill
            except subprocess.TimeoutExpired: print("Сервер не остановился даже после kill.")


    if client_process.poll() is None: 
        print("Остановка клиента...")
        client_process.terminate()
        try: client_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Клиент не завершился вовремя, принудительное завершение.")
            client_process.kill()
            try: client_process.wait(timeout=3)
            except subprocess.TimeoutExpired: print("Клиент не остановился даже после kill.")
            
    print("Процессы остановлены.")