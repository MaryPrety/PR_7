# client/voice_client/training_service.py
import os
import time
from pydub import AudioSegment # type: ignore
import librosa # type: ignore
import pygame
import numpy as np
from datetime import datetime

from .tts_stt import speak, listen_input
from .utils import calculate_bmi
from .config import MUSIC_FOLDER, EXERCISES, FFMPEG_CONFIGURED_SUCCESSFULLY as FFMPEG_OK
mixer_initialized_training = False

# --- Функции для музыки (analyze_bpm, get_music_by_bpm, init_training_mixer, play_training_music, stop_training_music) ---
# Эти функции остаются такими же, как в моем предыдущем полном ответе на training_service.py
# Пожалуйста, скопируйте их оттуда сюда, чтобы не дублировать большой объем кода.
# Я начну с функции explain_exercise и далее. Если они нужны здесь полностью, дайте знать.

def analyze_bpm(file_path: str) -> int | None:
    if not FFMPEG_OK: return None
    tmp_wav = None
    try:
        audio_segment_loaded = False
        if file_path.lower().endswith(".mp3"):
            audio = AudioSegment.from_mp3(file_path); audio_segment_loaded = True
        elif file_path.lower().endswith(".wav"):
            audio = AudioSegment.from_wav(file_path); audio_segment_loaded = True
        else: return None

        if audio_segment_loaded:
            base, _ = os.path.splitext(file_path)
            tmp_wav = f"{base}_temp_bpm_analysis_{os.getpid()}.wav" # Уникальное имя
            audio.export(tmp_wav, format="wav"); load_p = tmp_wav
        else: return None
        y, sr_lib = librosa.load(load_p, sr=None)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr_lib)
        tempo_values = librosa.feature.tempo(onset_envelope=onset_env, sr=sr_lib)
        bpm_value = tempo_values[0] if isinstance(tempo_values, np.ndarray) and tempo_values.size > 0 else None
        if bpm_value is not None: return round(float(bpm_value))
        return None
    except Exception as e:
        print(f"[BPM TrainingServ ОШИБКА] Анализ BPM для {file_path}: {e}")
        return None
    finally:
        if tmp_wav and os.path.exists(tmp_wav):
            try: os.remove(tmp_wav)
            except OSError as e_rem: print(f"[BPM TrainingServ ОШИБКА] Удаление {tmp_wav}: {e_rem}")

def get_music_by_bpm(target_bpm: int = 120, tolerance: int = 20) -> tuple[str | None, int | None]:
    if not FFMPEG_OK: speak("Анализ BPM недоступен (FFmpeg не настроен)."); return None, None
    if not os.path.exists(MUSIC_FOLDER) or not os.path.isdir(MUSIC_FOLDER):
        speak(f"Папка музыки '{MUSIC_FOLDER}' не найдена."); return None, None
    
    candidates = []; speak("Ищу подходящую музыку для тренировки..."); found_audio_files = False
    for track_filename in os.listdir(MUSIC_FOLDER):
        full_path = os.path.join(MUSIC_FOLDER, track_filename)
        if track_filename.lower().endswith((".mp3", ".wav")) and os.path.isfile(full_path):
            found_audio_files = True; bpm = analyze_bpm(full_path)
            if bpm and abs(bpm - target_bpm) <= tolerance: candidates.append((full_path, bpm))
            if not FFMPEG_OK: speak("Проблема с FFmpeg прервала поиск музыки."); return None, None
    if not found_audio_files: speak(f"В '{MUSIC_FOLDER}' не найдено музыкальных файлов .mp3 или .wav."); return None, None
    if candidates:
        selected_track = min(candidates, key=lambda x: abs(x[1] - target_bpm))
        speak(f"Найдена музыка: {os.path.basename(selected_track[0])} (~{selected_track[1]} BPM).")
        return selected_track[0], selected_track[1]
    speak(f"Музыка с темпом примерно {target_bpm} BPM (+/- {tolerance}) не найдена."); return None, None

def init_training_mixer() -> bool:
    global mixer_initialized_training
    if not mixer_initialized_training:
        try:
            pygame.mixer.init(); mixer_initialized_training = True
            print("[TrainingServ Музыка] Pygame mixer для тренировок успешно инициализирован.")
        except pygame.error as e:
            print(f"[TrainingServ Музыка ОШИБКА] Инициализация mixer: {e}")
    return mixer_initialized_training

def play_training_music(filepath: str) -> bool:
    if not mixer_initialized_training:
        if not init_training_mixer(): speak("Музыкальный плеер для тренировки не работает."); return False
    if not os.path.exists(filepath):
        print(f"[TrainingServ Музыка ОШИБКА] Музыкальный файл не найден: {filepath}"); return False
    try:
        pygame.mixer.music.load(filepath); pygame.mixer.music.play(-1) # -1 для бесконечного повторения
        print(f"[TrainingServ Музыка] Воспроизведение: {os.path.basename(filepath)}")
        return True
    except pygame.error as e:
        print(f"[TrainingServ Музыка ОШИБКА] Воспроизведение: {e}"); return False

def stop_training_music():
    if mixer_initialized_training and pygame.mixer.get_init() and pygame.mixer.music.get_busy():
        pygame.mixer.music.stop(); pygame.mixer.music.unload()
        print("[TrainingServ Музыка] Музыка для тренировки остановлена и выгружена.")


def explain_exercise(exercise_name_key: str):
    full_description = EXERCISES.get(exercise_name_key.lower(), f"Описание для '{exercise_name_key}' не найдено.")
    short_description = full_description
    # Пытаемся извлечь более короткое описание (например, после двоеточия, если оно есть, или первое предложение)
    if ":" in full_description:
        parts = full_description.split(':', 1)
        if len(parts) > 1 and parts[1].strip(): # Если есть текст после двоеточия
            short_description = parts[1].strip()
            if "." in short_description: # Берем первое предложение из этого текста
                short_description = short_description.split('.', 1)[0].strip() + "."
    elif "." in full_description: # Если нет двоеточия, но есть точка, берем первое предложение
        short_description = full_description.split('.', 1)[0].strip() + "."
    
    # Если короткое описание получилось слишком коротким, используем полное
    if len(short_description) < 25 and len(short_description) < len(full_description):
        speak(full_description)
    else:
        speak(short_description)

def can_train_outside(weather_conditions: dict, user_profile: dict) -> tuple[bool, list[str]]:
    # ... (код этой функции остается без изменений, как в предыдущем ответе)
    aqi_known_and_good = False; aqi_text = weather_conditions.get("aqi_text", "неизвестно")
    valid_aqi_texts = ["неизвестно", "не удалось определить", "неизвестно (сервер)", "неизвестно (публ.)",
                       "координаты для AQI не найдены", "индекс EPA неизв.", "индекс OWM неизв.",
                       "не удалось определить (сервер)", "не удалось определить OWM (сервер)",
                       "нет данных AQI", "aqi нет данных", "нет данных AQI для прогноза",
                       "не удалось определить AQI (OWM)", "N/A (публ.)", "N/A"]
    aqi_value_from_weather = weather_conditions.get("aqi_value")
    if aqi_value_from_weather is not None and isinstance(aqi_value_from_weather, (int, float)) and aqi_text not in valid_aqi_texts :
        aqi_source = weather_conditions.get("aqi_source","")
        if "WeatherAPI" in aqi_source: aqi_known_and_good = aqi_value_from_weather <= 2
        elif "OpenWeatherMap" in aqi_source: aqi_known_and_good = aqi_value_from_weather <= 2
    default_temp = 20.0
    temp_c_val = weather_conditions.get("temp_c", weather_conditions.get("max_t", default_temp))
    try: temp_c_float = float(temp_c_val if temp_c_val is not None else default_temp)
    except (ValueError, TypeError): temp_c_float = default_temp
    temp_ok = 5 <= temp_c_float <= 30
    try: precip_float = float(weather_conditions.get("precip_mm", 0.0))
    except (ValueError, TypeError): precip_float = 0.0
    rain_ok = precip_float <= 0.1 # Допускаем очень мелкий дождь/морось
    try: wind_float = float(weather_conditions.get("wind_kph", 0.0))
    except (ValueError, TypeError): wind_float = 0.0
    wind_ok = wind_float < 35
    overall_weather_ok = temp_ok and rain_ok and wind_ok; final_decision = overall_weather_ok
    reasons_indoors = []
    if not overall_weather_ok:
        if not temp_ok: reasons_indoors.append(f"температура ({temp_c_float:.0f}°C)")
        if not rain_ok: reasons_indoors.append("осадки")
        if not wind_ok: reasons_indoors.append(f"сильный ветер ({wind_float:.0f} км/ч)")
    if aqi_value_from_weather is not None and aqi_text not in valid_aqi_texts:
        if not aqi_known_and_good: final_decision = False; reasons_indoors.append(f"качество воздуха ({aqi_text})")
    elif aqi_text not in ["хорошее", "умеренное", "удовлетворительное"] and aqi_text not in valid_aqi_texts:
        final_decision = False; reasons_indoors.append(f"качество воздуха ({aqi_text})")
    health = user_profile.get("health_issues", [])
    if "breathing" in health and (not aqi_known_and_good and aqi_value_from_weather is not None and aqi_text not in valid_aqi_texts):
        final_decision = False
        if not any("дыхания" in r for r in reasons_indoors):
             reasons_indoors.append(f"качество воздуха (критично для дыхания, текущее: {aqi_text})")
    if "heart" in health and not temp_ok:
        final_decision = False
        if not any("сердца" in r for r in reasons_indoors):
             reasons_indoors.append("погодные условия (критично для сердца)")
    return final_decision, list(set(reasons_indoors))

def get_training_recommendation_and_run(user_profile: dict, weather_conditions: dict):
    age = user_profile.get("age", 30); weight = user_profile.get("weight"); height = user_profile.get("height")
    if weight is None or height is None: speak("Нет данных о весе/росте для ИМТ."); return
    try:
        _ , bmi_category = calculate_bmi(float(weight), float(height))
    except (ValueError, TypeError, ZeroDivisionError) as e: speak(f"Ошибка ИМТ ({e}). Проверьте профиль."); return

    intensity = "средняя"; bpm_target = 120
    if "дефицит" in bmi_category.lower(): intensity = "низкая"; bpm_target = 100
    elif "ожирение" in bmi_category.lower() or "предожирение" in bmi_category.lower():
        intensity = "низкая"; bpm_target = 100
        if "2" in bmi_category or "3" in bmi_category:
            speak("Значительное ожирение. Рекомендую консультацию врача."); intensity = "очень низкая, ходьба"; bpm_target = 90
    if age > 65: intensity = "очень низкая"; bpm_target = max(90, bpm_target - 30)
    elif age > 50: intensity = "низкая"; bpm_target = max(100, bpm_target - 20)

    health_issues = user_profile.get("health_issues", []); aqi_text_fw = weather_conditions.get("aqi_text", "неизвестно")
    aqi_val = weather_conditions.get("aqi_value"); aqi_src = weather_conditions.get("aqi_source", "")
    is_aqi_bad = False
    if aqi_val is not None and isinstance(aqi_val, (int, float)):
        if "WeatherAPI" in aqi_src and aqi_val >= 3: is_aqi_bad = True
        elif "OpenWeatherMap" in aqi_src and aqi_val >= 3: is_aqi_bad = True

    if "heart" in health_issues:
        speak("ВНИМАНИЕ: проблемы с сердцем! Активность только по согласованию с врачом!"); intensity = "по назначению врача"; bpm_target = 80
    if "breathing" in health_issues and is_aqi_bad:
        speak(f"ВНИМАНИЕ: проблемы с дыханием и воздух '{aqi_text_fw}'. Осторожно!");
        if intensity != "по назначению врача": intensity = "очень низкая"; bpm_target = max(90, bpm_target - 10)

    speak(f"Рекомендуемая интенсивность: {intensity}.")
    if "врача" in intensity: speak("Следуйте рекомендациям врача."); return

    # Адаптируйте эти ключи под ваш EXERCISES в config.py!
    selected_exercises_keys = []
    if "очень низкая" in intensity:
        selected_exercises_keys = ["приседания_с_опорой_на_стул", "отжимания_от_стены", "планка_на_коленях_и_предплечьях"]
    elif "низкая" in intensity:
        selected_exercises_keys = ["приседания_классические", "отжимания_с_колен", "планка_классическая"]
    else: # Средняя интенсивность
        selected_exercises_keys = ["прыжки_на_месте", "приседания_классические", "отжимания_классические", "планка_классическая"]
        
    speak("Разминка: 3-5 минут легкой ходьбы и вращений суставами. Пожалуйста, выполните самостоятельно."); time.sleep(1)
    
    music_file, music_bpm = get_music_by_bpm(bpm_target)
    
    for ex_idx, ex_key_from_list in enumerate(selected_exercises_keys):
        current_ex_key = ex_key_from_list.lower()

        if current_ex_key not in EXERCISES:
            speak(f"Упражнение с ключом '{current_ex_key}' не найдено. Пропускаю.")
            continue
        
        exercise_title = EXERCISES[current_ex_key].split(':')[0].split('.')[0].strip()
        speak(f"Следующее упражнение: {exercise_title}.")
        explain_exercise(current_ex_key)
        
        speak("Готовы начать это упражнение?")
        user_response = listen_input(timeout=12, phrase_time_limit=5)
        if user_response == "нет":
            speak("Упражнение пропущено.")
            # Не останавливаем музыку здесь, чтобы она могла продолжаться, если пользователь пропустил упражнение,
            # но хочет продолжить тренировку со следующего под ту же музыку.
            continue

        ex_duration = 15 # секунд
        if "низкая" in intensity: ex_duration = 12
        if "очень низкая" in intensity: ex_duration = 10
        if "планка" in current_ex_key:
            ex_duration = 20 if intensity == "средняя" else (15 if "низкая" in intensity else 10)
        
        # Запуск музыки (если еще не играет) и выполнение
        speak_parts_before_ex = []
        music_should_play_now = False
        if music_file:
            if not pygame.mixer.music.get_busy(): # Если музыка не играет
                speak_parts_before_ex.append(f"Включаю музыку ({os.path.basename(music_file)}, ~{music_bpm} BPM).")
                music_should_play_now = True
            # else: # Если музыка уже играет, ничего не говорим о ней дополнительно
            #    speak_parts_before_ex.append("Продолжаем с музыкой.")
        # else: # Если музыки нет
        #    speak_parts_before_ex.append("Музыка не найдена.") # Сообщение об этом было ранее
        
        speak_parts_before_ex.append(f"Выполняйте {ex_duration} секунд. Начали!")
        speak(" ".join(speak_parts_before_ex))

        if music_should_play_now:
            if not play_training_music(music_file):
                 speak("Не удалось включить музыку. Выполняйте без нее.")
        
        # Цикл выполнения упражнения
        start_exercise_time = time.time()
        while time.time() - start_exercise_time < ex_duration:
            # Можно добавить проверку команды "стоп"
            time.sleep(0.2)

        # Музыка останавливается ПОСЛЕ КАЖДОГО упражнения, перед отдыхом/следующим объяснением
        if pygame.mixer.music.get_busy():
            stop_training_music()

        speak("Время вышло! Отлично!")
        
        if ex_idx < len(selected_exercises_keys) - 1:
            speak("Короткий отдых, 15-20 секунд. Подготовьтесь к следующему упражнению.")
            time.sleep(18)
    
    # Убедимся, что музыка остановлена в конце всей тренировки
    if pygame.mixer.music.get_busy():
        stop_training_music()
    speak("Основная часть тренировки окончена. Не забудьте сделать заминку: легкую растяжку.")

# --- Точка входа в модуль тренировок ---
def handle_start_training_session_request(user_profile: dict, weather_data_for_training: dict | None):
    """
    Обрабатывает запрос на начало тренировочной сессии.
    Сначала получает или формирует данные о погоде, затем предлагает тренировку.
    """
    # Поздние импорты, чтобы избежать циклических зависимостей, если они есть
    from .profile_manager import save_user_profile, get_numeric_input_from_user, validate_weight

    if not user_profile:
        speak("Ошибка: Профиль пользователя не предоставлен для начала тренировки.")
        return

    if not weather_data_for_training:
        speak("Не удалось получить данные о погоде для адаптации тренировки. Начать стандартную тренировку в помещении?")
        if listen_input(timeout_param=10, phrase_time_limit_param=5) != "да":
            speak("Тренировка отменена.")
            return
        weather_data_for_training = {
            "city_resolved": user_profile.get("city", "неизвестно"), "temp_c": 20.0,
            "condition_text": "ясно (в помещении)", "aqi_text": "хорошее (в помещении)",
            "precip_mm": 0.0, "wind_kph": 0.0, "requested_date": datetime.now().strftime('%Y-%m-%d'),
            "aqi_value": 1, "aqi_source": "Mock", "min_t": 18.0, "max_t": 22.0,
            "humidity": 50.0, "is_day": 1
        }
    
    city_display = weather_data_for_training.get('city_resolved', user_profile.get('city','вашем городе'))
    speak_w_parts = [f"Условия для тренировки в городе {city_display}: {weather_data_for_training.get('condition_text','нет данных')}."]
    temp_c_report = weather_data_for_training.get("temp_c")
    if temp_c_report is not None : speak_w_parts.append(f"Температура {temp_c_report:.1f}°C.")
    aqi_report = weather_data_for_training.get('aqi_text', 'неизвестно')
    non_informative_aqi = ["неизвестно", "нет данных AQI", "aqi нет данных", "N/A",
                           "не удалось определить", "неизвестно (сервер)", "неизвестно (публ.)"]
    if aqi_report not in non_informative_aqi:
        speak_w_parts.append(f"Качество воздуха: {aqi_report}.")
    speak(" ".join(speak_w_parts))

    speak("Продолжить подготовку к тренировке?")
    if listen_input(timeout=12, phrase_time_limit=5) != "да":
        speak("Подготовка к тренировке отменена.")
        return
    
    can_train_out, reasons_indoors = can_train_outside(weather_data_for_training, user_profile)
    if can_train_out: speak("Погодные условия сегодня благоприятны для тренировки на улице.")
    else:
        reasons_str = f" Основные причины: {', '.join(reasons_indoors)}." if reasons_indoors else ""
        speak(f"Учитывая текущие условия, рекомендую сегодня тренироваться в помещении.{reasons_str}")
            
    get_training_recommendation_and_run(user_profile, weather_data_for_training) # Эта функция вызывает speak и listen_input
    
    # Обновление веса после тренировки
    speak("Хотите обновить свой вес в профиле после тренировки?")
    if listen_input(timeout_param=10, phrase_time_limit_param=5) == "да":
        current_weight_val = user_profile.get('weight')
        default_weight_for_function: float | int | None = None # Для передачи в default_value
        if current_weight_val is not None:
            try:
                default_weight_for_function = float(current_weight_val)
            except ValueError:
                pass # Оставляем None, если не можем сконвертировать

        # --- ИСПРАВЛЕННЫЙ ВЫЗОВ ---
        # Передаем сообщение как первый позиционный аргумент.
        # default_value передаем как именованный, если функция его так ожидает.
        # Если default_value тоже позиционный, то:
        # new_weight_str = get_numeric_input_from_user("Назовите ваш текущий вес в килограммах:", default_weight_for_function)
        new_weight_str = get_numeric_input_from_user(
            "Назовите ваш текущий вес в килограммах:", # Это будет первый позиционный аргумент (prompt_for_user)
            default_value=default_weight_for_function  # Это именованный аргумент (если он так определен)
            # Если в get_numeric_input_from_user есть еще именованные параметры (например, для listen_input),
            # их можно добавить сюда: timeout_listen=10, phrase_limit_listen=5 и т.д.
        )
        # --- КОНЕЦ ИСПРАВЛЕННОГО ВЫЗОВА ---

        if new_weight_str is not None:
            valid_weight = validate_weight(new_weight_str)
            if valid_weight is not None:
                user_profile["weight"] = valid_weight
                if save_user_profile(user_profile):
                    speak(f"Ваш вес успешно обновлен в профиле: {user_profile['weight']}кг.")
                else:
                    speak("Не удалось сохранить обновленный вес в профиле.")
            else:
                speak("Введено некорректное значение веса. Вес не обновлен.")
        else:
            speak("Ввод веса отменен или не был распознан.")