# client/voice_client/weather_service.py
import socket
import json
import requests
from datetime import datetime, timedelta

# Убираем импорт speak отсюда
# from .tts_stt import speak
from .utils import translate_city_for_public_api
from .config import (
    PUBLIC_WEATHER_API_KEY, PUBLIC_WEATHER_API_CURRENT_URL, PUBLIC_WEATHER_API_FORECAST_URL,
    PUBLIC_OWM_API_KEY, PUBLIC_OWM_AIR_POLLUTION_URL,
)

def _get_coordinates_public_fallback(location_name_original: str) -> dict | None:
    if not PUBLIC_WEATHER_API_KEY:
        return None
    location_name_for_api = translate_city_for_public_api(location_name_original)
    params_wa = {"key": PUBLIC_WEATHER_API_KEY, "q": location_name_for_api, "days": 1, "aqi": "no", "alerts": "no"}
    try:
        response = requests.get(PUBLIC_WEATHER_API_FORECAST_URL, params=params_wa, timeout=7)
        response.raise_for_status()
        data = response.json()
        if data.get("location"):
            loc = data["location"]
            if loc.get("lat") is not None and loc.get("lon") is not None:
                return {"lat": loc["lat"], "lon": loc["lon"], "name": loc.get("name", location_name_original)}
    except Exception as e:
        print(f"[WeatherServ Гео Публ.] Ошибка WA при геокодинге для '{location_name_for_api}': {e}")
    return None

def get_weather_and_air_quality_via_public_apis(city_name_from_profile: str, date_offset: int = 0) -> dict:
    print(f"[WeatherServ] Запрос погоды через ПУБЛИЧНЫЕ API для: {city_name_from_profile}, смещение дня: {date_offset}")
    city_name_for_public_api = translate_city_for_public_api(city_name_from_profile)
    requested_date_str = (datetime.now() + timedelta(days=date_offset)).strftime('%Y-%m-%d')

    weather_data = {
        "city_resolved": city_name_from_profile, "requested_date": requested_date_str,
        "temp_c": None, "condition_text": "неизвестно (публ.)", # Используем None для числовых значений по умолчанию
        "wind_kph": None, "humidity": None, "is_day": 1, "precip_mm": None,
        "aqi_value": None, "aqi_text": "неизвестно (публ.)", "aqi_source": "N/A (публ.)",
        "min_t": None, "max_t": None, "error_message": None,
        "source_info_for_speak": "публичных API"
    }

    if not PUBLIC_WEATHER_API_KEY:
        weather_data["error_message"] = "Ключ WeatherAPI (публичный) не настроен."
        return weather_data

    params_forecast_wa = {
        "key": PUBLIC_WEATHER_API_KEY, "q": city_name_for_public_api,
        "lang": "ru", "alerts": "no"
    }
    if date_offset == 0:
        params_forecast_wa["aqi"] = "yes"; params_forecast_wa["days"] = 1
    else:
        params_forecast_wa["aqi"] = "no"; params_forecast_wa["dt"] = requested_date_str

    try:
        response_f_wa = requests.get(PUBLIC_WEATHER_API_FORECAST_URL, params=params_forecast_wa, timeout=10)
        response_f_wa.raise_for_status()
        data_f_wa = response_f_wa.json()

        if data_f_wa.get("location"):
            weather_data["city_resolved"] = data_f_wa["location"].get("name", city_name_from_profile)

        if date_offset == 0 and data_f_wa.get("current"):
            current = data_f_wa["current"]
            weather_data.update({
                "temp_c": current.get("temp_c"),
                "condition_text": current.get("condition", {}).get("text", weather_data["condition_text"]),
                "wind_kph": current.get("wind_kph"), "humidity": current.get("humidity"),
                "precip_mm": current.get("precip_mm"), "is_day": current.get("is_day", 1)
            })
            if current.get("air_quality"):
                aq_data = current["air_quality"]
                weather_data["aqi_value"] = aq_data.get("us-epa-index")
                weather_data["aqi_source"] = "WeatherAPI (публ.)"
                if weather_data["aqi_value"] is not None:
                    epa_map = {1:"хорошее",2:"умеренное",3:"нездоровое для чувствительных групп",4:"нездоровое",5:"очень нездоровое",6:"опасное"}
                    weather_data["aqi_text"] = epa_map.get(weather_data["aqi_value"], f"EPA индекс {weather_data['aqi_value']}")
            if data_f_wa.get("forecast", {}).get("forecastday") and data_f_wa["forecast"]["forecastday"]:
                today_forecast = data_f_wa["forecast"]["forecastday"][0]["day"]
                weather_data.update({
                    "min_t": today_forecast.get("mintemp_c"), "max_t": today_forecast.get("maxtemp_c")
                })
                if weather_data["condition_text"] == "неизвестно (публ.)": # Если current не дал condition_text
                     weather_data["condition_text"] = today_forecast.get("condition",{}).get("text","неизвестно (публ.)")

        elif data_f_wa.get("forecast", {}).get("forecastday") and data_f_wa["forecast"]["forecastday"]:
            forecast_day_data = data_f_wa["forecast"]["forecastday"][0]["day"]
            weather_data.update({
                "min_t": forecast_day_data.get("mintemp_c"), "max_t": forecast_day_data.get("maxtemp_c"),
                "temp_c": forecast_day_data.get("avgtemp_c"),
                "condition_text": forecast_day_data.get("condition",{}).get("text", weather_data["condition_text"]),
                "wind_kph": forecast_day_data.get("maxwind_kph"),
                "humidity": forecast_day_data.get("avghumidity"),
                "precip_mm": forecast_day_data.get("totalprecip_mm")
            })
            if weather_data["aqi_value"] is None: # Только если AQI еще не установлен
                weather_data["aqi_text"] = "нет данных AQI для прогноза"
        else: # Если нет ни current, ни forecastday данных
            if not weather_data.get("error_message"): # Только если еще нет другой ошибки
                weather_data["error_message"] = "Отсутствуют данные о погоде в ответе WeatherAPI."


    except requests.exceptions.HTTPError as http_err:
        error_msg_prefix = f"Ошибка WeatherAPI (прогноз), код {http_err.response.status_code}"
        try:
            error_details = http_err.response.json()
            api_error_message = error_details.get("error", {}).get("message", "Неизвестная ошибка API.")
            if "future date beyond available range" in api_error_message.lower() or \
               "dt_out_of_range" in api_error_message.lower() or \
               ("parameter q has bad value" in api_error_message.lower() and "date is out of range" in api_error_message.lower()):
                weather_data["error_message"] = f"Прогноз на дату {requested_date_str} недоступен (слишком далеко или неверный город)."
            else:
                weather_data["error_message"] = f"{error_msg_prefix}: {api_error_message}"
            print(f"[WeatherServ Публ.] {error_msg_prefix}: {api_error_message} для '{city_name_for_public_api}', дата: {requested_date_str}")
        except json.JSONDecodeError:
             weather_data["error_message"] = f"{error_msg_prefix}: Неверный формат ответа при ошибке."
             print(f"[WeatherServ Публ.] {error_msg_prefix}, не JSON: {http_err.response.text[:100]} для '{city_name_for_public_api}', дата: {requested_date_str}")
    except Exception as e_f_wa:
        print(f"[WeatherServ Публ.] Общая ошибка WA (прогноз) для '{city_name_for_public_api}', дата {requested_date_str}: {e_f_wa}")
        if not weather_data["error_message"]:
            weather_data["error_message"] = f"Ошибка прогноза погоды (публичные API): {str(e_f_wa)[:50]}"

    if PUBLIC_OWM_API_KEY and weather_data["aqi_value"] is None and date_offset == 0:
        coords_for_owm = _get_coordinates_public_fallback(weather_data["city_resolved"])
        if coords_for_owm and coords_for_owm.get("lat") is not None:
            params_owm_aqi = {"lat": coords_for_owm["lat"], "lon": coords_for_owm["lon"], "appid": PUBLIC_OWM_API_KEY}
            try:
                resp_owm_aqi = requests.get(PUBLIC_OWM_AIR_POLLUTION_URL, params=params_owm_aqi, timeout=7)
                resp_owm_aqi.raise_for_status()
                data_owm_aqi = resp_owm_aqi.json()
                if data_owm_aqi.get("list") and data_owm_aqi["list"]:
                    owm_idx = data_owm_aqi["list"][0]["main"]["aqi"]
                    if weather_data["aqi_value"] is None: # Обновляем только если еще не было
                        weather_data["aqi_value"] = owm_idx
                        weather_data["aqi_source"] = "OWM (публ.)"
                        owm_map = {1:"хорошее",2:"удовлетворительное",3:"умеренное загрязнение",4:"плохое",5:"очень плохое"}
                        weather_data["aqi_text"] = owm_map.get(owm_idx, f"OWM индекс {owm_idx}")
                        if weather_data["error_message"] and "WeatherAPI" in weather_data["error_message"]:
                             weather_data["error_message"] = None
            except Exception as e_owm_aqi:
                print(f"[WeatherServ Публ.] Ошибка OWM AQI для '{coords_for_owm.get('name')}': {e_owm_aqi}")
                if weather_data["aqi_text"] == "неизвестно (публ.)":
                    weather_data["aqi_text"] = "не удалось определить AQI (OWM)"

    if weather_data["temp_c"] is None and weather_data["condition_text"] == "неизвестно (публ.)" and not weather_data["error_message"]:
        weather_data["error_message"] = "Не удалось получить основные данные о погоде (публичные API)."
    return weather_data

def handle_get_weather_request(
        user_profile_obj: dict, active_server_config: dict | None,
        current_session_id: str | None, session_id_update_callback: callable,
        city_override: str | None = None, date_offset_override: int = 0
    ) -> dict: # Изменил возвращаемый тип на dict, т.к. мы всегда что-то возвращаем
    user_city_from_profile = user_profile_obj.get("city", "Москва")
    city_to_request = city_override if city_override else user_city_from_profile
    actual_date_offset = max(0, min(date_offset_override, 2))
    
    # Инициализируем базовый словарь ответа, который будет заполняться
    # Это гарантирует, что функция всегда вернет словарь с ожидаемой структурой.
    base_response_structure = {
        "city_resolved": city_to_request,
        "requested_date": (datetime.now() + timedelta(days=actual_date_offset)).strftime('%Y-%m-%d'),
        "temp_c": None, "condition_text": "неизвестно", "wind_kph": None, "humidity": None,
        "is_day": 1, "precip_mm": None, "aqi_value": None, "aqi_text": "неизвестно",
        "aqi_source": "N/A", "min_t": None, "max_t": None, "error_message": None,
        "source_info_for_speak": "неизвестного источника"
    }

    if date_offset_override > 2 or date_offset_override < 0:
        # Сообщение об ограничении даты будет сформировано для озвучивания
        base_response_structure["error_message"] = f"Прогноз на запрошенную дату ({date_offset_override} дн.) недоступен. Показан прогноз на {actual_date_offset} дн."
        # Продолжаем с actual_date_offset


    print(f"[WeatherServ] Запрос погоды для города: '{city_to_request}', смещение дня: {actual_date_offset}")

    if active_server_config:
        server_name_log = active_server_config.get("name_internal", "приватный сервер")
        print(f"[WeatherServ] Попытка запроса через '{server_name_log}'...")
        server_ip = active_server_config.get("ip")
        server_tcp_port = active_server_config.get("tcp_port")

        if not server_ip or not server_tcp_port:
            print(f"[WeatherServ] Неполная конфигурация для '{server_name_log}'. Fallback.")
            fallback_data = get_weather_and_air_quality_via_public_apis(city_to_request, actual_date_offset)
            if base_response_structure["error_message"] and not fallback_data.get("error_message"):
                 # Если была ошибка ограничения даты, а fallback не дал ошибки, сохраняем исходную
                 fallback_data["error_message"] = base_response_structure["error_message"]
            return fallback_data


        payload_to_server = {
            "action": "get_weather_for_client", "city": city_to_request,
            "date_offset": actual_date_offset, "session_id": current_session_id
        }
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(12)
                s.connect((server_ip, server_tcp_port))
                s.sendall(json.dumps(payload_to_server).encode('utf-8'))
                response_bytes = s.recv(8192)
                if not response_bytes:
                    print(f"[WeatherServ<-Сервер] Нет ответа от '{server_name_log}'. Fallback.")
                    return get_weather_and_air_quality_via_public_apis(city_to_request, actual_date_offset)

                server_data_response = json.loads(response_bytes.decode('utf-8'))
                new_sid_from_srv = server_data_response.get("session_id")
                if new_sid_from_srv: session_id_update_callback(new_sid_from_srv)

                if server_data_response.get("status") == "success" and "data" in server_data_response:
                    print(f"[WeatherServ] Погода успешно получена от '{server_name_log}'.")
                    server_weather_data = server_data_response["data"]
                    server_weather_data["source_info_for_speak"] = f"приватного сервера '{server_name_log}'"
                    server_weather_data["requested_date"] = (datetime.now() + timedelta(days=actual_date_offset)).strftime('%Y-%m-%d')
                    if base_response_structure["error_message"] and not server_weather_data.get("error_message_server"):
                        server_weather_data["error_message_server"] = base_response_structure["error_message"] # Переносим ошибку ограничения даты
                    return server_weather_data
                else:
                    error_msg_fs = server_data_response.get("message", "неизвестная ошибка от приватного сервера")
                    print(f"[WeatherServ] '{server_name_log}' сообщил: '{error_msg_fs}'. Fallback.")
                    # Сохраняем ошибку от сервера для возможного озвучивания, если публичные API тоже не дадут данных
                    base_response_structure["error_message_server"] = error_msg_fs 
                    # Если была ошибка ограничения даты, она важнее общей ошибки сервера
                    if base_response_structure["error_message"] and "Прогноз на запрошенную дату" in base_response_structure["error_message"]:
                         pass # Оставляем ошибку ограничения даты
                    return get_weather_and_air_quality_via_public_apis(city_to_request, actual_date_offset)

        except (socket.timeout, ConnectionRefusedError, json.JSONDecodeError, Exception) as e:
            print(f"[WeatherServ] Ошибка с '{server_name_log}': {e}. Fallback.")
            base_response_structure["error_message_server"] = f"Ошибка связи с приватным сервером: {str(e)[:50]}"
            return get_weather_and_air_quality_via_public_apis(city_to_request, actual_date_offset)
    else:
        # print("[WeatherServ] Приватный сервер не активен. Использую публичные API.")
        return get_weather_and_air_quality_via_public_apis(city_to_request, actual_date_offset)


def format_weather_for_speech(weather_data_dict: dict, city_for_speech_original_request: str) -> str:
    """Формирует строку с погодой для озвучивания."""
    if not weather_data_dict: # Это не должно происходить, т.к. handle_get_weather_request всегда возвращает dict
        return f"К сожалению, не удалось получить данные о погоде для города {city_for_speech_original_request}."

    source_info = weather_data_dict.get("source_info_for_speak", "неизвестного источника")
    resolved_city_from_data = weather_data_dict.get('city_resolved', city_for_speech_original_request)
    requested_date_str = weather_data_dict.get("requested_date")
    
    date_for_speech = "сегодня"
    if requested_date_str:
        try:
            req_date_obj = datetime.strptime(requested_date_str, '%Y-%m-%d').date()
            today_date_obj = datetime.now().date()
            delta_days = (req_date_obj - today_date_obj).days
            if delta_days == 0: date_for_speech = "сегодня"
            elif delta_days == 1: date_for_speech = "завтра"
            elif delta_days == 2: date_for_speech = "послезавтра"
            else:
                months_ru = ["января", "февраля", "марта", "апреля", "мая", "июня",
                             "июля", "августа", "сентября", "октября", "ноября", "декабря"]
                date_for_speech = f"{req_date_obj.day}-го {months_ru[req_date_obj.month - 1]}"
        except ValueError: date_for_speech = "на запрошенную дату"

    # Проверяем ошибки сначала
    # Ошибка от сервера приоритетнее, если она есть
    error_msg_to_speak = weather_data_dict.get("error_message_server") or weather_data_dict.get("error_message")
    if error_msg_to_speak:
        # Если ошибка - это наше сообщение об ограничении даты, форматируем его
        if "Прогноз на запрошенную дату" in error_msg_to_speak:
            return error_msg_to_speak # Уже содержит город и дату
        return f"Не удалось получить погоду на {date_for_speech} для города {resolved_city_from_data} от {source_info}. Причина: {error_msg_to_speak}"

    condition = weather_data_dict.get('condition_text', 'неизвестно')
    min_t = weather_data_dict.get("min_t")
    max_t = weather_data_dict.get("max_t")
    temp_c = weather_data_dict.get("temp_c") # Может быть текущей или средней для прогноза
    aqi = weather_data_dict.get("aqi_text", "нет данных AQI")

    # Если нет ни одной из ключевых метрик погоды, считаем, что данных нет
    if temp_c is None and min_t is None and max_t is None and condition.startswith("неизвестно"):
         return f"Не удалось получить основные данные о погоде на {date_for_speech} для города {resolved_city_from_data} от {source_info}."

    speak_parts = [f"По данным от {source_info}, {date_for_speech} в городе {resolved_city_from_data} ожидается: {condition}."]
    
    if min_t is not None and max_t is not None:
        speak_parts.append(f"Температура воздуха от {min_t} до {max_t}° Цельсия.")
    elif temp_c is not None:
        speak_parts.append(f"Температура около {temp_c}° Цельсия.")
    
    non_informative_aqi = [
        "неизвестно", "не удалось определить", "неизвестно (сервер)", "неизвестно (публ.)",
        "координаты для AQI не найдены", "индекс EPA неизв.", "индекс OWM неизв.",
        "не удалось определить (сервер)", "не удалось определить OWM (сервер)",
        "нет данных AQI", "aqi нет данных", "нет данных AQI для прогноза",
        "не удалось определить AQI (OWM)", "N/A (публ.)", "N/A" # Добавил N/A
    ]
    if aqi not in non_informative_aqi and aqi is not None:
        # Убираем суффиксы в скобках для озвучивания
        cleaned_aqi = aqi.split('(')[0].strip()
        speak_parts.append(f"Качество воздуха: {cleaned_aqi}.")
    
    return " ".join(speak_parts)