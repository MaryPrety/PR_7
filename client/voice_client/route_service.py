# client/voice_client/route_service.py
import requests
import webbrowser
import json
import time # <--- ДОБАВЛЕН ИМПОРТ TIME

from .tts_stt import speak, listen_input
from .utils import translate_city_for_public_api # translate_city_for_public_api не используется в этом файле
from .config import PUBLIC_GRAPH_HOPPER_API_KEY, PUBLIC_GRAPH_HOPPER_URL, PUBLIC_GRAPH_HOPPER_GEOCODE_URL

# Вспомогательная функция для геокодинга через GraphHopper (для маршрутов)
def _gh_geocode_for_route(address_string_original: str) -> dict | None:
    address_for_api = address_string_original

    params_geo = {
        "q": address_for_api,
        "locale": "ru",
        "key": PUBLIC_GRAPH_HOPPER_API_KEY,
        "limit": 1
    }
    try:
        # print(f"[RouteServ GH Гео] Запрос координат для: '{address_for_api}'")
        response_geo = requests.get(PUBLIC_GRAPH_HOPPER_GEOCODE_URL, params=params_geo, timeout=8)
        response_geo.raise_for_status()
        data_geo = response_geo.json()
        if data_geo.get("hits") and data_geo["hits"]:
            hit = data_geo["hits"][0]
            point = hit.get("point")
            if point and "lat" in point and "lng" in point:
                resolved_name = hit.get("name", address_string_original)
                city_from_hit = hit.get("city")
                country_from_hit = hit.get("country")
                
                # Улучшенное формирование имени: сначала основное название, потом город (если не содержится), потом страна (если не содержится)
                name_parts = [resolved_name.split(',')[0].strip()] # Основное название
                if city_from_hit and city_from_hit.lower() not in resolved_name.lower():
                    name_parts.append(city_from_hit.strip())
                if country_from_hit and country_from_hit.lower() not in resolved_name.lower():
                    name_parts.append(country_from_hit.strip())
                
                resolved_name_final = ", ".join(name_parts)

                # print(f"[RouteServ GH Гео] Координаты для '{resolved_name_final}': {point['lat']}, {point['lng']}")
                return {"lat": point["lat"], "lon": point["lng"], "name": resolved_name_final}
            # else:
                # print(f"[RouteServ GH Гео] В ответе от GraphHopper отсутствуют координаты для '{address_for_api}'.")
        # else:
            # print(f"[RouteServ GH Гео] GraphHopper не нашел совпадений для '{address_for_api}'. Ответ: {data_geo}")
    except requests.exceptions.Timeout:
        print(f"[RouteServ GH Гео] Таймаут при геокодировании '{address_for_api}'.")
    except requests.exceptions.RequestException as e_geo:
        print(f"[RouteServ GH Гео] Ошибка запроса геокодирования для '{address_for_api}': {e_geo}")
    except Exception as e_geo_gen:
        print(f"[RouteServ GH Гео] Общая ошибка геокодирования для '{address_for_api}': {e_geo_gen}")
    return None

def handle_get_route_request(user_profile_obj: dict | None): # user_profile_obj может быть None
    # user_profile_obj здесь не используется, так как маршруты не зависят от профиля напрямую

    speak("Откуда вы хотите начать маршрут?")
    from_address_original = listen_input(timeout=10, phrase_time_limit=20) # ИСПРАВЛЕНО
    if not from_address_original:
        speak("Начальная точка маршрута не указана. Построение маршрута отменено.")
        return

    speak("Куда вы хотите построить маршрут?")
    to_address_original = listen_input(timeout=10, phrase_time_limit=20) # ИСПРАВЛЕНО
    if not to_address_original:
        speak("Конечная точка маршрута не указана. Построение маршрута отменено.")
        return

    speak(f"Ищу координаты для начала: '{from_address_original}'...")
    from_coords = _gh_geocode_for_route(from_address_original)
    if not from_coords:
        speak(f"Не удалось найти координаты для '{from_address_original}'. Попробуйте другой адрес.")
        return

    speak(f"Ищу координаты для конца: '{to_address_original}'...")
    to_coords = _gh_geocode_for_route(to_address_original)
    if not to_coords:
        speak(f"Не удалось найти координаты для '{to_address_original}'. Попробуйте другой адрес.")
        return

    speak("Как планируете передвигаться: пешком, велосипед, авто?")
    vehicle_choice_input = listen_input(timeout=7) # phrase_time_limit здесь можно оставить по умолчанию из tts_stt.py
    graphhopper_vehicle = "foot"; speak_vehicle = "пеший"
    vehicle_choice_lower = vehicle_choice_input.lower() # Приводим к нижнему регистру один раз

    if "вело" in vehicle_choice_lower: graphhopper_vehicle = "bike"; speak_vehicle = "велосипедный"
    elif "авто" in vehicle_choice_lower or "машин" in vehicle_choice_lower: graphhopper_vehicle = "car"; speak_vehicle = "автомобильный"

    route_params = {
        "point": [f"{from_coords['lat']},{from_coords['lon']}", f"{to_coords['lat']},{to_coords['lon']}"],
        "vehicle": graphhopper_vehicle, "locale": "ru", "key": PUBLIC_GRAPH_HOPPER_API_KEY,
        "instructions": "true", "calc_points": "false", "points_encoded": "false"
    }

    from_name_display = from_coords.get('name', from_address_original)
    to_name_display = to_coords.get('name', to_address_original)
    speak(f"Строю {speak_vehicle} маршрут от '{from_name_display}' до '{to_name_display}'...")

    try:
        response_route = requests.get(PUBLIC_GRAPH_HOPPER_URL, params=route_params, timeout=20)
        response_route.raise_for_status()
        data_route = response_route.json()

        if data_route.get("paths") and data_route["paths"]:
            path_details = data_route["paths"][0]
            distance_km = path_details.get("distance", 0) / 1000.0
            duration_s = path_details.get("time", 0) / 1000.0 # время в секундах из API (миллисекунды)
            
            # Форматирование времени
            hours = int(duration_s // 3600)
            minutes = int((duration_s % 3600) // 60)
            
            duration_speakable = ""
            if hours > 0:
                duration_speakable += f"{hours} час"
                if hours % 10 == 1 and hours % 100 != 11: duration_speakable += "" # 1 час
                elif 2 <= hours % 10 <= 4 and (hours % 100 < 10 or hours % 100 >= 20): duration_speakable += "а" # 2,3,4 часа
                else: duration_speakable += "ов" # 5 часов
                duration_speakable += " "
            
            if minutes > 0 or hours == 0: # Показываем минуты, если есть, или если нет часов (например, 0ч 30мин)
                duration_speakable += f"{minutes} минут"
                # Для "минут" склонение простое, в основном "минут"
            
            if not duration_speakable: # Если очень короткий маршрут
                duration_speakable = f"{int(duration_s)} секунд"


            speak(f"Маршрут построен. Расстояние: {distance_km:.1f} км. Время в пути: примерно {duration_speakable.strip()}.")

            instructions = path_details.get("instructions", [])
            if instructions:
                speak("Первые шаги:")
                for i, instr_item in enumerate(instructions[:3]): # Ограничиваем до 3 инструкций
                    instr_text = instr_item.get('text', 'Нет описания')
                    instr_dist = instr_item.get('distance', 0)
                    speak(f"Шаг {i+1}: {instr_text} ({instr_dist:.0f} м).")
                    if i < 2 : time.sleep(0.5) # Пауза между инструкциями, кроме последней озвученной
            else:
                speak("Детальные инструкции отсутствуют.")
            
            speak("Открыть карту в браузере?") # Отдельный speak перед listen_input
            if listen_input(timeout=7) == "да":
                mode_map = {"foot":"walking", "bike":"bicycling", "car":"driving"}
                map_url = f"https://www.google.com/maps/dir/?api=1&origin={from_coords['lat']},{from_coords['lon']}&destination={to_coords['lat']},{to_coords['lon']}&travelmode={mode_map.get(graphhopper_vehicle, 'walking')}"
                try:
                    webbrowser.open(map_url)
                    speak("Карта открыта.")
                except Exception as e_wb:
                    speak("Не удалось открыть карту.")
                    print(f"[RouteServ] Ошибка браузера: {e_wb}")
        else:
            msg_gh = data_route.get('message', 'неизвестная ошибка GraphHopper.')
            speak(f"Маршрут не построен. GraphHopper: {msg_gh}")
            if "Cannot find point" in msg_gh:
                speak("Попробуйте более точные адреса.")
    except requests.exceptions.Timeout:
        speak("Сервер маршрутов не ответил вовремя.")
    except requests.exceptions.HTTPError as http_err:
        speak(f"Ошибка сервера маршрутов: код {http_err.response.status_code}.")
        print(f"[RouteServ GH HTTP] {http_err.response.status_code} - {http_err.response.text[:100]}")
    except requests.exceptions.RequestException as e_req:
        speak(f"Ошибка сети при запросе маршрута: {e_req}")
    except Exception as e_gen:
        speak(f"Непредвиденная ошибка при построении маршрута: {e_gen}")
        print(f"[RouteServ Общая Ошибка] {e_gen}")