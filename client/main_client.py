# client/main_client.py

import socket
import json
import asyncio
import websockets # type: ignore
import sys
import os
import difflib
import uuid # Для типизации session_id, хотя клиент его не генерирует
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable # Для типизации

# ========================
# Добавляем корень проекта в PYTHONPATH (если нужно для shared)
# ========================
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# ========================
# Конфигурация и глобальные переменные
# ========================
SERVERS_CONFIG_FILE_PATH = os.path.join(project_root, "servers_config.json")
servers: dict = {}
current_server_name: str | None = None
current_session_id: str | None = None # Управляется сервером

CLIENT_EVENT_CACHE_FILE = os.path.join(project_root, "client_event_cache.json")
MAX_CLIENT_CACHE_SIZE = 100 # Макс. событий в кэше клиента
CLIENT_CACHE_EXPIRY_DAYS = 7 # Дней до устаревания события в кэше

ws_listener_thread: threading.Thread | None = None # Поток для WebSocket
ws_listener_task: asyncio.Task | None = None       # Задача asyncio внутри потока
ws_stop_event = asyncio.Event()                     # Событие для остановки WebSocket

# ========================
# Локальный кэш событий клиента (Пункт 6 ТЗ)
# ========================
def load_client_cache() -> list:
    if not os.path.exists(CLIENT_EVENT_CACHE_FILE):
        return []
    try:
        with open(CLIENT_EVENT_CACHE_FILE, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            valid_cache = []
            now = datetime.now()
            for event in cache_data:
                event_time_str = event.get("timestamp_client_received")
                if event_time_str:
                    try:
                        event_time = datetime.fromisoformat(event_time_str)
                        if now - event_time <= timedelta(days=CLIENT_CACHE_EXPIRY_DAYS):
                            valid_cache.append(event)
                    except ValueError: pass # Игнорируем события с неверным timestamp
            return valid_cache
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Кэш Клиента Ошибка] Загрузка: {e}")
        return []

def save_client_cache(cache_data: list):
    try:
        # Убедимся, что директория для кэша существует
        cache_dir = os.path.dirname(CLIENT_EVENT_CACHE_FILE)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            
        with open(CLIENT_EVENT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[Кэш Клиента Ошибка] Сохранение: {e}")

def add_event_to_client_cache(event_type: str, event_content: Any, source: str = "unknown"):
    """Добавляет событие в локальный кэш клиента."""
    cache = load_client_cache()
    new_event = {
        "type": event_type,
        "source": source,
        "content": event_content,
        "timestamp_client_received": datetime.now().isoformat() # Время получения события клиентом
    }
    cache.insert(0, new_event) # Новые события добавляются в начало списка
    if len(cache) > MAX_CLIENT_CACHE_SIZE:
        cache = cache[:MAX_CLIENT_CACHE_SIZE] # Ограничиваем размер кэша
    save_client_cache(cache)
    # print(f"[Кэш Клиента] Событие '{event_type}' от '{source}' добавлено.") # Для отладки

def show_event_history():
    print("\n--- История последних событий (локальный кэш клиента) ---")
    # Загружаем последние N событий, они уже отсортированы (новые в начале)
    cache = load_client_cache()[:15] # Показываем, например, последние 15
    if not cache:
        print("История событий пуста.")
        return
    
    # Выводим в обратном порядке, чтобы старые были наверху, новые внизу (хронологически)
    for i, event in enumerate(reversed(cache)):
        ts_str = event.get('timestamp_client_received', 'N/A')
        try:
            # Форматируем дату и время для красивого вывода
            ts_dt = datetime.fromisoformat(ts_str)
            formatted_ts = ts_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            formatted_ts = ts_str # Если формат неверный, выводим как есть

        print(f"{i+1}. [{formatted_ts}] Тип: {event.get('type', 'N/A')}, Источник: {event.get('source', 'N/A')}")
        content = event.get('content', {})
        if isinstance(content, dict):
            print(f"   Содержание: {json.dumps(content, indent=2, ensure_ascii=False)}")
        elif isinstance(content, str) and len(content) > 200: # Обрезаем слишком длинные строки
             print(f"   Содержание: {content[:200]}...")
        else:
            print(f"   Содержание: {content}")
        print("-" * 30)

# ========================
# Функции управления конфигурацией серверов (Пункт 3 ТЗ)
# ========================
def load_servers_config():
    global servers, current_server_name
    # ... (код этой и следующих функций управления серверами такой же, как вы предоставили)
    config_dir = os.path.dirname(SERVERS_CONFIG_FILE_PATH)
    if config_dir and not os.path.exists(config_dir):
        try: os.makedirs(config_dir); print(f"Создана директория для конфигурации: {config_dir}")
        except OSError as e:
            print(f"Не удалось создать директорию {config_dir}: {e}. Используется конфигурация по умолчанию.")
            servers = {"default": {"ip": "127.0.0.1", "tcp_port": 5000, "ws_port": 8765, "udp_port": 5002}}
            current_server_name = "default" if "default" in servers else None
            return
    if os.path.exists(SERVERS_CONFIG_FILE_PATH):
        try:
            with open(SERVERS_CONFIG_FILE_PATH, "r", encoding="utf-8") as f: servers = json.load(f)
            if not servers: servers = {"default": {"ip": "127.0.0.1", "tcp_port": 5000, "ws_port": 8765, "udp_port": 5002}}; save_servers_config()
        except (json.JSONDecodeError, IOError) as e:
            print(f"Ошибка загрузки конфигурации: {e}. Используется по умолчанию."); servers = {"default": {"ip": "127.0.0.1", "tcp_port": 5000, "ws_port": 8765, "udp_port": 5002}}
    else:
        print(f"Файл конфигурации не найден. Используется по умолчанию."); servers = {"default": {"ip": "127.0.0.1", "tcp_port": 5000, "ws_port": 8765, "udp_port": 5002}}; save_servers_config()
    if not current_server_name and servers: current_server_name = list(servers.keys())[0]
    elif current_server_name and current_server_name not in servers: current_server_name = list(servers.keys())[0] if servers else None

def save_servers_config():
    config_dir = os.path.dirname(SERVERS_CONFIG_FILE_PATH)
    if config_dir and not os.path.exists(config_dir):
        try: os.makedirs(config_dir)
        except OSError as e: print(f"Не удалось создать директорию {config_dir}: {e}. Не сохранено."); return False
    try:
        with open(SERVERS_CONFIG_FILE_PATH, "w", encoding="utf-8") as f: json.dump(servers, f, indent=4, ensure_ascii=False)
        print(f"Конфигурации серверов сохранены.")
        return True
    except IOError as e: print(f"Ошибка сохранения конфигурации: {e}"); return False

def add_server_interactive():
    global servers
    print("--- Добавление нового сервера ---"); s_name = input("Имя сервера: ").strip()
    if not s_name: print("Имя не может быть пустым."); return
    if s_name in servers: print(f"Сервер '{s_name}' уже существует."); return
    s_ip = input(f"IP-адрес '{s_name}': ").strip()
    if not s_ip: print("IP-адрес не может быть пустым."); return
    try:
        s_tcp_port = int(input(f"TCP порт '{s_name}': ").strip())
        s_ws_port_str = input(f"WebSocket порт (Enter для {s_tcp_port + 3765}): ").strip()
        s_ws_port = int(s_ws_port_str) if s_ws_port_str else s_tcp_port + 3765
        s_udp_port_str = input(f"UDP порт (Enter для {s_tcp_port + 2}): ").strip()
        s_udp_port = int(s_udp_port_str) if s_udp_port_str else s_tcp_port + 2
        servers[s_name] = {"ip": s_ip, "tcp_port": s_tcp_port, "ws_port": s_ws_port, "udp_port": s_udp_port}
        if save_servers_config(): print(f"Сервер '{s_name}' добавлен.")
        else: print(f"Сервер '{s_name}' добавлен в сессию, но не сохранен в файл.")
    except ValueError as ve: print(f"Ошибка ввода: {ve}. Отмена.")
    except Exception as e: print(f"Ошибка добавления сервера: {e}")

def remove_server_interactive():
    global servers, current_server_name, current_session_id
    if not servers: print("Нет серверов для удаления."); return
    print("--- Удаление сервера ---"); server_names = list(servers.keys())
    for i, name in enumerate(server_names): print(f"{i+1}. {name}")
    choice_str = input(f"Номер или имя сервера для удаления (или 'отмена'): ").strip()
    if choice_str.lower() == 'отмена': print("Удаление отменено."); return
    server_to_remove_name = None
    if choice_str.isdigit():
        try: idx = int(choice_str) - 1; server_to_remove_name = server_names[idx] if 0 <= idx < len(server_names) else None
        except ValueError: pass
    if not server_to_remove_name and choice_str in servers: server_to_remove_name = choice_str
    if server_to_remove_name:
        if input(f"Удалить '{server_to_remove_name}'? (да/нет): ").strip().lower() == 'да':
            if servers.pop(server_to_remove_name, None):
                if save_servers_config(): print(f"Сервер '{server_to_remove_name}' удален.")
                else: print(f"Сервер '{server_to_remove_name}' удален из сессии, файл не обновлен.")
                if current_server_name == server_to_remove_name:
                    stop_ws_listener_sync() # Останавливаем WS, если он был для удаляемого сервера
                    current_server_name = None; current_session_id = None; print("Текущий сервер удален.")
                if servers and not current_server_name: select_server() # Предлагаем выбрать новый
                elif not servers: print("Все серверы удалены.")
            else: print(f"Сервер '{server_to_remove_name}' не найден.")
        else: print("Удаление отменено.")
    else: print(f"Сервер '{choice_str}' не найден.")

def select_server():
    global current_server_name, current_session_id, servers
    if not servers: print("Список серверов пуст. Добавьте сервер ('добавить сервер')."); return
    print("Доступные серверы:"); server_names_list = list(servers.keys())
    for i, name in enumerate(server_names_list): s_conf = servers[name]; print(f"{i+1}. {name} ({s_conf.get('ip','N/A')}:{s_conf.get('tcp_port','N/A')})")
    while True:
        choice = input(f"Выберите сервер (1-{len(server_names_list)}) или имя: ").strip(); chosen_name = None
        if choice.isdigit():
            try: idx = int(choice) - 1; chosen_name = server_names_list[idx] if 0 <= idx < len(server_names_list) else None
            except ValueError: pass
        if not chosen_name and choice in servers: chosen_name = choice
        elif not chosen_name:
            matches = difflib.get_close_matches(choice, server_names_list, n=1, cutoff=0.6)
            if matches and input(f"Вы имели в виду '{matches[0]}'? (y/n): ").lower() == 'y': chosen_name = matches[0]
        if chosen_name:
            if current_server_name != chosen_name:
                print(f"Смена сервера с '{current_server_name}' на '{chosen_name}'. Сессия сброшена.")
                stop_ws_listener_sync() # Останавливаем WS слушатель перед сменой сервера
                current_session_id = None
            current_server_name = chosen_name; s_conf = servers[current_server_name]
            print(f"Текущий сервер: {current_server_name} ({s_conf.get('ip','N/A')}:{s_conf.get('tcp_port','N/A')})")
            # Можно автоматически запускать WS слушатель для нового сервера
            # start_ws_listener_thread()
            return
        else: print("Сервер не найден. Попробуйте снова.")

# ========================
# TCP: Отправка данных (Пункт 3 ТЗ)
# ========================
def send_profile_interactive():
    # ... (код без изменений, как в вашем файле, но вызывает send_tcp_message) ...
    global current_session_id
    if not current_server_name or current_server_name not in servers: print("Сначала выберите сервер ('выбрать сервер')."); return
    config = servers[current_server_name]; name = input("Имя профиля: ").strip(); age_str = input("Возраст: ").strip()
    try:
        age = int(age_str) if age_str.isdigit() else 0
        profile_data = {"action": "update_profile", "name": name, "age": age}
        if current_session_id: profile_data["session_id"] = current_session_id
        response_data = send_tcp_message(config["ip"], config["tcp_port"], profile_data)
        if response_data: add_event_to_client_cache("tcp_response", response_data, f"TCP_to:{config['ip']}:{config['tcp_port']}")
    except ValueError: print("Возраст должен быть числом.")
    except Exception as e: print(f"Ошибка подготовки данных профиля: {e}")

def send_tcp_message(ip: str, port: int, payload_dict: dict) -> dict | None:
    # ... (код без изменений, как в вашем файле) ...
    global current_session_id
    print(f"TCP: Попытка -> {ip}:{port}, Payload: {payload_dict}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10); s.connect((ip, port)); s.sendall(json.dumps(payload_dict).encode('utf-8'))
            response_bytes = s.recv(4096)
            if not response_bytes: print("TCP: Сервер закрыл соединение без ответа."); return None
            response_str = response_bytes.decode('utf-8')
            try:
                response_data = json.loads(response_str); print("TCP: Ответ сервера (JSON):", response_data)
                if response_data.get("status") == "success" and "session_id" in response_data:
                    new_session_id = response_data["session_id"]
                    if current_session_id != new_session_id: current_session_id = new_session_id; print(f"TCP: Сессия установлена/обновлена. SID: {current_session_id}")
                elif "message" in response_data: print(f"TCP: Сообщение от сервера: {response_data['message']}")
                return response_data
            except json.JSONDecodeError: print(f"TCP: Ответ не JSON: '{response_str}'"); return {"raw_response": response_str}
    except socket.timeout: print(f"TCP: Таймаут {ip}:{port}."); return None
    except ConnectionRefusedError: print(f"TCP: Отказ в соединении с {ip}:{port}."); return None
    except Exception as e: print(f"TCP: Общая ошибка {ip}:{port}: {e}"); return None


# ========================
# WebSocket: Подписка на события (Пункт 4 и 7 ТЗ)
# ========================
async def websocket_listener_logic(uri: str, ws_port_for_log: int):
    # ... (код без изменений, как в моем предыдущем полном ответе client/main_client.py) ...
    global ws_stop_event
    ws_stop_event.clear()
    print(f"WS: Попытка подключения к {uri} (порт {ws_port_for_log})..."); add_event_to_client_cache("websocket_attempt", {"uri": uri}, "client")
    try:
        async with websockets.connect(uri, open_timeout=10, close_timeout=5, ping_interval=20, ping_timeout=15) as websocket: # type: ignore
            print(f"WS: Успешно подключено к {uri}. Ожидание событий..."); add_event_to_client_cache("websocket_connect", {"uri": uri, "status": "connected"}, "client")
            if current_session_id: await websocket.send(json.dumps({"action": "ws_identify", "session_id": current_session_id}))
            while not ws_stop_event.is_set():
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    try:
                        data = json.loads(message); print("\nWS: << Получено событие от сервера >>")
                        if data.get("type") == "day_event": print(f"  Событие дня: {data.get('event_name', 'N/A')}\n  Описание: {data.get('description', 'N/A')}"); add_event_to_client_cache("day_event", data, uri)
                        elif data.get("type") == "data_update": print(f"  Обновление данных: {data.get('source', 'N/A')}\n  Содержание: {data.get('content', {})}"); add_event_to_client_cache("data_update", data, uri)
                        else: print(f"  Неизвестный тип: {data.get('type')}\n  Данные: {data}"); add_event_to_client_cache("unknown_ws_message", data, uri)
                        print("-" * 30)
                    except json.JSONDecodeError: print(f"WS: Получено не JSON: {message[:200]}"); add_event_to_client_cache("invalid_ws_json", {"raw_message": message[:200]}, uri)
                except asyncio.TimeoutError: continue
                except websockets.ConnectionClosedOK: print("WS: Соединение закрыто сервером (OK)."); break # type: ignore
                except websockets.ConnectionClosedError as cc_err: print(f"WS: Соединение закрыто с ошибкой: {cc_err}"); break # type: ignore
                except Exception as e_recv: print(f"WS: Ошибка приема/обработки: {e_recv}"); break
            print("WS: Цикл слушателя завершен (событие остановки).")
    except (websockets.exceptions.InvalidURI, ConnectionRefusedError, socket.gaierror, OSError, asyncio.TimeoutError) as e_conn: # type: ignore
        print(f"WS: Не удалось подключиться/поддерживать соединение с {uri}: {e_conn}"); add_event_to_client_cache("websocket_connect_fail", {"uri": uri, "error": str(e_conn)}, "client")
    except Exception as e_outer: print(f"WS: Внешняя ошибка слушателя: {e_outer}")
    finally: print(f"WS: Слушатель для {uri} остановлен."); add_event_to_client_cache("websocket_disconnect", {"uri": uri, "status": "stopped"}, "client")

async def run_websocket_listener_async_wrapper(uri: str, port: int):
    # ... (код без изменений) ...
    try: await websocket_listener_logic(uri, port)
    except asyncio.CancelledError: print("WS: Задача слушателя отменена.")


def start_ws_listener_thread():
    # ... (код без изменений, как в моем предыдущем полном ответе client/main_client.py) ...
    global ws_listener_task, ws_stop_event, ws_listener_thread
    if not current_server_name or current_server_name not in servers: print("Сначала выберите сервер."); return
    if ws_listener_thread and ws_listener_thread.is_alive(): print("WS: Слушатель уже активен."); return
    config = servers[current_server_name]; ws_uri = f"ws://{config['ip']}:{config['ws_port']}"
    print(f"--- Запуск WS Listener для {current_server_name} в потоке ---"); ws_stop_event = asyncio.Event()
    def run_loop_in_thread():
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        try:
            global ws_listener_task; ws_listener_task = loop.create_task(run_websocket_listener_async_wrapper(ws_uri, config['ws_port']))
            loop.run_until_complete(ws_listener_task)
        except KeyboardInterrupt: print("WS Thread: KeyboardInterrupt..."); ws_stop_event.set()
        except Exception as e: print(f"WS Thread: Ошибка в цикле: {e}")
        finally: loop.close(); print("WS Thread: Цикл asyncio остановлен.")
    ws_listener_thread = threading.Thread(target=run_loop_in_thread, daemon=True); ws_listener_thread.start()
    print("WS: Слушатель запущен в фоне. ('стоп ws' для остановки).")

def stop_ws_listener_sync():
    # ... (код без изменений, как в моем предыдущем полном ответе client/main_client.py) ...
    global ws_listener_task, ws_stop_event, ws_listener_thread
    if not ws_listener_thread or not ws_listener_thread.is_alive(): print("WS: Слушатель не активен."); ws_listener_task = None; ws_listener_thread = None; return
    print("WS: Попытка остановки слушателя WebSocket..."); ws_stop_event.set()
    ws_listener_thread.join(timeout=3.0) # Ждем завершения потока
    if ws_listener_thread.is_alive(): print("WS: Поток слушателя не завершился в таймаут.")
    else: print("WS: Поток слушателя WebSocket остановлен.")
    ws_listener_task = None; ws_listener_thread = None


# ========================
# UDP: Отправка геолокации (Пункт 5 ТЗ)
# ========================
def send_location_interactive():
    # ... (код без изменений, как в вашем файле, но вызывает send_udp_message) ...
    if not current_server_name or current_server_name not in servers: print("Сначала выберите сервер."); return
    lat_str = input("Широта (55.75): ").strip(); lon_str = input("Долгота (37.61): ").strip()
    try:
        lat = float(lat_str); lon = float(lon_str)
        location_data = {"latitude": lat, "longitude": lon, "action": "location_update"}
        if current_session_id: location_data["session_id"] = current_session_id
        print(f"Отправка геолокации: {location_data}")
        response = send_udp_message(location_data)
        if response: add_event_to_client_cache("udp_response", response, f"UDP_to:{servers[current_server_name]['ip']}:{servers[current_server_name]['udp_port']}")
    except ValueError: print("Ошибка: широта и долгота должны быть числами.")
    except Exception as e: print(f"Ошибка подготовки геолокации: {e}")

def send_udp_message(payload_dict: dict) -> dict | None:
    # ... (код без изменений, как в вашем файле) ...
    if not current_server_name: print("UDP: Сервер не выбран."); return None # Добавил проверку
    config = servers[current_server_name]; UDP_SERVER_ADDR = (config["ip"], config["udp_port"])
    # print(f"UDP: Отправка на {UDP_SERVER_ADDR}, payload: {payload_dict}") # Можно раскомментировать для детальной отладки
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5)
        try:
            sock.sendto(json.dumps(payload_dict).encode('utf-8'), UDP_SERVER_ADDR)
            data_bytes, server_addr_from = sock.recvfrom(1024)
            response_data = json.loads(data_bytes.decode('utf-8')); print(f"UDP: Ответ от {server_addr_from}:", response_data)
            return response_data
        except socket.timeout: print(f"UDP: Сервер {UDP_SERVER_ADDR} не ответил."); return None
        except ConnectionRefusedError: print(f"UDP: Отказ в соединении {UDP_SERVER_ADDR}."); return None
        except Exception as e: print(f"UDP: Ошибка: {e}"); return None

# ========================
# Основной цикл и команды
# ========================
COMMAND_ACTIONS = {
    "отправить профиль": send_profile_interactive,
    "слушать ws": start_ws_listener_thread,
    "стоп ws": stop_ws_listener_sync,
    "отправить геолокацию": send_location_interactive,
    "выбрать сервер": select_server,
    "добавить сервер": add_server_interactive,
    "удалить сервер": remove_server_interactive,
    "показать сервер": lambda: print(f"Текущий сервер: {current_server_name} (IP: {servers.get(current_server_name,{}).get('ip','N/A')}, TCP: {servers.get(current_server_name,{}).get('tcp_port','N/A')}), SID: {current_session_id or 'не установлен'}" if current_server_name else "Сервер не выбран."),
    "показать историю": show_event_history,
    "выход": lambda: sys.exit("Программа завершена.")
}
AVAILABLE_COMMANDS_TEXT = list(COMMAND_ACTIONS.keys())

def process_command(user_input_str: str):
    # ... (код без изменений, как в вашем файле) ...
    user_input_str = user_input_str.strip().lower()
    if not user_input_str: return
    matched_command_text = None
    if user_input_str.isdigit():
        try: cmd_index = int(user_input_str) - 1
        except ValueError: print("Неверный номер команды."); return
        if 0 <= cmd_index < len(AVAILABLE_COMMANDS_TEXT): matched_command_text = AVAILABLE_COMMANDS_TEXT[cmd_index]
        else: print("Неверный номер команды."); return
    if not matched_command_text:
        matches = difflib.get_close_matches(user_input_str, AVAILABLE_COMMANDS_TEXT, n=1, cutoff=0.5)
        if matches: matched_command_text = matches[0]
        else:
            potential_matches = []
            input_words = user_input_str.split()
            for cmd_key_original_case in AVAILABLE_COMMANDS_TEXT:
                cmd_key_lower = cmd_key_original_case.lower()
                all_input_words_in_key = all(word in cmd_key_lower for word in input_words)
                is_single_word_substring = (len(input_words) == 1 and input_words[0] in cmd_key_lower)
                if all_input_words_in_key or is_single_word_substring: potential_matches.append(cmd_key_original_case)
            if len(potential_matches) == 1: matched_command_text = potential_matches[0]
            elif len(potential_matches) > 1: print("Найдено несколько команд, уточните:"); [print(f"  {i+1}. {pm.capitalize()}") for i, pm in enumerate(potential_matches)]; return
    if matched_command_text:
        print(f"\n--- Выполняется: {matched_command_text.capitalize()} ---")
        action_function = COMMAND_ACTIONS[matched_command_text]
        try: action_function()
        except Exception as e_action: print(f"Ошибка при выполнении команды '{matched_command_text}': {e_action}"); import traceback; traceback.print_exc()
    elif user_input_str: print(f"Команда '{user_input_str}' не распознана.")

def main_loop():
    print("Клиент для тестирования сетевого взаимодействия запущен.")
    print("Введите 'помощь' для списка команд или 'выход' для завершения.")
    while True:
        print("\n----- Главное меню (Сетевой клиент) -----")
        if current_server_name and current_server_name in servers:
            s_conf = servers[current_server_name]
            ws_status = "активен" if ws_listener_thread and ws_listener_thread.is_alive() else "не активен"
            print(f"Текущий сервер: {current_server_name} (IP: {s_conf.get('ip','N/A')}, TCP: {s_conf.get('tcp_port','N/A')}), SID: {current_session_id or 'не установлен'}, WS: {ws_status}")
        else: print("Сервер не выбран.")
        print("Доступные действия:")
        for i, cmd_text in enumerate(AVAILABLE_COMMANDS_TEXT): print(f"  {i+1}. {cmd_text.capitalize()}")
        try:
            user_input = input("Введите команду или её номер: ").strip()
            if user_input.lower() in ["помощь", "help", "h", "?"]: continue
            process_command(user_input)
        except EOFError: # Обработка Ctrl+D в некоторых терминалах
            print("\nПолучен EOF. Завершение работы...")
            break
        except KeyboardInterrupt: # Обработка Ctrl+C в цикле ввода
            print("\nПолучен сигнал прерывания. Для выхода введите 'выход'.")


if __name__ == "__main__":
    load_servers_config()
    if not current_server_name and servers: current_server_name = list(servers.keys())[0]
    elif current_server_name and current_server_name not in servers: current_server_name = list(servers.keys())[0] if servers else None
    
    try:
        main_loop()
    except KeyboardInterrupt: print("\nКлиент завершает работу (основной Ctrl+C)...")
    except Exception as e_main: print(f"Критическая ошибка в клиенте: {e_main}"); import traceback; traceback.print_exc()
    finally:
        stop_ws_listener_sync() # Гарантированная попытка остановить WS при любом выходе
        print("Клиент полностью завершил работу.")