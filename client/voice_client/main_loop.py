# client/voice_client/main_loop.py
import time
import os
import json
import pygame
from datetime import datetime
import traceback

# --- Импорты из пакета ---
# Важно: эти импорты произойдут ПОСЛЕ того, как voice_client_entry.py
# инициализирует ресурсы и обновит app_config (модуль config)
from .config import (
    MENU_TEXT, MENU_KEYWORDS,
    USERS_DIR, MUSIC_FOLDER, # MUSIC_FOLDER здесь не используется напрямую, но может быть нужен
    FFMPEG_CONFIGURED_SUCCESSFULLY,
    SERVERS_CONFIG_FILE_VC,
    TRANSLATION_ENABLED as CONFIG_TRANSLATION_ENABLED_IN_MAINLOOP, # Переименовано для ясности области видимости
)
from .tts_stt import speak, listen_input, init_mixer_for_tts, engine as tts_engine
from .utils import (
    find_best_match_command, calculate_bmi,
    # validate_... функции используются в profile_manager или здесь при необходимости
)
from .profile_manager import (
    load_users, choose_user, register_new_user_interaction,
    handle_profile_management_options, # handle_delete_profile_flow вызывается из него
    save_user_profile, get_numeric_input_from_user
)
from .weather_service import handle_get_weather_request, format_weather_for_speech
from .training_service import handle_start_training_session_request, init_training_mixer, mixer_initialized_training
from .finance_news_service import get_financial_news_from_alphavantage
from .route_service import handle_get_route_request

# --- Глобальные переменные этого модуля ---
loaded_servers_vc_main: dict = {}
active_server_config_vc_main: dict | None = None
active_session_id_vc_main: str | None = None

all_user_profiles_list_main: list[dict] = []
current_user_profile_main: dict | None = None

# --- Функции управления серверами (остаются без изменений относительно предыдущей версии) ---
def load_servers_config_main():
    global loaded_servers_vc_main
    if os.path.exists(SERVERS_CONFIG_FILE_VC):
        try:
            with open(SERVERS_CONFIG_FILE_VC, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                    loaded_servers_vc_main = loaded_data
                    if loaded_servers_vc_main:
                        print(f"[VC Серверы] Конфигурации успешно загружены из {SERVERS_CONFIG_FILE_VC}")
                    else:
                        print(f"[VC Серверы] Файл {SERVERS_CONFIG_FILE_VC} пуст (валидный JSON, но пустой объект).")
                else:
                    print(f"[VC Серверы] Файл {SERVERS_CONFIG_FILE_VC} не содержит ожидаемый формат словаря. Загружено: {type(loaded_data)}")
                    loaded_servers_vc_main = {}
        except (json.JSONDecodeError, IOError) as e:
            print(f"[VC Серверы] Ошибка загрузки '{SERVERS_CONFIG_FILE_VC}': {e}.")
            loaded_servers_vc_main = {}
    else:
        print(f"[VC Серверы] Файл конфигурации '{SERVERS_CONFIG_FILE_VC}' не найден.")
        loaded_servers_vc_main = {}

def select_server_for_user_region_main(user_city: str | None) -> bool:
    global active_server_config_vc_main, active_session_id_vc_main, loaded_servers_vc_main
    if not isinstance(loaded_servers_vc_main, dict) or not loaded_servers_vc_main.get("servers"):
        # print("[VC Серверы] Конфигурации серверов не загружены или не содержат секцию 'servers'.")
        if active_server_config_vc_main: active_server_config_vc_main = None; active_session_id_vc_main = None
        return False

    server_configs_dict = loaded_servers_vc_main.get("servers", {})
    region_map = loaded_servers_vc_main.get("region_server_map", {})
    default_server_key = loaded_servers_vc_main.get("default_server")
    
    target_server_key: str | None = None

    if user_city and isinstance(region_map, dict):
        target_server_key = region_map.get(user_city.strip().lower())

    if not target_server_key: # Если не нашли по городу или город не указан
        target_server_key = default_server_key
        reason_selection = f"сервер по умолчанию ('{target_server_key}')" if target_server_key else "сервер по умолчанию не задан"
    else:
        reason_selection = f"сервер для города '{user_city}' ('{target_server_key}')"

    if target_server_key and target_server_key in server_configs_dict:
        new_config = server_configs_dict[target_server_key].copy()
        new_config["name_internal"] = target_server_key # Добавляем ключ сервера для идентификации

        if active_server_config_vc_main and active_server_config_vc_main.get("name_internal") == target_server_key:
            # print(f"[VC Серверы] Сервер '{target_server_key}' уже активен.")
            return True # Сервер не изменился

        active_server_config_vc_main = new_config
        active_session_id_vc_main = None # Сбрасываем ID сессии при смене сервера
        print(f"[VC Серверы] Выбран {reason_selection}. IP: {active_server_config_vc_main.get('ip')}")
        # speak(f"Для вашего региона ({user_city or 'по умолчанию'}) выбран сервер: {target_server_key}.")
        return True
    else:
        print(f"[VC Серверы] Не удалось найти конфигурацию для {reason_selection}. Приватный сервер не будет использован.")
        if active_server_config_vc_main: active_server_config_vc_main = None; active_session_id_vc_main = None
        return False

def update_session_id_callback_main(new_sid: str | None):
    global active_session_id_vc_main
    if new_sid != active_session_id_vc_main:
        active_session_id_vc_main = new_sid
        print(f"[MainLoop] Session ID обновлен/сброшен: {'None' if not new_sid else new_sid}")

# --- Обработчики команд (без изменений относительно предыдущей полной версии, только проверены вызовы listen_input) ---
def parse_weather_query(query_text: str, default_city: str) -> tuple[str, int]:
    # ... (код этой функции остается таким же, как в ответе от 2024-03-03 00:40)
    city, date_offset = default_city, 0; query_lower = query_text.lower()
    if "завтра" in query_lower: date_offset = 1
    elif "послезавтра" in query_lower: date_offset = 2
    elif "вчера" in query_lower: date_offset = 0; speak("Погоду на вчера не показываю, покажу на сегодня.")
    words = query_lower.split(); city_found = False
    for i, word in enumerate(words):
        if word in ["в", "для", "городе"] and i + 1 < len(words):
            parts = []; [(parts.append(words[j]),) for j in range(i + 1, len(words)) if words[j] not in ["завтра", "послезавтра", "сегодня", "какая", "будет", "погода"]];
            if parts: city = " ".join(parts).capitalize(); city_found = True; break
    if not city_found:
        non_kw = [w for w in words if w not in ["погода","какая","будет","завтра","послезавтра","сегодня","в","для","городе"]];
        if non_kw: cand_city = " ".join(non_kw).capitalize();
        if len(cand_city) > 2 and not any(q in cand_city.lower() for q in ["какая","такая"]): city=cand_city; city_found=True
    if city == default_city and not city_found and date_offset == 0 and query_text.strip().lower() != "погода":
        if not any(d in query_lower for d in ["завтра", "послезавтра", "сегодня"]):
            cl_q = query_text; [ (cl_q := cl_q.lower().replace(kw, "").strip()) for kw in ["погода","какая","будет"] ];
            if len(cl_q) > 2: city = cl_q.capitalize()
    # print(f"[WeatherParse] Q:'{query_text}', City:'{city}', Offset:{date_offset}")
    return city, date_offset

def handle_get_weather_action(initial_query: str | None = None):
    # ... (код этой функции остается таким же, как в ответе от 2024-03-03 00:40, вызовы listen_input там уже исправлены)
    global current_user_profile_main, active_server_config_vc_main, active_session_id_vc_main
    if not current_user_profile_main: speak("Сначала выберите профиль."); return
    default_city = current_user_profile_main.get("city", "Москва"); city_req, date_off_req, ask = default_city, 0, True
    if initial_query and initial_query.lower().strip() not in ["погода", "узнать погоду", "какая погода"]:
        p_city, p_off = parse_weather_query(initial_query, default_city)
        if p_city != default_city or p_off != 0: city_req, date_off_req, ask = p_city, p_off, False
    if ask:
        speak(f"Погода. Для какого города? (По умолч.: {default_city})"); city_in = listen_input(timeout=10,phrase_time_limit=10)
        if city_in and city_in.lower() not in ["да","для него","этот","по умолчанию","там же"]: city_req=city_in.strip().capitalize()
        elif not city_in and not default_city: speak("Город не указан."); return
        speak(f"На какой день погода для {city_req}? (сегодня/завтра/послезавтра)"); day_in = listen_input(timeout=10,phrase_time_limit=5)
        if day_in: _, date_off_req = parse_weather_query(day_in, city_req)
    day_s = {0:"сегодня",1:"завтра",2:"послезавтра"}.get(date_off_req, "указанный день")
    speak(f"Запрашиваю погоду для {city_req} на {day_s}..."); weather_data = handle_get_weather_request(current_user_profile_main, active_server_config_vc_main, active_session_id_vc_main, update_session_id_callback_main, city_override=city_req, date_offset_override=date_off_req)
    speak(format_weather_for_speech(weather_data, city_req))


def handle_start_training_action():
    # ... (код этой функции остается таким же, как в ответе от 2024-03-03 00:40, вызовы listen_input там уже исправлены)
    global current_user_profile_main, active_server_config_vc_main, active_session_id_vc_main
    if not current_user_profile_main: speak("Сначала выберите профиль."); return
    speak("Для адаптации тренировки проверю погоду..."); city = current_user_profile_main.get("city", "Москва")
    weather_data = handle_get_weather_request(current_user_profile_main, active_server_config_vc_main,active_session_id_vc_main, update_session_id_callback_main,city_override=city, date_offset_override=0)
    if weather_data and not (weather_data.get("error_message_server") or weather_data.get("error_message")):
        handle_start_training_session_request(current_user_profile_main, weather_data)
    else:
        err = weather_data.get("error_message_server") or weather_data.get("error_message") if weather_data else "Не удалось получить погоду."
        speak(f"{err} Хотите стандартную тренировку в помещении?");
        if listen_input(timeout=10, phrase_time_limit=5) == "да":
            mock = {"city_resolved": city, "temp_c": 20, "condition_text": "ясно(в помещении)", "precip_mm": 0}; handle_start_training_session_request(current_user_profile_main, mock)
        else: speak("Тренировка отменена.")

def handle_bmi_action():
    # ... (код этой функции остается таким же, как в ответе от 2024-03-03 00:40)
    global current_user_profile_main
    if not current_user_profile_main: speak("Сначала выберите профиль."); return
    w, h = current_user_profile_main.get("weight"), current_user_profile_main.get("height")
    bmi_v, bmi_c = calculate_bmi(w, h)
    if "нулю" in bmi_c or "не указан" in bmi_c: speak(f"Не могу рассчитать ИМТ: {bmi_c}"); return
    current_user_profile_main.update({"bmi": bmi_v, "bmi_category": bmi_c})
    if save_user_profile(current_user_profile_main): speak(f"{current_user_profile_main['name']}, ваш ИМТ: {bmi_v:.1f} ({bmi_c}).")
    else: speak(f"Ваш ИМТ: {bmi_v:.1f} ({bmi_c}), но не удалось сохранить.")

def handle_set_goal_action():
    # ... (код этой функции остается таким же, как в ответе от 2024-03-03 00:40, вызов get_numeric_input_from_user там уже исправлен)
    global current_user_profile_main
    if not current_user_profile_main: speak("Сначала выберите профиль."); return
    curr_w = current_user_profile_main.get("weight"); curr_w_s = str(curr_w) if isinstance(curr_w, (int,float)) else None
    speak(f"Текущий вес: {curr_w_s if curr_w_s else 'не указан'} кг. Цель по весу (кг)?")
    goal_s = get_numeric_input_from_user("Целевой вес (кг):", default_value_str=curr_w_s)
    if goal_s:
        from .utils import validate_weight # Поздний импорт
        valid_g = validate_weight(goal_s)
        if valid_g is not None:
            current_user_profile_main["goal_weight"] = valid_g
            if save_user_profile(current_user_profile_main): speak(f"Цель по весу: {valid_g:.1f} кг.")
            else: speak("Цель установлена, но не сохранена.")
        # else: validate_weight уже озвучил ошибку
    # else: speak("Установка цели отменена.")

def handle_show_progress_action():
    # ... (код этой функции остается таким же, как в ответе от 2024-03-03 00:40, вызовы listen_input там уже исправлены)
    global current_user_profile_main
    if not current_user_profile_main: speak("Сначала выберите профиль."); return
    init, curr, goal = (current_user_profile_main.get(k) for k in ['initial_weight','weight','goal_weight'])
    if init is None or curr is None: speak("Нет данных о начальном/текущем весе."); return
    try: init_f, curr_f = float(init), float(curr)
    except: speak("Ошибка в данных веса."); return
    speak(f"Начальный вес: {init_f:.1f}кг. Текущий: {curr_f:.1f}кг."); ch = round(init_f-curr_f,1)
    if abs(ch)<0.05: speak("Вес не изменился.")
    elif ch>0: speak(f"Вы похудели на {abs(ch):.1f}кг!")
    else: speak(f"Вы набрали {abs(ch):.1f}кг.")
    if goal is not None:
        try: goal_f = float(goal)
        except: speak("Ошибка в цели."); return
        speak(f"Цель: {goal_f:.1f}кг."); rem = round(curr_f-goal_f,1)
        if abs(rem)<0.05: speak("Вы достигли цели!")
        elif rem>0: speak(f"До цели сбросить {rem:.1f}кг.")
        else: speak(f"Вы превысили цель на {abs(rem):.1f}кг!")
    else:
        speak("Цель не установлена. Установить сейчас?");
        if listen_input(timeout=7,phrase_time_limit=5) == "да": handle_set_goal_action()

# --- Основной цикл ассистента ---
def run_voice_assistant():
    global current_user_profile_main, all_user_profiles_list_main # и другие глобальные переменные этого модуля

    # --- Инициализация (проверка флагов из config) ---
    speak("Привет! Я ваш фитнес-ассистент. Идет загрузка...")
    
    if not FFMPEG_CONFIGURED_SUCCESSFULLY: # Этот флаг из config.py
        speak("Внимание: FFmpeg не настроен. Функции, связанные с аудио, могут быть ограничены.")
    
    # CONFIG_TRANSLATION_ENABLED_IN_MAINLOOP импортирован из config и должен быть актуален
    if not CONFIG_TRANSLATION_ENABLED_IN_MAINLOOP:
        speak("Внимание: Переводчик Googletrans не инициализирован. Функции перевода будут недоступны.")
    # else:
    #     print("[MainLoop] Переводчик активен (проверено в main_loop).")

    init_mixer_for_tts()
    if not init_training_mixer():
        speak("Предупреждение: Не удалось инициализировать микшер для музыки в тренировках.")

    load_servers_config_main()
    all_user_profiles_list_main = load_users()

    # --- Выбор/создание профиля ---
    current_user_profile_main = choose_user(all_user_profiles_list_main, "Пожалуйста, выберите ваш профиль")
    if not current_user_profile_main:
        speak("Профили не найдены или не выбран. Хотите создать новый?")
        if listen_input(timeout=10, phrase_time_limit=5) == "да":
            current_user_profile_main = register_new_user_interaction(None)
            if current_user_profile_main:
                 # Убедимся, что профиль добавляется в список, если register_new_user_interaction сам его не добавил
                if not any(p.get("name") == current_user_profile_main.get("name") for p in all_user_profiles_list_main):
                    all_user_profiles_list_main.append(current_user_profile_main)
                # save_user_profile уже вызывается внутри register_new_user_interaction
        else:
            speak("Без профиля работа ассистента невозможна. Завершаю."); return

    if not current_user_profile_main:
        speak("Профиль не установлен. Перезапустите ассистента."); return

    select_server_for_user_region_main(current_user_profile_main.get("city"))
    speak(f"Профиль {current_user_profile_main.get('name', 'Пользователь')} активен. Чем могу помочь? Скажите 'команды'.")

    # --- Основной цикл обработки команд ---
    try:
        while True:
            if not current_user_profile_main: # Аварийный случай
                speak("Ошибка: активный профиль не установлен. Пожалуйста, выберите профиль.")
                all_user_profiles_list_main = load_users() # Перезагружаем список
                current_user_profile_main = choose_user(all_user_profiles_list_main, "Выберите активный профиль")
                if not current_user_profile_main: speak("Не удалось выбрать профиль. Завершаю."); break
                select_server_for_user_region_main(current_user_profile_main.get("city"))
                speak(f"Профиль {current_user_profile_main.get('name')} снова активен.")

            original_cmd_in = listen_input(timeout=7, phrase_time_limit=15) # Основной listen для команд
            if not original_cmd_in: continue

            cmd_lower = original_cmd_in.lower()
            action_key: str | None = None

            # Сначала специфические команды, которые могут содержать ключевые слова общих команд
            if "погод" in cmd_lower and not any(kw in cmd_lower for kw in ["команды", "меню"]): action_key = "get_weather"
            elif "команды" in cmd_lower or "меню" in cmd_lower: speak(MENU_TEXT); speak("Что выберете?"); continue
            # Общая команда для всех действий с профилем, включая "изменить", "удалить", "новый"
            elif any(kw in cmd_lower for kw in ["профил", "пользовател", "изменить", "удалить", "новый"]): 
                action_key = "manage_profile" 
            
            if action_key is None: # Если не специальная, ищем по карте
                action_key = find_best_match_command(original_cmd_in, MENU_KEYWORDS)

            # --- Выполнение действий ---
            if action_key == "exit": speak(f"До свидания, {current_user_profile_main.get('name', 'пользователь')}!"); break
            elif action_key == "get_weather": handle_get_weather_action(original_cmd_in if "погод" in cmd_lower else None)
            elif action_key == "start_training": handle_start_training_action()
            elif action_key == "show_bmi": handle_bmi_action()
            elif action_key == "set_goal": handle_set_goal_action()
            elif action_key == "show_progress": handle_show_progress_action()
            elif action_key == "get_financial_news": get_financial_news_from_alphavantage(current_user_profile_main)
            elif action_key == "get_route": handle_get_route_request(current_user_profile_main)
            
            elif action_key == "manage_profile":
                if not current_user_profile_main: speak("Сначала выберите профиль."); continue
                
                updated_profile, updated_list = handle_profile_management_options(
                    current_user_profile_main,
                    all_user_profiles_list_main,
                    select_server_func=select_server_for_user_region_main
                )
                all_user_profiles_list_main = updated_list # Обновляем глобальный список профилей

                if updated_profile:
                    if current_user_profile_main.get("name") != updated_profile.get("name") or \
                       current_user_profile_main.get("city") != updated_profile.get("city"):
                        current_user_profile_main = updated_profile
                        # select_server_for_user_region_main вызывается внутри handle_profile_management_options при необходимости
                        # но можно и здесь для уверенности, если город или профиль сменился
                        select_server_for_user_region_main(current_user_profile_main.get("city")) 
                        speak(f"Активен профиль: {current_user_profile_main.get('name')}.")
                    else: # Профиль тот же, изменений, влияющих на сервер, не было
                        current_user_profile_main = updated_profile
                elif not all_user_profiles_list_main: # Все профили удалены
                    speak("Все профили удалены. Давайте создадим новый.")
                    new_prof = register_new_user_interaction(None)
                    if new_prof:
                        all_user_profiles_list_main.append(new_prof)
                        current_user_profile_main = new_prof
                        select_server_for_user_region_main(current_user_profile_main.get("city"))
                        speak(f"Активен профиль: {current_user_profile_main.get('name')}.")
                    else: speak("Не удалось создать профиль. Завершаю."); break
                else: # Текущий профиль был удален, но остались другие
                    speak("Текущий профиль был удален. Выберите новый активный профиль.")
                    current_user_profile_main = choose_user(all_user_profiles_list_main, "Выберите новый активный профиль")
                    if not current_user_profile_main: speak("Активный профиль не выбран. Завершаю."); break
                    select_server_for_user_region_main(current_user_profile_main.get("city"))
                    speak(f"Профиль {current_user_profile_main.get('name')} теперь активен.")
            
            elif action_key is None and original_cmd_in:
                 speak(f"Извините, я не понял команду '{original_cmd_in}'. Пожалуйста, скажите 'команды'.")

            if action_key and action_key != "exit" and current_user_profile_main:
                speak(f"{current_user_profile_main.get('name', 'Пользователь')}, что-нибудь еще?")
            time.sleep(0.1) # Небольшая пауза

    except KeyboardInterrupt:
        speak("Получена команда прерывания. Завершаю работу.")
    except Exception as e:
        error_msg = f"Произошла критическая ошибка: {str(e)[:100]}." # Ограничиваем длину для TTS
        print(f"[MainLoop CRITICAL ERROR] {e}")
        traceback.print_exc()
        try: speak(error_msg)
        except Exception as e_speak: print(f"[MainLoop] Ошибка при озвучивании крит. ошибки: {e_speak}")
    finally:
        if mixer_initialized_training and pygame.mixer.get_init(): # Проверяем, что микшер был инициализирован
            pygame.mixer.quit()
            print("[MainLoop] Pygame mixer (для тренировок) остановлен.")
        if tts_engine and hasattr(tts_engine, '_inLoop') and tts_engine._inLoop: # type: ignore
             try: tts_engine.endLoop() # type: ignore
             except RuntimeError: pass # Может быть уже остановлен
             except Exception as e_tts_stop: print(f"[MainLoop] Ошибка при остановке TTS: {e_tts_stop}")
        print("[MainLoop] Голосовой ассистент завершил свою работу.")

# Этот блок if __name__ == '__main__': обычно нужен, если main_loop.py может запускаться напрямую.
# Если он всегда запускается через voice_client_entry.py, то этот блок здесь не обязателен,
# так как создание папок уже есть в voice_client_entry.py.
# Оставим для случая прямого запуска main_loop.py (например, для тестов без subprocess).
if __name__ == '__main__':
    # --- Инициализация необходимых директорий (дублируется из voice_client_entry.py для прямого запуска) ---
    # Важно: Если запускаете через voice_client_entry.py, эта часть здесь не нужна.
    # Но если хотите иметь возможность запускать main_loop.py напрямую, она полезна.
    
    # Для прямого запуска main_loop.py, нужно также инициализировать переводчик здесь,
    # если он не был инициализирован через voice_client_entry.py
    # (чтобы переменные в config были корректны).
    # Это усложняет, поэтому рекомендуется одна точка входа (voice_client_entry.py)
    # для инициализации глобальных ресурсов.

    # print("[Direct MainLoop Start] Создание директорий (если необходимо)...")
    # for dir_path_ml in [USERS_DIR, MUSIC_FOLDER]: # USERS_DIR, MUSIC_FOLDER из .config
    #     if not os.path.exists(dir_path_ml):
    #         try: os.makedirs(dir_path_ml, exist_ok=True)
    #         except OSError as e_mkdir_ml: print(f"[Direct MainLoop Start] Ошибка создания {dir_path_ml}: {e_mkdir_ml}")
    
    # print("[Direct MainLoop Start] Запуск run_voice_assistant...")
    run_voice_assistant()