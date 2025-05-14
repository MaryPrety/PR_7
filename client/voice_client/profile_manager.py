# client/voice_client/profile_manager.py
import os
import json
import time
from typing import Callable 

from .config import USERS_DIR
from .tts_stt import speak, listen_input
from .utils import validate_height, validate_weight, validate_age, calculate_bmi

def load_users() -> list[dict]:
    if not os.path.exists(USERS_DIR):
        try:
            os.makedirs(USERS_DIR)
            print(f"[Профили] Создана директория: {USERS_DIR}")
            return []
        except OSError as e:
            print(f"[Профили] Ошибка создания директории {USERS_DIR}: {e}")
            return []

    loaded_profiles = []
    for filename in os.listdir(USERS_DIR):
        if filename.lower().endswith(".json"):
            filepath = os.path.join(USERS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                if isinstance(user_data, dict) and user_data.get("name") and \
                   isinstance(user_data["name"], str) and user_data["name"].strip():
                    loaded_profiles.append(user_data)
                else:
                    print(f"[Профили] Файл {filename} не содержит валидных данных профиля.")
            except json.JSONDecodeError:
                print(f"[Профили] Ошибка декодирования JSON в {filename}.")
            except Exception as e:
                print(f"[Профили] Не удалось загрузить {filename}: {e}")
    return loaded_profiles

def generate_safe_filename(name: str) -> str:
    safe_name = "".join(c if c.isalnum() or c in [' ', '_', '-'] else '' for c in name).strip()
    safe_name = safe_name.replace(' ', '_').lower()
    if not safe_name:
        safe_name = f'unnamed_profile_{int(time.time())}'
    return f"{safe_name}.json"

def save_user_profile(user_profile_data: dict) -> bool:
    if not isinstance(user_profile_data, dict) or not user_profile_data.get("name", "").strip():
        speak("Ошибка: попытка сохранить профиль без имени или с некорректными данными.")
        return False
    if not os.path.exists(USERS_DIR):
        try: os.makedirs(USERS_DIR)
        except OSError as e:
            speak(f"Критическая ошибка: не удалось создать папку профилей: {e}")
            return False
    filename = generate_safe_filename(user_profile_data["name"])
    filepath = os.path.join(USERS_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(user_profile_data, f, ensure_ascii=False, indent=4)
        print(f"[Профили] Профиль '{user_profile_data['name']}' сохранен в: {filepath}")
        return True
    except Exception as e:
        speak(f"Не удалось сохранить профиль {user_profile_data.get('name')}.")
        print(f"[Профили Ошибка] Сохранение {filepath}: {e}")
        return False

def delete_profile_file(user_name: str) -> bool:
    if not user_name: return False
    filename = generate_safe_filename(user_name)
    filepath = os.path.join(USERS_DIR, filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"[Профили] Файл профиля {filepath} удален.")
            return True
        except Exception as e:
            print(f"[Профили Ошибка] Не удалось удалить {filepath}: {e}")
            return False
    return True

def get_numeric_input_from_user(
    prompt_text: str,
    default_value_str: str | None = None,
    max_attempts: int = 3,
    timeout_listen: int = 10, # Параметры для listen_input
    phrase_limit_listen: int = 7
) -> str | None:
    full_prompt = prompt_text
    if default_value_str is not None:
        full_prompt += f" (Текущее значение: {default_value_str}. Скажите новое или 'оставить')"
    
    for attempt in range(max_attempts):
        speak(full_prompt if attempt == 0 else prompt_text)
        # Передаем параметры listen_input с правильными именами
        user_input_str = listen_input(timeout=timeout_listen, phrase_time_limit=phrase_limit_listen)

        if not user_input_str:
            if default_value_str and attempt == 0:
                speak(f"Ввод не получен. Оставить {default_value_str}?")
                if listen_input(timeout=7, phrase_time_limit=5) == "да": # Короткий таймаут для да/нет
                    return default_value_str
            speak("Ввод не получен. Попробуйте еще раз.")
            continue
        if default_value_str and user_input_str.lower() in ["оставить", "такой же", "не менять"]:
            speak(f"Хорошо, оставляем: {default_value_str}.")
            return default_value_str
        try:
            float(user_input_str.replace(',', '.'))
            return user_input_str.replace(',', '.')
        except ValueError:
            speak("Это не похоже на число. Введите числовое значение.")
            if attempt < max_attempts - 1 and default_value_str:
                 speak(f"Напомню, текущее: {default_value_str}.")
    speak("Превышено количество попыток. Действие отменено.")
    return None

def register_new_user_interaction(
    existing_profile_data: dict | None = None
) -> dict | None:
    profile_data = existing_profile_data.copy() if existing_profile_data else {}
    is_editing = bool(existing_profile_data)
    original_name_for_file_deletion = profile_data.get("name") if is_editing else None

    action_text = "Редактирование профиля" if is_editing else "Создание нового профиля"
    speak(f"{action_text}. Давайте пройдемся по основным пунктам.")

    # --- Имя ---
    current_name = profile_data.get("name", "")
    prompt_name_text = f"Текущее имя: {current_name}. Хотите изменить?" if is_editing and current_name else "Как вас зовут?"
    speak(prompt_name_text)
    
    # Для да/нет ответа на "Хотите изменить?"
    change_decision_input = ""
    if is_editing and current_name:
        change_decision_input = listen_input(timeout=7, phrase_time_limit=5)

    if not (is_editing and current_name) or change_decision_input == "да":
        speak("Назовите ваше имя:") # ИСПРАВЛЕНИЕ: speak() перед listen_input()
        new_name_input = listen_input(timeout=10, phrase_time_limit=10)
        if new_name_input and new_name_input.strip():
            profile_data["name"] = new_name_input.strip().capitalize()
        elif not current_name: # Если создаем новый и имя не введено
            speak("Имя не может быть пустым. Регистрация отменена.")
            return None
    if not profile_data.get("name"): speak("Имя осталось пустым. Регистрация отменена."); return None

    # --- Рост ---
    current_height_str = str(profile_data.get("height")) if profile_data.get("height") is not None else None
    profile_data["height"] = validate_height(
        get_numeric_input_from_user(
            prompt_text="Ваш рост (в сантиметрах)?", 
            default_value_str=current_height_str
        )
    )
    if profile_data["height"] is None and "height" not in profile_data: # Если ввод не удался и не было старого значения
        speak("Рост не указан корректно. Пожалуйста, укажите для расчета ИМТ."); return None

    # --- Вес ---
    current_weight_str = str(profile_data.get("weight")) if profile_data.get("weight") is not None else None
    weight_input_str = get_numeric_input_from_user(
        prompt_text="Ваш текущий вес (в килограммах)?",
        default_value_str=current_weight_str
    )
    weight_val = validate_weight(weight_input_str)
    if weight_val is not None:
        profile_data["weight"] = weight_val
        if not is_editing or "initial_weight" not in profile_data:
            profile_data["initial_weight"] = weight_val
    elif "weight" not in profile_data:
        speak("Вес не указан корректно. Пожалуйста, укажите для расчета ИМТ."); return None

    if "goal_weight" not in profile_data: profile_data["goal_weight"] = None

    # --- Возраст ---
    current_age_str = str(profile_data.get("age")) if profile_data.get("age") is not None else None
    profile_data["age"] = validate_age(
        get_numeric_input_from_user(
            prompt_text="Сколько вам полных лет?",
            default_value_str=current_age_str
        )
    )
    # Возраст может быть None, не прерываем

    # --- Город ---
    current_city = profile_data.get("city", "Москва")
    speak(f"Ваш город для погоды и новостей. Текущий: {current_city}. Хотите изменить?")
    if listen_input(timeout=7, phrase_time_limit=5) == "да":
        speak("Назовите город:") # ИСПРАВЛЕНИЕ
        city_input_val = listen_input(timeout=10, phrase_time_limit=10)
        if city_input_val and city_input_val.strip():
            profile_data["city"] = city_input_val.strip().capitalize()
    elif "city" not in profile_data:
         profile_data["city"] = current_city

    # --- Проблемы со здоровьем ---
    if "health_issues" not in profile_data: profile_data["health_issues"] = []
    speak("Теперь несколько вопросов о здоровье. Отвечайте 'да' или 'нет'.")
    
    updated_issues = []
    health_questions = {
        "allergies": "серьезные аллергии, влияющие на активность на улице",
        "breathing": "проблемы с дыханием, например, астма",
        "heart": "известные проблемы с сердцем",
        "joints": "проблемы с суставами (колени, спина), ограничивающие упражнения"
    }
    for issue_key, question_text in health_questions.items():
        speak(f"Есть ли у вас {question_text}?")
        if listen_input(timeout=7, phrase_time_limit=5) == "да": # ИСПРАВЛЕНИЕ (если тут были *param)
            updated_issues.append(issue_key)
    profile_data["health_issues"] = list(set(updated_issues))

    # --- Расчет ИМТ ---
    if profile_data.get("weight") is not None and profile_data.get("height") is not None:
        bmi_val, bmi_cat = calculate_bmi(profile_data["weight"], profile_data["height"])
        profile_data["bmi"] = round(bmi_val, 1)
        profile_data["bmi_category"] = bmi_cat
        speak(f"Ваш Индекс Массы Тела: {profile_data['bmi']:.1f}, это {bmi_cat}.")
    else:
        speak("Не удалось рассчитать ИМТ, так как вес или рост не указаны.")

    if is_editing and original_name_for_file_deletion and \
       original_name_for_file_deletion.lower() != profile_data.get("name", "").lower():
        delete_profile_file(original_name_for_file_deletion)

    if save_user_profile(profile_data):
        speak(f"Профиль для {profile_data['name']} успешно {'обновлен' if is_editing else 'создан'}.")
        return profile_data
    else:
        # save_user_profile уже озвучит ошибку
        return None

def choose_user(
    users_list: list[dict],
    prompt_message: str = "Выберите пользователя",
    current_profile_to_exclude: dict | None = None
) -> dict | None:
    if not users_list: speak("Список профилей пуст."); return None

    available_profiles = [p for p in users_list if not (current_profile_to_exclude and p.get("name") == current_profile_to_exclude.get("name"))]
    if not available_profiles:
        speak(f"Кроме текущего профиля '{current_profile_to_exclude.get('name') if current_profile_to_exclude else ''}', других нет." if current_profile_to_exclude else "Нет доступных профилей.")
        return None

    speak(prompt_message + " Доступные профили:")
    profile_names = [p.get("name", "Безымянный") for p in available_profiles]
    for i, name in enumerate(profile_names): speak(f"{i+1} - {name}")

    if len(available_profiles) == 1:
        speak(f"Автоматически выбран: {profile_names[0]}."); return available_profiles[0]

    speak("Назовите номер или имя профиля:") # ИСПРАВЛЕНИЕ
    user_choice_input = listen_input(timeout=10, phrase_time_limit=7)
    if not user_choice_input: speak("Выбор не сделан."); return None

    if user_choice_input.isdigit():
        try:
            idx = int(user_choice_input) - 1
            if 0 <= idx < len(available_profiles):
                speak(f"Выбран: {available_profiles[idx].get('name')}."); return available_profiles[idx]
            else: speak("Некорректный номер."); return None
        except ValueError: pass
    
    choice_lower = user_choice_input.lower()
    for p in available_profiles:
        if p.get("name", "").lower() == choice_lower: speak(f"Выбран: {p.get('name')}."); return p
    for p in available_profiles:
        if choice_lower in p.get("name", "").lower(): speak(f"Найден похожий: {p.get('name')}."); return p
            
    speak(f"Профиль '{user_choice_input}' не найден."); return None

def handle_profile_management_options(
    current_profile: dict,
    all_profiles: list[dict],
    select_server_func: Callable[[str | None], bool] | None = None
) -> tuple[dict | None, list[dict]]:
    speak(f"Управление профилем '{current_profile.get('name', 'Без имени')}'. Опции: информация, изменить, удалить, создать новый, переключить. Что выберете?")
    # ИСПРАВЛЕНИЕ
    choice_input = listen_input(timeout=10, phrase_time_limit=10) 
    updated_active_profile: dict | None = current_profile
    updated_all_profiles = list(all_profiles)

    if not choice_input: speak("Команда не распознана."); return updated_active_profile, updated_all_profiles
    choice_lower = choice_input.lower()

    if "информац" in choice_lower:
        speak(f"Информация о профиле {current_profile.get('name', 'Без имени')}:")
        for key, value in current_profile.items():
            if key not in ["password_hash", "salt"]:
                display_key = key.replace('_', ' ').capitalize()
                if key == "bmi": display_key = "ИМТ"
                elif key == "bmi_category": display_key = "Категория ИМТ"
                speak(f"{display_key}: {value}")

    elif "изменить" in choice_lower or "редактировать" in choice_lower:
        prev_city = current_profile.get("city"); original_name = current_profile.get("name")
        edited_profile = register_new_user_interaction(current_profile.copy())
        if edited_profile:
            updated_active_profile = edited_profile
            found = False
            for i, p in enumerate(updated_all_profiles):
                if p.get("name") == original_name: updated_all_profiles[i] = edited_profile; found = True; break
            if not found: # Если имя изменилось
                updated_all_profiles = [p for p in updated_all_profiles if p.get("name") != original_name]
                if not any(p.get("name") == edited_profile.get("name") for p in updated_all_profiles):
                    updated_all_profiles.append(edited_profile)
            if select_server_func and edited_profile.get("city") != prev_city:
                select_server_func(edited_profile.get("city"))
        # else: register_new_user_interaction уже озвучит ошибку/отмену

    elif "удалить" in choice_lower:
        updated_active_profile, updated_all_profiles = handle_delete_profile_flow(
            current_profile, updated_all_profiles, select_server_func
        )

    elif "новый" in choice_lower or "создать" in choice_lower:
        new_profile = register_new_user_interaction(None)
        if new_profile:
            new_name_lower = new_profile.get("name","").lower()
            updated_all_profiles = [p for p in updated_all_profiles if p.get("name","").lower() != new_name_lower]
            updated_all_profiles.append(new_profile)
            speak("Хотите сделать его активным?")
            if listen_input(timeout=7, phrase_time_limit=5) == "да":
                updated_active_profile = new_profile
                if select_server_func: select_server_func(updated_active_profile.get("city"))
            # else: register_new_user_interaction уже озвучит создание
    
    elif "переключить" in choice_lower or "сменить" in choice_lower:
        if len(updated_all_profiles) <= 1:
            speak("Нет других профилей." if updated_all_profiles else "Список пуст.")
        else:
            chosen = choose_user(updated_all_profiles, "На какой профиль переключиться?", current_profile)
            if chosen:
                updated_active_profile = chosen
                if select_server_func: select_server_func(updated_active_profile.get("city"))
    else:
        speak("Не поняла ваш выбор для управления профилем.")
    
    return updated_active_profile, updated_all_profiles

def handle_delete_profile_flow(
    current_profile_to_check: dict,
    all_profiles_list_ref: list[dict], # Передаем как ссылку для изменения на месте
    select_server_func: Callable[[str | None], bool] | None = None
) -> tuple[dict | None, list[dict]]:
    if not all_profiles_list_ref: speak("Нет профилей для удаления."); return current_profile_to_check, all_profiles_list_ref

    target_profile_to_delete: dict | None
    speak("Какой профиль вы хотите удалить?") # ИСПРАВЛЕНИЕ
    if len(all_profiles_list_ref) == 1:
        speak(f"Это ваш единственный профиль: {all_profiles_list_ref[0].get('name')}. Удалить?")
        target_profile_to_delete = all_profiles_list_ref[0]
    else:
        # choose_user уже озвучит промпт "Выберите профиль для удаления"
        target_profile_to_delete = choose_user(list(all_profiles_list_ref), "Выберите профиль для удаления")

    if not target_profile_to_delete: speak("Удаление отменено."); return current_profile_to_check, all_profiles_list_ref

    speak(f"Точно удалить профиль '{target_profile_to_delete.get('name')}'? (да/нет)") # ИСПРАВЛЕНИЕ
    confirmation = listen_input(timeout=10, phrase_time_limit=5)

    if "да" in confirmation.lower():
        if delete_profile_file(target_profile_to_delete.get('name',"")):
            speak(f"Профиль '{target_profile_to_delete.get('name')}' удален.")
            # Обновляем переданный по ссылке список
            all_profiles_list_ref[:] = [p for p in all_profiles_list_ref if p.get("name","").lower() != target_profile_to_delete.get("name","").lower()]
            
            if current_profile_to_check and \
               current_profile_to_check.get("name") == target_profile_to_delete.get("name"):
                # Текущий профиль удален. main_loop решит, что делать дальше.
                return None, all_profiles_list_ref 
            else: # Удален не текущий
                return current_profile_to_check, all_profiles_list_ref
        else:
            # delete_profile_file должна была озвучить ошибку
            return current_profile_to_check, all_profiles_list_ref
    else:
        speak("Удаление отменено."); return current_profile_to_check, all_profiles_list_ref