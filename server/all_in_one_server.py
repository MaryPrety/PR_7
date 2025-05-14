# server/all_in_one_server.py
import socket
import threading
import asyncio
import websockets # type: ignore
import json
import random
import time
import uuid # Для генерации session_id

# ========================
# Настройки портов
# ========================
TCP_HOST = '0.0.0.0'
TCP_PORT = 5000
WS_HOST = '0.0.0.0'
WS_PORT = 8765
UDP_HOST = '0.0.0.0'
UDP_PORT = 5002

# ========================
# "База данных" активных сессий (очень упрощенная, в памяти)
# Формат: { "session_id_1": {"user_name": "some_user", "last_seen": timestamp, "addr": address_tuple}, ... }
# ========================
active_sessions = {}
SESSION_TIMEOUT_SECONDS = 30 * 60 # 30 минут жизни сессии без активности

# ========================
# Локальный кэш событий (для WebSocket)
# ========================
server_event_cache = [] # Хранит последние N событий, генерируемых сервером
MAX_SERVER_CACHE_SIZE = 20

# ========================
# TCP Server (настройка профиля и управление сессиями)
# ========================
def handle_tcp_client(conn, addr):
    print(f"[TCP] Подключение от {addr}")
    raw_data_str = "" # Для логгирования в случае ошибки JSON
    try:
        raw_data_bytes = conn.recv(1024)
        if not raw_data_bytes:
            print(f"[TCP] Получены пустые данные от {addr}. Соединение закрыто.")
            return # Просто выходим, conn закроется в finally

        raw_data_str = raw_data_bytes.decode('utf-8')
        client_payload = json.loads(raw_data_str)
        print(f"[TCP] Получен payload от {addr}: {client_payload}")

        client_session_id = client_payload.get("session_id")
        # Извлекаем имя пользователя, если есть, или используем IP:Port как идентификатор
        user_identifier_from_payload = client_payload.get("name", f"{addr[0]}:{addr[1]}")

        current_server_session_id = None
        session_status_message = ""

        if client_session_id and client_session_id in active_sessions:
            # Клиент прислал существующий ID, проверяем его (в нашем случае просто обновляем)
            active_sessions[client_session_id]["last_seen"] = time.time()
            # Обновляем имя пользователя, если оно изменилось или было установлено
            if "name" in client_payload:
                 active_sessions[client_session_id]["user_name"] = user_identifier_from_payload
            current_server_session_id = client_session_id
            session_status_message = f"Сессия {client_session_id} для '{active_sessions[client_session_id]['user_name']}' подтверждена и обновлена."
            print(f"[TCP] {session_status_message}")
        else:
            # Клиент прислал невалидный ID или не прислал ID вовсе - генерируем новый
            current_server_session_id = str(uuid.uuid4())
            active_sessions[current_server_session_id] = {
                "user_name": user_identifier_from_payload,
                "last_seen": time.time(),
                "addr": addr, # Сохраняем адрес для информации
                "tcp_connection_time": time.time()
            }
            session_status_message = f"Для '{user_identifier_from_payload}' создана новая сессия: {current_server_session_id}."
            print(f"[TCP] {session_status_message}")
        
        # Формируем JSON ответ
        response_payload = {
            "status": "success",
            "message": f"Профиль '{user_identifier_from_payload}' обработан. {session_status_message}",
            "session_id": current_server_session_id # Всегда возвращаем актуальный ID
        }
        conn.sendall(json.dumps(response_payload).encode('utf-8'))

    except json.JSONDecodeError as e:
        error_message = f"Ошибка при разборе JSON от {addr}: {e}. Полученные данные: '{raw_data_str}'"
        print(f"[TCP] {error_message}")
        try:
            response_payload = {"status": "error", "message": "Invalid JSON received by server."}
            conn.sendall(json.dumps(response_payload).encode('utf-8'))
        except Exception as send_err:
            print(f"[TCP] Ошибка при отправке JSON-сообщения об ошибке клиенту {addr}: {send_err}")
    except ConnectionResetError:
        print(f"[TCP] Соединение сброшено клиентом {addr} во время обработки.")
    except Exception as e:
        error_message = f"Непредвиденная ошибка при обработке TCP от {addr}: {e}"
        print(f"[TCP] {error_message}")
        try:
            response_payload = {"status": "error", "message": f"Server error during TCP processing: {str(e)[:100]}"}
            conn.sendall(json.dumps(response_payload).encode('utf-8'))
        except Exception as send_err:
             print(f"[TCP] Ошибка при отправке JSON-сообщения о непредвиденной ошибке клиенту {addr}: {send_err}")
    finally:
        if conn:
            try:
                conn.close()
                # print(f"[TCP] Соединение с {addr} закрыто.")
            except Exception as e_close:
                print(f"[TCP] Ошибка при закрытии соединения с {addr}: {e_close}")

def run_tcp_server():
    # Запускаем очистку старых сессий в отдельном потоке, чтобы не блокировать основной
    session_cleanup_thread = threading.Thread(target=periodic_session_cleanup, daemon=True)
    session_cleanup_thread.start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Позволяет переиспользовать адрес
        s.bind((TCP_HOST, TCP_PORT))
        s.listen()
        print(f"[TCP] Сервер запущен на {TCP_HOST}:{TCP_PORT}...")

        while True: # Цикл приема новых подключений
            try:
                conn, addr = s.accept()
                # Для каждого клиента создаем новый поток для обработки
                client_thread = threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True)
                client_thread.start()
            except Exception as e_accept:
                print(f"[TCP] Ошибка при приеме подключения: {e_accept}")
                # Можно добавить небольшую паузу перед следующей попыткой accept, если ошибки частые
                time.sleep(0.1)


def periodic_session_cleanup():
    """Периодически удаляет истекшие сессии."""
    while True:
        time.sleep(SESSION_TIMEOUT_SECONDS / 2) # Проверяем каждые полтаймаута
        now = time.time()
        expired_ids = [
            sid for sid, data in list(active_sessions.items()) # list() для создания копии перед итерацией
            if now - data.get("last_seen", 0) > SESSION_TIMEOUT_SECONDS
        ]
        if expired_ids:
            print(f"[TCP Sessions] Начинается очистка {len(expired_ids)} истекших сессий...")
            for sid in expired_ids:
                if sid in active_sessions: # Дополнительная проверка, вдруг сессия обновилась
                    del active_sessions[sid]
                    print(f"[TCP Sessions] Истекшая сессия {sid} удалена.")
        # else:
        #     print(f"[TCP Sessions] Нет истекших сессий для удаления. Активных: {len(active_sessions)}")


# ========================
# WebSocket Server (события и обновления)
# ========================
connected_ws_clients = set() # Хранит объекты websocket соединений

async def ws_register_client(websocket):
    connected_ws_clients.add(websocket)
    remote_addr_str = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}" if websocket.remote_address else "Unknown WS Client"
    print(f"[WS] Новый клиент подключен: {remote_addr_str} (Всего: {len(connected_ws_clients)})")

async def ws_unregister_client(websocket):
    connected_ws_clients.discard(websocket) # Используем discard для безопасности
    remote_addr_str = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}" if websocket.remote_address else "Unknown WS Client"
    print(f"[WS] Клиент отключился: {remote_addr_str} (Осталось: {len(connected_ws_clients)})")


async def ws_message_handler(websocket, path):
    await ws_register_client(websocket)
    try:
        # Можно добавить обработку входящих сообщений от клиента, если нужно
        # Например, клиент может отправить свой session_id для идентификации
        # async for message in websocket:
        #     print(f"[WS] Получено от {websocket.remote_address}: {message[:100]}")
        #     # Тут может быть логика привязки WebSocket к TCP сессии по session_id
        
        # Держим соединение открытым для получения broadcast'ов
        # Клиент должен поддерживать пинг/понг или периодически слать что-то, чтобы сервер его не закрыл по таймауту
        while True:
            await asyncio.sleep(3600) # Просто спим, ожидая broadcast или закрытия соединения
    except websockets.ConnectionClosedError as cce: # type: ignore
        print(f"[WS] Соединение с {websocket.remote_address} закрыто с ошибкой: {cce.reason} (код {cce.code})")
    except websockets.ConnectionClosedOK: # type: ignore
        print(f"[WS] Соединение с {websocket.remote_address} закрыто корректно.")
    except Exception as e_ws_handler:
        print(f"[WS] Ошибка в обработчике WebSocket для {websocket.remote_address}: {e_ws_handler}")
    finally:
        await ws_unregister_client(websocket)


async def broadcast_server_events():
    """Генерирует и рассылает "события дня" и другие данные всем WebSocket клиентам."""
    global server_event_cache
    while True:
        # Генерация "события дня" (Пункт 7)
        day_event_payload = {
            "type": "day_event",
            "event_name": f"Редкий артефакт #{int(time.time() % 1000)} обнаружен!",
            "description": f"В локации '{random.choice(['Забытые Руины', 'Лес Теней', 'Хрустальная Пещера'])}' появился {random.choice(['Могущественный артефакт', 'Древний свиток', 'Зачарованный кристалл'])}.",
            "timestamp_event": time.time() # Используем другое имя, чтобы не конфликтовать с timestamp сообщения
        }
        server_event_cache.append({"timestamp": time.time(), "event": day_event_payload}) # Добавляем в серверный кэш
        if len(server_event_cache) > MAX_SERVER_CACHE_SIZE:
            server_event_cache.pop(0)
        
        message_to_send_day_event = json.dumps(day_event_payload)

        # Генерация "данных, которые меняются" (Пункт 4)
        # Пример: информация о погоде в случайном городе или "игровые новости"
        changing_data_payload = {
            "type": "data_update",
            "source": "server_generator",
            "content": {
                "topic": random.choice(["Погода", "Экономика игры", "Активность монстров"]),
                "value": random.randint(1, 100),
                "details": f"Последнее обновление {time.strftime('%H:%M:%S')}"
            },
            "timestamp_update": time.time()
        }
        message_to_send_data_update = json.dumps(changing_data_payload)

        # Копируем сет клиентов перед итерацией
        clients_snapshot = list(connected_ws_clients)
        if clients_snapshot:
            print(f"[WS Broadcast] Отправка {len(clients_snapshot)} клиентам...")
            # Рассылаем событие дня
            # await websockets.broadcast(clients_snapshot, message_to_send_day_event) # Удобно, но менее гибко с обработкой ошибок
            for client in clients_snapshot:
                try:
                    await client.send(message_to_send_day_event)
                except Exception: pass # Ошибки обработаются в ws_message_handler при разрыве

            await asyncio.sleep(5) # Небольшая пауза между типами сообщений

            # Рассылаем обновляемые данные
            for client in clients_snapshot: # Используем тот же снепшот
                try:
                    await client.send(message_to_send_data_update)
                except Exception: pass
        
        # Интервал для "данные меняются каждые 1-5 минут"
        await asyncio.sleep(random.randint(60, 300)) # 1-5 минут

async def run_websocket_server():
    # Запускаем фоновую задачу для рассылки событий
    asyncio.create_task(broadcast_server_events())
    
    # Запускаем сервер для приема подключений
    # ping_interval и ping_timeout помогают поддерживать соединение живым и обнаруживать разрывы
    async with websockets.serve(ws_message_handler, WS_HOST, WS_PORT, ping_interval=20, ping_timeout=20): # type: ignore
        print(f"[WebSocket] Сервер запущен на {WS_HOST}:{WS_PORT}...")
        await asyncio.Future()  # Держит сервер работающим "вечно"


# ========================
# UDP Server (гео-подсказки)
# ========================
def run_udp_server():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((UDP_HOST, UDP_PORT))
        print(f"[UDP] Сервер запущен на {UDP_HOST}:{UDP_PORT}...")

        while True:
            raw_data_udp = b""
            addr_udp = None
            try:
                raw_data_udp, addr_udp = sock.recvfrom(1024) # Размер буфера
                location_payload = json.loads(raw_data_udp.decode('utf-8'))
                print(f"[UDP] Получена геолокация от {addr_udp}: {location_payload}")
                
                client_session_id_udp = location_payload.get("session_id")
                if client_session_id_udp and client_session_id_udp in active_sessions:
                    active_sessions[client_session_id_udp]["last_seen"] = time.time() # Обновляем сессию
                    user_name_for_hint = active_sessions[client_session_id_udp].get("user_name", "Игрок")
                    hint_message = f"{user_name_for_hint}, вы рядом с древним обелиском. Будьте осторожны!"
                else:
                    hint_message = "Вы находитесь в неизведанной территории. Осторожнее!"
                
                hint_payload = {"hint": hint_message, "timestamp": time.time()}
                sock.sendto(json.dumps(hint_payload).encode('utf-8'), addr_udp)

            except json.JSONDecodeError:
                print(f"[UDP] Ошибка: Неверный JSON от {addr_udp}. Данные: '{raw_data_udp.decode(errors='ignore')}'")
            except Exception as e_udp:
                print(f"[UDP] Ошибка при обработке UDP запроса от {addr_udp if addr_udp else 'неизвестного источника'}: {e_udp}")


# ========================
# Запуск всех серверов
# ========================
if __name__ == "__main__":
    print("[Main Server] Запуск серверов...")

    # Запуск TCP сервера в отдельном потоке
    tcp_server_thread = threading.Thread(target=run_tcp_server, daemon=True)
    tcp_server_thread.start()

    # Запуск UDP сервера в отдельном потоке
    udp_server_thread = threading.Thread(target=run_udp_server, daemon=True)
    udp_server_thread.start()

    # Запуск WebSocket сервера (он асинхронный и блокирующий, если не обернут)
    # asyncio.run() запускает цикл событий и блокирует до завершения run_websocket_server
    try:
        asyncio.run(run_websocket_server())
    except KeyboardInterrupt:
        print("\n[Main Server] Сервер останавливается по команде пользователя (Ctrl+C)...")
    except Exception as main_loop_error:
        print(f"[Main Server] Критическая ошибка в основном цикле asyncio: {main_loop_error}")
    finally:
        print("[Main Server] Все серверные потоки должны завершиться.")