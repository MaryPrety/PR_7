# client/voice_client/tts_stt.py
import pyttsx3
import speech_recognition as sr
import pygame # For pygame.mixer

# Используем псевдонимы, чтобы явно указать, что это из config
# Закомментировал пока, так как инициализация googletrans здесь вызывает вопросы
# from .config import TRANSLATION_ENABLED as cfg_translation_enabled, translator_instance as cfg_translator_instance


# Инициализация TTS (pyttsx3)
engine = None
try:
    engine = pyttsx3.init()
    if engine:
        voices = engine.getProperty('voices')
        russian_voice_found = False
        if voices:
            for voice in voices:
                # Ensure voice and voice.name are not None before accessing attributes
                if voice and voice.name and ("russian" in voice.name.lower() or "русский" in voice.name.lower()):
                    engine.setProperty('voice', voice.id)
                    russian_voice_found = True
                    print(f"[TTS] Установлен русский голос: {voice.name}")
                    break
            if not russian_voice_found and voices: # Check voices again in case it's empty
                engine.setProperty('voice', voices[0].id)
                print(f"[TTS] Русский голос не найден. Используется голос по умолчанию: {voices[0].name}")
        else:
            print("[TTS] Голосовые движки не найдены в системе.")
        engine.setProperty('rate', 165)
        engine.setProperty('volume', 1.0)
    else:
        print("[TTS] Не удалось инициализировать движок pyttsx3 (engine is None).")
except Exception as e_init_tts:
    print(f"[TTS ОШИБКА Инициализации] Не удалось инициализировать pyttsx3: {e_init_tts}")
    engine = None # Ensure engine is None if initialization failed

# === ИНИЦИАЛИЗАЦИЯ PYGAME.MIXER для TTS/Общих звуков, если нужно ===
tts_mixer_initialized = False

def init_mixer_for_tts() -> bool:
    """Инициализирует pygame.mixer, если он еще не инициализирован."""
    global tts_mixer_initialized
    if not tts_mixer_initialized:
        try:
            pygame.mixer.init()
            tts_mixer_initialized = True
            print("[TTS Mixer] Pygame mixer (для TTS/общих звуков) успешно инициализирован.")
        except pygame.error as e:
            print(f"[TTS Mixer ОШИБКА] Не удалось инициализировать pygame mixer: {e}")
    return tts_mixer_initialized

# =====================================================================

def speak(text: str):
    if not engine:
        print(f"[TTS ОШИБКА Движка] Движок не инициализирован. Воспроизвожу в консоль: {text}")
        return
    
    print(f"[Ассистент]: {text}")
    
    try:
        # Check if the engine is in a loop and try to end it.
        # This can happen if a previous runAndWait was interrupted.
        if hasattr(engine, '_inLoop') and engine._inLoop: # type: ignore
            engine.endLoop()
    except RuntimeError:
        # This error can occur if the loop is already stopped or in an invalid state.
        # It's often safe to ignore it and proceed.
        pass # pass
    except Exception as e_loop_check:
        # Catch any other unexpected errors during loop check
        print(f"[TTS] Неожиданная ошибка при проверке/завершении цикла озвучивания: {e_loop_check}")


    try:
        engine.say(text)
        engine.runAndWait()
    except RuntimeError as e_runtime:
        print(f"[TTS] RuntimeError во время engine.say/runAndWait: {e_runtime}")
        # Attempt to recover if possible, e.g., by trying to end a potentially stuck loop
        try:
            if hasattr(engine, '_inLoop') and engine._inLoop: # type: ignore
                engine.endLoop()
            # Retry speaking
            engine.say(text)
            engine.runAndWait()
        except Exception as e_retry:
            print(f"[TTS] Повторная попытка озвучивания не удалась: {e_retry}")
    except Exception as e_general:
        print(f"[TTS] Общая ошибка озвучивания: {e_general}")


# Инициализация Googletrans (теперь перенесена в utils.py, чтобы избежать циклических импортов, если tts_stt импортирует utils)
# Если она нужна здесь, то config должен быть импортирован после определения всех функций этого модуля.
# Но лучше оставить ее в utils.py, как более общем месте.
# from .config import TRANSLATION_ENABLED, translator_instance # Для информации
# if not TRANSLATION_ENABLED: ... (логика инициализации) ...


def listen_input(
    timeout_param: int | float | str | None = 7,
    phrase_time_limit_param: int | float | str | None = 15
) -> str:
    recognizer = sr.Recognizer()
    
    # Эти параметры устанавливаются напрямую и имеют правильные типы
    recognizer.pause_threshold = 0.8  # float
    recognizer.energy_threshold = 300  # int (speech_recognition handles int or float for this)
    recognizer.dynamic_energy_threshold = True # bool

    # --- ОБРАБОТКА ПАРАМЕТРОВ ДЛЯ recognizer.listen ---
    # recognizer.listen ожидает, что timeout и phrase_time_limit будут числами (int/float) или None.
    # Преобразуем их, если они приходят как строки, и установим значения по умолчанию при ошибке.

    actual_timeout = None
    if timeout_param is not None:
        try:
            actual_timeout = float(timeout_param)
        except (ValueError, TypeError):
            print(f"[STT WARNING] Некорректное значение timeout: '{timeout_param}' (тип: {type(timeout_param)}). Используется значение по умолчанию: 7 сек.")
            actual_timeout = 7.0 # Значение по умолчанию, если конвертация не удалась

    actual_phrase_limit = None
    if phrase_time_limit_param is not None:
        try:
            actual_phrase_limit = float(phrase_time_limit_param)
        except (ValueError, TypeError):
            print(f"[STT WARNING] Некорректное значение phrase_time_limit: '{phrase_time_limit_param}' (тип: {type(phrase_time_limit_param)}). Используется значение по умолчанию: 15 сек.")
            actual_phrase_limit = 15.0 # Значение по умолчанию, если конвертация не удалась
    # --- КОНЕЦ ОБРАБОТКИ ПАРАМЕТРОВ ---

    with sr.Microphone() as source:
        print("[Ассистент]: Слушаю вас...")
        try:
            # Передаем обработанные значения (float или None) в recognizer.listen
            audio = recognizer.listen(source, timeout=actual_timeout, phrase_time_limit=actual_phrase_limit)
        except sr.WaitTimeoutError:
            # print("[STT] Время ожидания фразы истекло.") # Сообщение уже было в оригинале, можно оставить
            return "" # Возвращаем пустую строку, как и было
        except Exception as e_listen:
            # Здесь ловилась ошибка '>' not supported between instances of 'float' and 'str'
            print(f"[STT] Ошибка во время прослушивания (recognizer.listen): {e_listen} (Тип ошибки: {type(e_listen)})")
            return ""

    try:
        text = recognizer.recognize_google(audio, language="ru-RU")
        print(f"[Вы сказали]: {text}")
        return text.strip().lower()
    except sr.UnknownValueError:
        # print("[STT] Речь не распознана Google Speech Recognition.") # Сообщение уже было
        return ""
    except sr.RequestError as e:
        print(f"[STT] Ошибка запроса к Google Speech Recognition; {e}. Проверьте интернет-соединение.")
        return ""
    except Exception as e_rec_general:
        print(f"[STT] Общая ошибка распознавания: {e_rec_general}")
        return ""

# Пример вызова, если нужно протестировать отдельно (закомментировать при интеграции)
if __name__ == '__main__':
    # init_mixer_for_tts() # Pygame mixer для TTS, здесь не нужен для listen_input
    print("Тестирование функции listen_input. Говорите после 'Слушаю вас...'.")
    
    # Тест с параметрами по умолчанию
    # recognized_text = listen_input()
    # print(f"Распознано (по умолчанию): '{recognized_text}'")

    # Тест с передачей строковых значений, которые должны быть сконвертированы
    # recognized_text_str_params = listen_input(timeout_param="5", phrase_time_limit_param="10")
    # print(f"Распознано (строковые параметры): '{recognized_text_str_params}'")

    # Тест с некорректным строковым значением
    # recognized_text_bad_str = listen_input(timeout_param="abc", phrase_time_limit_param="xyz")
    # print(f"Распознано (некорректные строки): '{recognized_text_bad_str}'")

    # Тест с None
    # recognized_text_none = listen_input(timeout_param=None, phrase_time_limit_param=None)
    # print(f"Распознано (None параметры): '{recognized_text_none}'")

    speak("Тестовое сообщение для проверки TTS.")
    user_input = listen_input()
    if user_input:
        speak(f"Вы сказали: {user_input}")
    else:
        speak("Ничего не было распознано или произошла ошибка.")