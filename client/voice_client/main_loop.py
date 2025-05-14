# client/voice_client/main_loop.py
import time
import os
import json
import pygame
from datetime import datetime, timedelta # Для работы с датами

from .config import (
    MENU_TEXT, MENU_KEYWORDS,
    USERS_DIR, MUSIC_FOLDER,
    FFMPEG_CONFIGURED_SUCCESSFULLY,
    SERVERS_CONFIG_FILE_VC
)
from .tts_stt import speak, listen_input, init_mixer_for_tts, engine as tts_engine
from .utils import find_best_match_command, calculate_bmi # validate_weight из profile_manager
from .profile_manager import (
    load_users, choose_user, register_new_user_interaction,
    handle_profile_management_options, handle_delete_profile_flow,
    save_user_profile, get_numeric_input_from_user, validate_weight
)
from .weather_service import (
    handle_get_weather_request,
    format_weather_for_speech 
)
from .training_service import (
    handle_start_training_session_request,
    init_training_mixer,
    # stop_training_music, # Обычно вызывается внутри training_service
    mixer_initialized_training
)
from .finance_news_service import get_financial_news_from_alphavantage
from .route_service import handle_get_route_request

# ... (код load_servers_config_main и select_server_for_user_region_main остается тем же) ...
loaded_servers_vc_main: dict = {}
active_server_config_vc_main: dict | None = None
active_session_id_vc_main: str | None = None

def load_servers_config_main():
    global loaded_servers_vc_main
    if os.path.exists(SERVERS_CONFIG_FILE_VC):
        try:
            with open(SERVERS_CONFIG_FILE_VC, "r", encoding="utf-8") as f:
                loaded_servers_vc_main = json.load(f)
                if loaded_servers_vc_main:
                    print(f"[VC Серверы] Конфигурации загружены из {SERVERS_CONFIG_FILE_VC}")
                else:
                    print(f"[VC Серверы] Файл {SERVERS_CONFIG_FILE_VC} пуст.")
        except (json.JSONDecodeError, IOError) as e:
            print(f"[VC Серверы] Ошибка загрузки '{SERVERS_CONFIG_FILE_VC}': {e}.")
            loaded_servers_vc_main = {}
    else:
        print(f"[VC Серверы] Файл конфигурации серверов '{SERVERS_CONFIG_FILE_VC}' не найден.")
        loaded_servers_vc_main = {}

def select_server_for_user_region_main(user_city: str | None) -> bool:
    global active_server_config_vc_main, active_session_id_vc_main, loaded_servers_vc_main
    if not user_city:
        if active_server_config_vc_main:
            # speak("Город не указан в профиле. Не могу выбрать приватный сервер. Fallback на публичные API.")
            print(f"[VC Серверы] Город не указан. Сброс активного сервера.")
            active_server_config_vc_main = None
            active_session_id_vc_main = None
        return False

    if not loaded_servers_vc_main:
        if active_server_config_vc_main:
            print("[VC Серверы] Конфигурации серверов не загружены, сброс активного сервера.")
        active_server_config_vc_main = None
        active_session_id_vc_main = None
        return False

    norm_city = user_city.strip().lower()
    best_match_name = None
    for s_name, cfg in loaded_servers_vc_main.items():
        if norm_city in [r.strip().lower() for r in cfg.get("regions", [])]:
            best_match_name = s_name
            break
    if not best_match_name and "default" in loaded_servers_vc_main:
        best_match_name = "default"
        print(f"[VC Серверы] Для '{user_city}' не найден специфичный сервер, используется 'default'.")

    if best_match_name:
        new_cfg = loaded_servers_vc_main[best_match_name].copy()
        new_cfg["name_internal"] = best_match_name
        if active_server_config_vc_main and active_server_config_vc_main.get("name_internal") == best_match_name:
            return True

        prev_s_name = active_server_config_vc_main.get("name_internal") if active_server_config_vc_main else None
        active_server_config_vc_main = new_cfg
        active_session_id_vc_main = None
        msg = f"Для региона ({user_city}) {'выбран другой' if prev_s_name else 'будет использован'} приватный сервер: {best_match_name}."
        # speak(msg) # Озвучивание при необходимости
        print(f"[VC Серверы] Выбран: '{best_match_name}' для '{user_city}'. IP: {active_server_config_vc_main.get('ip')}")
        return True
    else:
        if active_server_config_vc_main:
            # speak("Для вашего региона не найден приватный сервер, и сервер по умолчанию отсутствует. Fallback на публичные API.")
            print(f"[VC Серверы] Для '{user_city}' не найден сервер, и нет 'default'. Сброс активного сервера.")
        active_server_config_vc_main = None
        active_session_id_vc_main = None
        return False

all_user_profiles_list_main: list[dict] = []
current_user_profile_main: dict | None = None

def update_session_id_callback_main(new_sid: str | None):
    global active_session_id_vc_main
    if new_sid and active_session_id_vc_main != new_sid:
        active_session_id_vc_main = new_sid
        print(f"[MainLoop] Session ID обновлен: {new_sid}")
    elif not new_sid and active_session_id_vc_main is not None:
        print(f"[MainLoop] Session ID сброшен (был: {active_session_id_vc_main}).")
        active_session_id_vc_main = None


def parse_weather_query(query_text: str, default_city: str) -> tuple[str, int]:
    """Пытается извлечь город и день из запроса о погоде."""
    city = default_city
    date_offset = 0 # 0 - сегодня

    query_lower = query_text.lower()

    # Простое определение дня
    if "завтра" in query_lower:
        date_offset = 1
    elif "послезавтра" in query_lower:
        date_offset = 2
    elif "вчера" in query_lower: # Прогноз на вчера не делаем, но для примера
        date_offset = -1 # weather_service ограничит это до 0
        speak("К сожалению, я не могу показать погоду на вчера. Покажу на сегодня.")
    # ... можно добавить другие дни недели, если нужно, но это сложнее без NLU

    # Простое извлечение города: ищем "в <город>" или "для <город>"
    # Это очень примитивно и может давать ошибки.
    words = query_lower.split()
    city_found = False
    for i, word in enumerate(words):
        if word in ["в", "для", "городе"] and i + 1 < len(words):
            # Пытаемся собрать возможное название города из нескольких слов
            potential_city_parts = []
            for j in range(i + 1, len(words)):
                # Если следующее слово - предлог или указание дня, вероятно, город закончился
                if words[j] in ["завтра", "послезавтра", "сегодня", "какая", "будет"]:
                    break
                potential_city_parts.append(words[j])
            if potential_city_parts:
                city = " ".join(potential_city_parts).capitalize() # Первую букву заглавной
                city_found = True
                break
    
    # Если город не найден в явном виде, но есть слова, не относящиеся к дате,
    # можно попробовать использовать их как город.
    if not city_found:
        non_date_words = [w for w in words if w not in ["погода", "какая", "будет", "завтра", "послезавтра", "сегодня", "в", "для", "городе"]]
        if non_date_words:
            # Предполагаем, что это название города, если оно не слишком короткое
            # и не похоже на случайное слово. Это эвристика.
            potential_city_candidate = " ".join(non_date_words).capitalize()
            if len(potential_city_candidate) > 2: # Простое условие
                 # Проверим, не является ли это просто вопросительным словом или артиклем
                is_common_word = any(cw in potential_city_candidate.lower() for cw in ["какая", "такая", "покажи"])
                if not is_common_word:
                    city = potential_city_candidate


    if city == default_city and not city_found and date_offset == 0 and query_text.strip().lower() != "погода":
        # Если город остался по умолчанию, не было явного указания города, день - сегодня,
        # и запрос не просто "погода", то возможно, весь запрос был названием города.
        # Это рискованно, но можно попробовать, если другие методы не сработали.
        # Исключаем случаи, когда запрос содержит явные указания на день.
        if not ("завтра" in query_lower or "послезавтра" in query_lower or "сегодня" in query_lower):
            cleaned_query_city = query_text.replace("погода", "").replace("какая", "").replace("будет", "").strip().capitalize()
            if len(cleaned_query_city) > 2: # Если что-то осталось и это не короткое слово
                city = cleaned_query_city


    print(f"[WeatherQueryParse] Запрос: '{query_text}', Город: '{city}', Смещение дня: {date_offset}")
    return city, date_offset


def handle_get_weather_action(initial_query: str | None = None):
    if not current_user_profile_main:
        speak("Сначала выберите профиль, чтобы я мог узнать ваш город по умолчанию.")
        return

    default_city = current_user_profile_main.get("city", "Москва") # Город из профиля как fallback
    city_to_request = default_city
    date_offset_to_request = 0
    ask_for_details = True # Флаг, нужно ли спрашивать город/день

    if initial_query and initial_query.lower().strip() != "погода":
        city_from_query, date_offset_from_query = parse_weather_query(initial_query, default_city)
        # Если parse_weather_query вернул что-то отличное от дефолтов, значит, детали были в запросе
        if city_from_query != default_city or date_offset_from_query != 0:
            city_to_request = city_from_query
            date_offset_to_request = date_offset_from_query
            ask_for_details = False # Детали уже есть, не спрашиваем

        if date_offset_to_request < 0: date_offset_to_request = 0 # Погода на вчера не доступна
        # Ограничение на количество дней вперед (0-2)
        # if date_offset_to_request > 2: 
            # Сообщение об этом будет сформировано в format_weather_for_speech
            # date_offset_to_request = 2 # weather_service сам ограничит и вернет ошибку если надо

    if ask_for_details:
        speak(f"Хорошо, погода. Для какого города? По умолчанию: {default_city}.")
        city_input = listen_input(timeout_param=10, phrase_time_limit_param=10)
        if city_input and city_input.lower() not in ["да", "для него", "этот", "по умолчанию", "там же", "этот же"]:
            city_to_request = city_input.strip().capitalize()
        elif not city_input and default_city:
            # speak(f"Хорошо, смотрю для города {default_city}.") # Озвучивание будет перед запросом
            pass
        elif not default_city and not city_input: # Если нет города в профиле и не назвали
            speak("Город не указан в профиле и не был назван. Не могу продолжить.")
            return
        
        # Если город остался по умолчанию, и пользователь просто сказал "погода", уточняем день
        # или если пользователь назвал город, тоже уточняем день
        speak(f"На какой день интересует погода для города {city_to_request}? Например, сегодня, завтра или послезавтра.")
        day_input = listen_input(timeout_param=10, phrase_time_limit_param=5)
        if day_input:
            # Город здесь не важен для parse_weather_query, только для извлечения дня
            _ , date_offset_from_day_input = parse_weather_query(day_input, city_to_request) 
            date_offset_to_request = date_offset_from_day_input
            if date_offset_to_request < 0: date_offset_to_request = 0
            # if date_offset_to_request > 2:
                # date_offset_to_request = 2 # Ограничение будет обработано в weather_service

    # Озвучиваем, для какого города и дня делаем запрос, ПЕРЕД фактическим запросом
    day_str_for_prompt = "сегодня"
    if date_offset_to_request == 1: day_str_for_prompt = "завтра"
    elif date_offset_to_request == 2: day_str_for_prompt = "послезавтра"
    # Для других смещений (если поддерживается) можно добавить более сложную логику
    
    speak(f"Минутку, запрашиваю погоду для города {city_to_request} на {day_str_for_prompt}...")

    weather_data_dict = handle_get_weather_request(
        current_user_profile_main,
        active_server_config_vc_main,
        active_session_id_vc_main,
        update_session_id_callback_main,
        city_override=city_to_request,
        date_offset_override=date_offset_to_request
    )

    # ИЗМЕНЕНИЕ: Используем format_weather_for_speech для получения строки и затем speak
    speech_output = format_weather_for_speech(weather_data_dict, city_to_request)
    speak(speech_output)



def handle_start_training_action():
    if not current_user_profile_main:
        speak("Сначала выберите профиль.")
        return
    speak("Для адаптации тренировки сначала проверю погоду на сегодня...")
    # Для тренировки всегда запрашиваем погоду на сегодня для города из профиля
    city_for_training = current_user_profile_main.get("city", "Москва")
    weather_data = handle_get_weather_request(
        current_user_profile_main,
        active_server_config_vc_main,
        active_session_id_vc_main,
        update_session_id_callback_main,
        city_override=city_for_training, # Явно указываем город
        date_offset_override=0         # Явно указываем сегодня
    )
    if weather_data and not (weather_data.get("error_message_server") or weather_data.get("error_message")):
        handle_start_training_session_request(current_user_profile_main, weather_data)
    else:
        err_msg = "Не удалось получить актуальные данные о погоде."
        if weather_data and (weather_data.get("error_message_server") or weather_data.get("error_message")):
            err_msg = weather_data.get("error_message_server") or weather_data.get("error_message") or err_msg
        speak(f"{err_msg} Хотите начать стандартную тренировку в помещении?")
        if listen_input(timeout_param=10, phrase_time_limit_param=5) == "да":
            mock_weather = {
                "city_resolved": city_for_training, "temp_c": 20,
                "condition_text": "ясно (в помещении)", "aqi_text": "хорошее (в помещении)",
                "precip_mm": 0, "wind_kph": 0, "requested_date": datetime.now().strftime('%Y-%m-%d')
            }
            handle_start_training_session_request(current_user_profile_main, mock_weather)
        else:
            speak("Тренировка отменена.")

# ... (handle_bmi_action, handle_set_goal_action, handle_show_progress_action остаются прежними) ...
def handle_bmi_action():
    if not current_user_profile_main: speak("Сначала выберите профиль."); return
    weight = current_user_profile_main.get("weight"); height = current_user_profile_main.get("height")
    if weight is None or height is None or float(height or 0) == 0:
        speak("Нет данных о весе или росте, или рост равен нулю. Пожалуйста, обновите профиль."); return
    try:
        bmi_val, bmi_cat = calculate_bmi(float(weight), float(height))
        current_user_profile_main.update({"bmi": round(bmi_val, 1), "bmi_category": bmi_cat})
        if save_user_profile(current_user_profile_main):
            speak(f"{current_user_profile_main['name']}, ваш Индекс Массы Тела: {current_user_profile_main['bmi']:.1f} ({bmi_cat}).")
        else: speak(f"Ваш ИМТ: {round(bmi_val, 1)} ({bmi_cat}), но не удалось сохранить обновленные данные профиля.")
    except (ValueError, TypeError): speak("Ошибка в данных веса или роста. Пожалуйста, проверьте профиль.")

def handle_set_goal_action():
    if not current_user_profile_main: speak("Сначала выберите профиль."); return
    current_weight = current_user_profile_main.get("weight")
    speak(f"Ваш текущий вес: {current_weight if current_weight is not None else 'не указан'} кг. Какую цель по весу вы хотите установить?")
    goal_val_str = get_numeric_input_from_user("Целевой вес (кг):", default_value_str=str(current_weight) if isinstance(current_weight, (int, float)) else None)
    if goal_val_str is not None:
        try:
            valid_goal = validate_weight(goal_val_str)
            if valid_goal is not None:
                current_user_profile_main["goal_weight"] = valid_goal
                if save_user_profile(current_user_profile_main): speak(f"Цель по весу установлена: {current_user_profile_main['goal_weight']} кг.")
                else: speak("Цель по весу установлена, но не удалось сохранить профиль.")
            else: speak("Введено некорректное значение для целевого веса.")
        except ValueError: speak("Некорректный формат ввода для целевого веса.")
    else: speak("Установка цели отменена или не удалось получить ввод.")

def handle_show_progress_action():
    if not current_user_profile_main: speak("Сначала выберите профиль."); return
    initial_weight = current_user_profile_main.get('initial_weight'); current_weight = current_user_profile_main.get('weight'); goal_weight = current_user_profile_main.get('goal_weight')
    if initial_weight is None or current_weight is None:
        speak("Недостаточно данных для отображения прогресса. Убедитесь, что начальный и текущий вес указаны в профиле."); return
    try:
        initial_w_f = float(initial_weight); current_w_f = float(current_weight)
    except (ValueError, TypeError): speak("Ошибка в данных веса. Пожалуйста, проверьте профиль."); return
    speak(f"Начальный вес: {initial_w_f:.1f} кг. Текущий вес: {current_w_f:.1f} кг."); change = round(initial_w_f - current_w_f, 1)
    if change > 0.05: speak(f"Вы похудели на {abs(change):.1f} кг!")
    elif change < -0.05: speak(f"Вы набрали {abs(change):.1f} кг.")
    else: speak("Ваш вес практически не изменился.")
    if goal_weight is not None:
        try:
            goal_w_f = float(goal_weight); speak(f"Ваша цель: {goal_w_f:.1f} кг."); remaining = round(current_w_f - goal_w_f, 1)
            if remaining > 0.05: speak(f"До цели осталось сбросить {remaining:.1f} кг.")
            elif remaining < -0.05: speak(f"Вы превысили свою цель на {abs(remaining):.1f} кг! Возможно, стоит поставить новую цель.")
            else: speak("Поздравляю, вы достигли своей цели по весу!")
        except (ValueError, TypeError): speak("Ошибка в данных целевого веса. Пожалуйста, проверьте профиль.")
    else:
        speak("Цель по весу не установлена.")
        if listen_input("Хотите установить цель сейчас?", timeout_param=7) == "да": handle_set_goal_action()


# --- Основной цикл ---
def run_voice_assistant():
    global current_user_profile_main, all_user_profiles_list_main, active_session_id_vc_main, active_server_config_vc_main

    load_servers_config_main()
    speak("Привет! Я ваш фитнес-ассистент. Идет загрузка...")
    if not FFMPEG_CONFIGURED_SUCCESSFULLY:
        speak("Внимание: FFmpeg не был успешно настроен. Некоторые функции могут быть ограничены.")
    init_mixer_for_tts()
    if not init_training_mixer():
        print("[MainLoop] Микшер для музыки в тренировках не был инициализирован.")

    all_user_profiles_list_main = load_users()
    current_user_profile_main = choose_user(all_user_profiles_list_main, "Пожалуйста, выберите ваш профиль")
    if not current_user_profile_main:
        speak("Профили не найдены или не выбран. Хотите создать новый профиль?")
        if listen_input(timeout_param=10, phrase_time_limit_param=5) == "да":
            current_user_profile_main = register_new_user_interaction(None)
            if current_user_profile_main and not any(p.get("name", "").lower() == current_user_profile_main.get("name", "").lower() for p in all_user_profiles_list_main):
                 all_user_profiles_list_main.append(current_user_profile_main)
                 save_user_profile(current_user_profile_main) # Сохраняем новый профиль
        else:
            speak("Без профиля работа ассистента невозможна. Завершаю."); return

    if not current_user_profile_main:
        speak("Профиль не установлен. Перезапустите ассистента."); return

    select_server_for_user_region_main(current_user_profile_main.get("city"))
    speak(f"Профиль {current_user_profile_main.get('name', 'Пользователь')} активен. Чем могу помочь? Скажите 'команды' для списка.")

    try:
        while True:
            if not current_user_profile_main: # Защита
                speak("Произошла ошибка с активным профилем. Пожалуйста, выберите или создайте профиль.")
                all_user_profiles_list_main = load_users()
                current_user_profile_main = choose_user(all_user_profiles_list_main, "Активный профиль?")
                if not current_user_profile_main: speak("Не удалось восстановить профиль. Завершаю работу."); break
                select_server_for_user_region_main(current_user_profile_main.get("city"))
                speak(f"Профиль {current_user_profile_main.get('name')} снова активен.")

            original_cmd_in = listen_input(timeout_param=7, phrase_time_limit_param=15) # Общие параметры для команд
            if not original_cmd_in:
                continue

            action_key = None
            cmd_lower = original_cmd_in.lower()

            # Сначала проверяем, не является ли это запросом погоды с деталями
            if "погод" in cmd_lower and not ("команды" in cmd_lower or "меню" in cmd_lower): # "погод" - чтобы ловить "погода", "погоду"
                action_key = "get_weather"
                # handle_get_weather_action вызовет parse_weather_query с original_cmd_in
            elif "команды" in cmd_lower or "меню" in cmd_lower:
                speak(MENU_TEXT)
                speak("Что выберете?")
                continue
            elif "изменить профиль" in cmd_lower or "редактировать профиль" in cmd_lower: action_key = "edit_profile_details"
            elif "удалить профиль" in cmd_lower: action_key = "delete_profile_interactive"
            elif "новый пользователь" in cmd_lower or "добавить пользователя" in cmd_lower or "создать профиль" in cmd_lower: action_key = "add_user_profile"
            elif "профил" in cmd_lower: action_key = "manage_profile"

            if action_key is None:
                action_key = find_best_match_command(original_cmd_in, MENU_KEYWORDS)

            # --- Обработка действий ---
            if action_key == "exit": speak(f"До свидания, {current_user_profile_main.get('name', 'пользователь')}!"); break
            
            elif action_key == "get_weather":
                # Если action_key был определен как "get_weather" из-за "погод" в cmd_lower,
                # передаем original_cmd_in для парсинга.
                # Если action_key был найден через find_best_match_command для простого "погода",
                # то initial_query будет None, и handle_get_weather_action задаст вопросы.
                query_for_weather = original_cmd_in if "погод" in cmd_lower else None
                handle_get_weather_action(initial_query=query_for_weather)
            
            elif action_key == "start_training": handle_start_training_action()
            elif action_key == "show_bmi": handle_bmi_action()
            elif action_key == "set_goal": handle_set_goal_action()
            elif action_key == "show_progress": handle_show_progress_action()
            elif action_key == "get_financial_news": get_financial_news_from_alphavantage(current_user_profile_main)
            elif action_key == "get_route": handle_get_route_request(current_user_profile_main)
            
            # ... (остальная часть run_voice_assistant с обработкой профилей остается такой же, как в вашем последнем полном коде)
            elif action_key=="manage_profile":
                if not current_user_profile_main: speak("Сначала выберите профиль."); continue
                updated_user, profiles_list_updated = handle_profile_management_options(current_user_profile_main, all_user_profiles_list_main)
                all_user_profiles_list_main = profiles_list_updated
                if updated_user:
                    current_user_profile_main = updated_user
                    select_server_for_user_region_main(current_user_profile_main.get("city"))
                elif not all_user_profiles_list_main: speak("Все профили были удалены. Завершаю работу."); break
                else:
                    speak("Текущий профиль был удален.")
                    current_user_profile_main = choose_user(all_user_profiles_list_main, "Пожалуйста, выберите новый активный профиль.")
                    if not current_user_profile_main: speak("Активный профиль не выбран. Завершаю работу."); break
                    select_server_for_user_region_main(current_user_profile_main.get("city"))
                    speak(f"Профиль {current_user_profile_main.get('name')} теперь активен.")

            elif action_key=="edit_profile_details":
                 if not current_user_profile_main: speak("Сначала выберите профиль."); continue
                 prev_city = current_user_profile_main.get("city"); original_name = current_user_profile_main.get("name")
                 edited_user = register_new_user_interaction(existing_profile_data=current_user_profile_main.copy())
                 if edited_user:
                     current_user_profile_main = edited_user; found_in_list = False
                     for i, p in enumerate(all_user_profiles_list_main):
                         if p.get("name", "").lower() == original_name.lower():
                             all_user_profiles_list_main[i] = edited_user; found_in_list = True; break
                     if not found_in_list: all_user_profiles_list_main.append(edited_user)
                     save_user_profile(edited_user) # Сохраняем изменения
                     speak(f"Профиль {edited_user.get('name')} обновлен.")
                     if edited_user.get("city") != prev_city: select_server_for_user_region_main(edited_user.get("city"))
                 else: speak("Редактирование профиля отменено или не удалось.")

            elif action_key=="delete_profile_interactive":
                if not current_user_profile_main: speak("Сначала выберите профиль."); continue
                new_active_profile, profiles_list_updated = handle_delete_profile_flow(current_user_profile_main, all_user_profiles_list_main)
                all_user_profiles_list_main = profiles_list_updated; current_user_profile_main = new_active_profile
                if current_user_profile_main:
                    speak(f"Профиль {current_user_profile_main.get('name')} теперь активен.")
                    select_server_for_user_region_main(current_user_profile_main.get("city"))
                elif not all_user_profiles_list_main: speak("Все профили удалены. Завершаю работу."); break
                else:
                    current_user_profile_main = choose_user(all_user_profiles_list_main, "Текущий профиль удален. Пожалуйста, выберите новый активный профиль.")
                    if not current_user_profile_main: speak("Активный профиль не выбран. Завершаю работу."); break
                    select_server_for_user_region_main(current_user_profile_main.get("city"))
                    speak(f"Профиль {current_user_profile_main.get('name')} теперь активен.")

            elif action_key == "add_user_profile":
                added_prof = register_new_user_interaction(None)
                if added_prof:
                    all_user_profiles_list_main[:] = [p for p in all_user_profiles_list_main if p.get("name","").lower() != added_prof.get("name","").lower()]
                    all_user_profiles_list_main.append(added_prof)
                    save_user_profile(added_prof) # Сохраняем новый профиль
                    speak(f"Профиль {added_prof['name']} успешно создан.")
                    speak("Хотите переключиться на этот профиль сейчас?")
                    if listen_input(timeout_param=7, phrase_time_limit_param=5) == "да":
                        current_user_profile_main = added_prof
                        select_server_for_user_region_main(current_user_profile_main.get("city"))
                        speak(f"Активен профиль: {current_user_profile_main.get('name')}")
                else: speak("Создание нового профиля отменено или не удалось.")
            
            elif action_key is None and original_cmd_in:
                 speak(f"Извините, я не понял команду '{original_cmd_in}'. Пожалуйста, скажите 'команды' для списка доступных действий.")

            if action_key and action_key != "exit": # Если была команда (кроме выхода)
                speak(f"{current_user_profile_main.get('name', 'Пользователь')}, что-нибудь еще?")
            time.sleep(0.1) # Небольшая пауза в цикле

    except KeyboardInterrupt: speak("Получена команда прерывания. Завершаю работу.")
    except Exception as e:
        error_message_for_speak = f"Произошла критическая ошибка: {str(e)[:100]}."
        speak(error_message_for_speak); print(f"[MainLoop CRITICAL ERROR] {e}"); import traceback; traceback.print_exc()
    finally:
        if mixer_initialized_training and pygame.mixer.get_init(): pygame.mixer.quit(); print("[MainLoop] Pygame mixer (для тренировок) был остановлен.")
        if tts_engine and hasattr(tts_engine, '_inLoop') and tts_engine._inLoop:
             try: tts_engine.endLoop(); print("[MainLoop] Цикл TTS движка принудительно завершен.")
             except Exception as e_tts_end: print(f"[MainLoop] Ошибка при завершении цикла TTS: {e_tts_end}")
        print("[MainLoop] Голосовой ассистент завершил свою работу.")

if __name__ == '__main__':
    for dir_path in [USERS_DIR, MUSIC_FOLDER]:
        if not os.path.exists(dir_path):
            try: os.makedirs(dir_path); print(f"[Старт] Директория '{dir_path}' успешно создана.")
            except OSError as e: print(f"[Старт ОШИБКА] Не удалось создать директорию '{dir_path}': {e}")
    run_voice_assistant()