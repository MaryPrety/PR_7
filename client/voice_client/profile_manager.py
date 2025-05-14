# client/voice_client/profile_manager.py
import os
import json
import time
from .config import USERS_DIR
from .tts_stt import speak, listen_input # Убедимся, что они импортируются корректно
from .utils import validate_height, validate_weight, validate_age, calculate_bmi 

# ... (load_users, generate_safe_filename, save_user_profile, delete_profile_file, 
#      get_numeric_input_from_user, register_new_user_interaction, choose_user - 
#      КОД ЭТИХ ФУНКЦИЙ ОСТАЕТСЯ ТАКИМ ЖЕ, КАК В ПОЛНОМ ОТВЕТЕ ДЛЯ profile_manager.py
#      от "2024-01-19 02:50" или из моего последнего ответа, где был profile_manager.py. 
#      Я не буду их повторять здесь для краткости, НО ОНИ ДОЛЖНЫ БЫТЬ В ФАЙЛЕ)

# !!! КОПИРУЮ СЮДА НЕДОСТАЮЩИЕ ВЕРСИИ ЭТИХ ФУНКЦИЙ ИЗ МОЕГО ПРЕДЫДУЩЕГО ОТВЕТА !!!
def load_users() -> list[dict]:
    if not os.path.exists(USERS_DIR):
        try: os.makedirs(USERS_DIR); print(f"[Профили] Создана: {USERS_DIR}"); return []
        except OSError as e: print(f"[Профили] Ошибка {USERS_DIR}: {e}"); return []
    loaded_profiles = []
    for filename in os.listdir(USERS_DIR):
        if filename.lower().endswith(".json"):
            filepath = os.path.join(USERS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f: user_data = json.load(f)
                if "name" in user_data and user_data["name"].strip(): loaded_profiles.append(user_data)
            except Exception as e: print(f"[Профили] Ошибка {filename}: {e}")
    return loaded_profiles

def generate_safe_filename(name: str) -> str:
    safe_name = "".join(c if c.isalnum() or c in [' ', '_'] else '' for c in name.lower()).replace(' ', '_')
    return f"{safe_name or f'unnamed_profile_{int(time.time())}'}.json"

def save_user_profile(user_profile_data: dict) -> bool:
    if not user_profile_data or not user_profile_data.get("name", "").strip(): speak("Ошибка: профиль без имени."); return False
    if not os.path.exists(USERS_DIR):
        try: os.makedirs(USERS_DIR)
        except OSError as e: speak(f"Ошибка создания папки: {e}"); return False
    filepath = os.path.join(USERS_DIR, generate_safe_filename(user_profile_data["name"]))
    try:
        with open(filepath, "w", encoding="utf-8") as f: json.dump(user_profile_data, f, ensure_ascii=False, indent=4)
        print(f"[Профили] Сохранен: {filepath}"); return True
    except Exception as e: speak(f"Ошибка сохранения {user_profile_data.get('name')}."); print(f"[Профили Ошибка] {e}"); return False

def delete_profile_file(user_name: str) -> bool:
    if not user_name: return False
    filepath = os.path.join(USERS_DIR, generate_safe_filename(user_name))
    if os.path.exists(filepath):
        try: os.remove(filepath); print(f"[Профили] Файл {filepath} удален."); return True
        except Exception as e: print(f"[Профили Ошибка] Удаление {filepath}: {e}"); return False
    return True # Если файла нет, считаем "успешным" удалением

def get_numeric_input_from_user(
    prompt_for_user: str, # Первый аргумент - позиционный
    # default_value МОЖЕТ БЫТЬ именованным или отсутствовать
    default_value: float | int | str | None = None, # Если он есть и именованный
    # ... другие параметры ...
    timeout_listen: int = 10, # Пример других именованных параметров
    phrase_limit_listen: int = 5
) -> str | None:
    speak(f"{prompt_for_user} (По умолчанию: {default_value})" if default_value is not None else prompt_for_user)
    user_input_text = listen_input(timeout_param=timeout_listen, phrase_time_limit_param=phrase_limit_listen)
    if not user_input_text and default_value is not None:
        return str(default_value) # Возвращаем строку, как и при вводе пользователя
    # ... (дальнейшая валидация, если есть, или просто возврат строки)
    return user_input_text

def register_new_user_interaction(existing_profile_data: dict | None = None) -> dict | None:
    profile = existing_profile_data.copy() if existing_profile_data else {}
    is_editing = bool(existing_profile_data); old_name = profile.get("name") if is_editing else None
    speak(f"Редактирование профиля {old_name}." if is_editing else "Создаем новый профиль. Ваше имя?")
    name = profile.get("name", "")
    if not is_editing or (is_editing and listen_input(f"Имя: {name}. Изменить?", timeout=5) == "да"):
        name_new = listen_input("Новое имя:", timeout=10)
        if name_new: name = name_new.strip().capitalize()
        elif not name : speak("Имя не может быть пустым."); return None
    profile["name"] = name
    if not profile["name"]: speak("Имя пустое."); return None
    # ... (дальнейшая логика для роста, веса, возраста, города, здоровья - как в ПОЛНОМ файле profile_manager.py, который я давал)
    current_height = profile.get("height") # Копирую оставшуюся часть
    question = f"Ваш рост {current_height} см. Изменить?" if is_editing and current_height is not None else f"{profile['name']}, ваш рост (см)?"
    speak(question)
    if not is_editing or (is_editing and current_height is None) or listen_input(timeout=5) == "да": profile["height"] = validate_height(get_numeric_input_from_user("Рост (см):", default_value=current_height if is_editing else 170))
    current_weight = profile.get("weight")
    question = f"Ваш вес {current_weight} кг. Изменить?" if is_editing and current_weight is not None else "Ваш вес (кг)?"
    speak(question)
    if not is_editing or (is_editing and current_weight is None) or listen_input(timeout=5) == "да":
        new_weight_val = validate_weight(get_numeric_input_from_user("Вес (кг):", default_value=current_weight if is_editing else 60))
        if not is_editing or profile.get("initial_weight") is None: profile["initial_weight"] = new_weight_val
        profile["weight"] = new_weight_val
    if "goal_weight" not in profile: profile["goal_weight"]=None 
    current_age = profile.get("age")
    question = f"Ваш возраст {current_age} лет. Изменить?" if is_editing and current_age is not None else "Полных лет?"
    speak(question)
    if not is_editing or (is_editing and current_age is None) or listen_input(timeout=5) == "да": profile["age"] = validate_age(get_numeric_input_from_user("Возраст:", default_value=current_age if is_editing else 30))
    current_city = profile.get("city", "Москва")
    question = f"Ваш город {current_city}. Изменить?" if is_editing else "Город (погода, новости)?"
    speak(question)
    if not is_editing or listen_input(timeout=5) == "да":
        city_input_val = listen_input("Назовите город.",timeout=10); profile["city"] = city_input_val.strip().capitalize() if city_input_val else current_city
    if "health_issues" not in profile: profile["health_issues"] = []
    if not is_editing or not profile["health_issues"]: 
        speak("Вопросы о здоровье (да/нет).")
        if listen_input("Аллергии?",timeout=5) == "да" and "allergies" not in profile["health_issues"]: profile["health_issues"].append("allergies")
        if listen_input("Проблемы с дыханием/астма?",timeout=5) == "да" and "breathing" not in profile["health_issues"]: profile["health_issues"].append("breathing")
        if listen_input("Проблемы с сердцем?",timeout=5) == "да" and "heart" not in profile["health_issues"]: profile["health_issues"].append("heart")
    profile["bmi"], profile["bmi_category"] = calculate_bmi(profile["weight"],profile["height"])
    if is_editing and old_name and old_name.lower() != profile["name"].lower(): delete_profile_file(old_name)
    if save_user_profile(profile): speak(f"Профиль {profile['name']} {'обновлен' if is_editing else 'создан'}. ИМТ {profile['bmi']:.1f} ({profile['bmi_category']})."); return profile
    speak(f"Не удалось сохранить профиль {profile['name']}."); return None

def choose_user(users_list: list[dict], prompt_message: str = "Выберите пользователя") -> dict | None: # Как было
    if not users_list: speak("Список пуст."); return None
    speak(prompt_message + ". Доступные:"); names=[p.get("name","?") for p in users_list]
    for i, n in enumerate(names): speak(f"{i+1}-{n}")
    if len(users_list)==1: speak(f"Выбран: {names[0]}."); return users_list[0]
    choice = listen_input("Номер или имя?", timeout=10)
    if not choice: speak(f"По умолч.: {names[0]}."); return users_list[0]
    if choice.isdigit():
        idx = int(choice)-1
        if 0<=idx<len(users_list): speak(f"Выбран: {names[idx]}."); return users_list[idx]
    for p in users_list: 
        if p.get("name","").lower() == choice.lower(): speak(f"Выбран: {p['name']}."); return p
    for p in users_list:
        if choice.lower() in p.get("name","").lower(): speak(f"Найден: {p['name']}."); return p
    speak(f"Не найден. По умолч.: {names[0]}."); return users_list[0]
# --- КОНЕЦ КОПИРОВАНИЯ ---


# --- НОВАЯ ФУНКЦИЯ для обработки подменю профиля ---
def handle_profile_management_options(current_profile: dict, all_profiles_list: list[dict]) -> dict | None:
    """
    Предоставляет пользователю опции управления профилем и обрабатывает выбор.
    Возвращает обновленный/выбранный current_profile или None, если все профили удалены.
    """
    from .main_loop import select_server_for_user_region # Поздний импорт для избежания цикла

    speak(f"Управление профилем '{current_profile['name']}'. Вы можете: "
          "изменить текущий профиль, удалить профиль, создать новый, или переключиться на другой. "
          "Что бы вы хотели сделать?")
    
    choice = listen_input(timeout=10, phrase_limit=15)
    newly_selected_or_updated_profile = current_profile # По умолчанию

    if "изменить" in choice:
        speak("Редактируем текущий профиль.")
        edited_profile = register_new_user_interaction(existing_profile_data=current_profile)
        if edited_profile:
            # Обновляем профиль в общем списке
            all_profiles_list[:] = [edited_profile if p.get("name") == current_profile.get("name") else p for p in all_profiles_list]
            # Если имя было изменено, старый объект может остаться, если имя файла другое. Чистим.
            if current_profile.get("name") != edited_profile.get("name"):
                all_profiles_list[:] = [p for p in all_profiles_list if p.get("name") != current_profile.get("name")]
                # Добавляем отредактированный, если его там еще нет (из-за смены имени)
                if not any(p.get("name") == edited_profile.get("name") for p in all_profiles_list):
                    all_profiles_list.append(edited_profile)


            newly_selected_or_updated_profile = edited_profile
            if newly_selected_or_updated_profile.get("city") != current_profile.get("city"):
                 select_server_for_user_region(newly_selected_or_updated_profile.get("city", "Москва"))


    elif "удалить" in choice:
        # Эта функция сама обрабатывает выбор, подтверждение и обновление all_profiles_list
        newly_selected_or_updated_profile = handle_delete_profile_flow(current_profile, all_profiles_list)

    elif "новый" in choice or "создать" in choice:
        new_profile = register_new_user_interaction()
        if new_profile:
            # Удаляем старый с таким же именем, если вдруг был, и добавляем новый
            all_profiles_list[:] = [p for p in all_profiles_list if p.get("name","").lower() != new_profile.get("name","").lower()]
            all_profiles_list.append(new_profile)
            speak(f"Профиль для {new_profile['name']} создан. Хотите переключиться на него?")
            if listen_input(timeout=7) == "да":
                newly_selected_or_updated_profile = new_profile
                select_server_for_user_region(newly_selected_or_updated_profile.get("city", "Москва"))

    elif "переключиться" in choice or "выбрать другой" in choice:
        if len(all_profiles_list) > 1:
            chosen_user = choose_user(all_profiles_list, "На какой профиль вы хотите переключиться?")
            if chosen_user and chosen_user.get("name") != current_profile.get("name"):
                newly_selected_or_updated_profile = chosen_user
                select_server_for_user_region(newly_selected_or_updated_profile.get("city", "Москва"))
            elif chosen_user:
                speak(f"Профиль '{chosen_user.get('name')}' уже активен.")
        elif len(all_profiles_list) == 1:
            speak("У вас только один профиль. Не на что переключаться.")
        else: # all_profiles_list пуст (маловероятно здесь, но для полноты)
             speak("Нет доступных профилей для переключения.")


    else:
        speak("Не совсем поняла ваш выбор для управления профилем. Возвращаемся в главное меню.")
    
    return newly_selected_or_updated_profile


def handle_delete_profile_flow(current_profile_to_check_if_deleted: dict, all_profiles_list_ref: list[dict]) -> dict | None:
    """ Логика выбора профиля для удаления и последующих действий. """
    from .main_loop import select_server_for_user_region # Поздний импорт

    if not all_profiles_list_ref:
        speak("Нет профилей для удаления."); return current_profile_to_check_if_deleted

    target_profile_to_delete = None
    if len(all_profiles_list_ref) == 1:
        speak(f"У вас только один профиль: {all_profiles_list_ref[0]['name']}. Вы уверены, что хотите его удалить? "
              "После этого нужно будет создать новый.")
        target_profile_to_delete = all_profiles_list_ref[0]
    else:
        speak("Какой профиль вы хотите удалить?")
        target_profile_to_delete = choose_user(list(all_profiles_list_ref), "Выберите профиль для удаления") # list() для копии

    if not target_profile_to_delete:
        speak("Удаление отменено."); return current_profile_to_check_if_deleted

    speak(f"Вы точно хотите удалить профиль '{target_profile_to_delete['name']}'? Это действие необратимо. (да/нет)")
    confirmation = listen_input(timeout=10)

    if "да" in confirmation:
        if delete_profile_file(target_profile_to_delete['name']):
            speak(f"Профиль '{target_profile_to_delete['name']}' успешно удален.")
            # Удаляем из текущего списка в памяти
            all_profiles_list_ref[:] = [p for p in all_profiles_list_ref if p.get("name","").lower() != target_profile_to_delete.get("name","").lower()]
            
            # Если был удален ТЕКУЩИЙ активный профиль
            if current_profile_to_check_if_deleted and \
               current_profile_to_check_if_deleted.get("name") == target_profile_to_delete.get("name"):
                if all_profiles_list_ref: # Если остались другие профили
                    speak("Текущий профиль был удален. Пожалуйста, выберите новый активный профиль.")
                    new_active = choose_user(all_profiles_list_ref, "Выберите новый активный профиль")
                    if new_active: select_server_for_user_region(new_active.get("city","Москва"))
                    return new_active # Может быть None, если пользователь не выбрал
                else: # Если других профилей не осталось
                    speak("Все профили были удалены. Давайте создадим новый.")
                    new_profile_after_all_deleted = register_new_user_interaction()
                    if new_profile_after_all_deleted:
                        all_profiles_list_ref.append(new_profile_after_all_deleted)
                        select_server_for_user_region(new_profile_after_all_deleted.get("city","Москва"))
                    return new_profile_after_all_deleted # Возвращаем новый или None
            else: # Был удален не текущий профиль, текущий остается
                return current_profile_to_check_if_deleted
        else:
            speak(f"Не удалось удалить файл профиля для '{target_profile_to_delete['name']}'.")
            return current_profile_to_check_if_deleted # Возвращаем исходный текущий профиль
    else:
        speak("Удаление профиля отменено."); return current_profile_to_check_if_deleted