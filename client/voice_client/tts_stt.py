# client/voice_client/tts_stt.py
import pyttsx3
import speech_recognition as sr
import pygame

# --- TTS Engine Initialization ---
engine = None
try:
    engine = pyttsx3.init()
    if engine:
        voices = engine.getProperty('voices')
        russian_voice_found = False
        if voices:
            for voice in voices:
                # Ensure voice.name is not None before calling lower() or accessing attributes
                if hasattr(voice, 'name') and voice.name and \
                   ("russian" in voice.name.lower() or "русский" in voice.name.lower()):
                    engine.setProperty('voice', voice.id)
                    russian_voice_found = True
                    print(f"[TTS] Установлен русский голос: {voice.name}")
                    break
            if not russian_voice_found and voices: # If no Russian voice, use the first available
                if voices[0].id: # Check if voice ID is not None
                    engine.setProperty('voice', voices[0].id)
                    print(f"[TTS] Русский голос не найден. Используется голос по умолчанию: {voices[0].name if hasattr(voices[0], 'name') else 'Unknown Voice'}")
                else:
                    print("[TTS] Голос по умолчанию не имеет валидного ID.")
        else:
            print("[TTS] Голосовые движки не найдены в системе, но pyttsx3 инициализирован.")
        
        engine.setProperty('rate', 165)  # Speed of speech
        engine.setProperty('volume', 1.0) # Volume (0.0 to 1.0)
    else:
        # This case (engine being None after pyttsx3.init()) is unlikely if no exception occurred,
        # but good to have a message.
        print("[TTS ОШИБКА] pyttsx3.init() вернул None. TTS не будет работать.")
except Exception as e:
    print(f"[TTS КРИТИЧЕСКАЯ ОШИБКА] Не удалось инициализировать движок pyttsx3: {e}")
    engine = None # Ensure engine is None if initialization failed

# --- Pygame Mixer for TTS/General Sounds ---
tts_mixer_initialized = False

def init_mixer_for_tts() -> bool:
    """Инициализирует pygame.mixer, если он еще не инициализирован."""
    global tts_mixer_initialized
    if not tts_mixer_initialized:
        if not pygame.get_init(): # Check if pygame itself is initialized
            try:
                print("[Pygame Core] Попытка инициализации Pygame...")
                pygame.init() # Initialize all pygame modules
                print("[Pygame Core] Pygame успешно инициализирован.")
            except pygame.error as e:
                print(f"[Pygame Core ОШИБКА] Не удалось инициализировать pygame: {e}")
                return False # Cannot initialize mixer if pygame core fails

        try:
            print("[TTS Mixer] Попытка инициализации Pygame mixer...")
            pygame.mixer.init()
            tts_mixer_initialized = True
            print("[TTS Mixer] Pygame mixer (для TTS/общих звуков) успешно инициализирован.")
        except pygame.error as e:
            print(f"[TTS Mixer ОШИБКА] Не удалось инициализировать pygame mixer: {e}")
            # Consider not speaking here if TTS might rely on this mixer
    return tts_mixer_initialized

# --- Speak Function ---
def speak(text: str):
    """Озвучивает переданный текст."""
    if not engine:
        print(f"[TTS ОШИБКА Движка] Движок не инициализирован. Воспроизвожу в консоль: {text}")
        return
    
    print(f"[Ассистент]: {text}")
    try:
        # Attempt to fix "RuntimeError: Run loop already started"
        # Check if _inLoop attribute exists and is True
        if hasattr(engine, '_inLoop') and engine._inLoop: # type: ignore
            engine.endLoop()
    except RuntimeError:
        # This might happen if the loop was already ending or in an unstable state.
        print("[TTS Предупреждение] RuntimeError при попытке engine.endLoop().")
        pass 
    except AttributeError:
        # _inLoop might not exist in all pyttsx3 versions/drivers
        # print("[TTS Предупреждение] Атрибут _inLoop не найден в движке TTS.")
        pass


    try:
        engine.say(text)
        engine.runAndWait()
    except RuntimeError as e:
        print(f"[TTS] RuntimeError во время engine.say/runAndWait: {e}")
        # Attempt to recover if possible
        try:
            if hasattr(engine, '_inLoop') and engine._inLoop: # type: ignore
                 engine.endLoop() # Try to end any existing loop again
            engine.say(text) # Retry saying
            engine.runAndWait() # Retry waiting
            print("[TTS] Повторная попытка озвучивания после RuntimeError успешна.")
        except Exception as e_retry:
            print(f"[TTS] Повторная попытка озвучивания не удалась: {e_retry}")
    except Exception as e_general:
        print(f"[TTS] Общая ошибка озвучивания: {e_general}")

# --- Speech Recognition Function ---
def listen_input(
    timeout: int = 7,                   # Renamed from timeout_seconds for consistency with original error
    phrase_time_limit: int = 15,        # Renamed from phrase_time_limit_seconds for consistency
    energy_threshold_val: float = 300.0, # Use float for energy_threshold
    dynamic_energy_threshold_flag: bool = True,
    pause_threshold_val: float = 0.8    # Use float for pause_threshold
    ) -> str:
    """
    Прослушивает пользовательский ввод с микрофона и распознает речь.

    Args:
        timeout: Максимальное время ожидания начала речи (в секундах).
        phrase_time_limit: Максимальная длительность фразы (в секундах).
        energy_threshold_val: Порог энергии для определения речи.
        dynamic_energy_threshold_flag: Автоматически ли подстраивать порог энергии.
        pause_threshold_val: Длительность тишины, считающаяся концом фразы.

    Returns:
        Распознанный текст в нижнем регистре или пустую строку при ошибке/таймауте.
    """
    recognizer = sr.Recognizer()
    
    recognizer.pause_threshold = pause_threshold_val 
    recognizer.energy_threshold = energy_threshold_val
    recognizer.dynamic_energy_threshold = dynamic_energy_threshold_flag

    with sr.Microphone() as source:
        # Optional: Adjust for ambient noise if dynamic energy threshold is off
        # if not recognizer.dynamic_energy_threshold:
        #     print("[STT] Калибровка под окружающий шум (1 сек)...")
        #     try:
        #         recognizer.adjust_for_ambient_noise(source, duration=1)
        #         print(f"[STT] Новый порог энергии: {recognizer.energy_threshold}")
        #     except Exception as e_ambient:
        #         print(f"[STT ОШИБКА] Не удалось откалибровать шум: {e_ambient}")


        print("[Ассистент]: Слушаю вас...")
        try:
            # Ensure timeout and phrase_time_limit are floats or None if library expects that.
            # speech_recognition typically handles int for these where float is expected.
            audio = recognizer.listen(
                source, 
                timeout=float(timeout) if timeout is not None else None,
                phrase_time_limit=float(phrase_time_limit) if phrase_time_limit is not None else None
            )
        except sr.WaitTimeoutError:
            print("[STT] Время ожидания фразы истекло (ничего не сказано).")
            return ""
        except Exception as e_listen:
            print(f"[STT] Ошибка во время прослушивания (recognizer.listen): {e_listen}")
            return ""

    try:
        print("[STT] Распознавание речи...")
        text = recognizer.recognize_google(audio, language="ru-RU")
        recognized_text = text.strip().lower()
        print(f"[Вы сказали]: {recognized_text}")
        return recognized_text
    except sr.UnknownValueError:
        print("[STT] Речь не распознана Google Speech Recognition (UnknownValueError).")
        return ""
    except sr.RequestError as e:
        print(f"[STT] Ошибка запроса к Google Speech Recognition (RequestError): {e}. Проверьте интернет.")
        return ""
    except Exception as e_rec_general:
        print(f"[STT] Общая ошибка распознавания: {e_rec_general}")
        return ""

# --- Main execution for testing (optional) ---
if __name__ == "__main__":
    print("Тестирование модуля TTS/STT...")

    if not tts_mixer_initialized:
        init_mixer_for_tts()
    
    speak("Привет! Это тест системы озвучивания текста.")
    
    print("\n--- Тест распознавания речи ---")
    speak("Пожалуйста, скажите что-нибудь в течение 5 секунд.")
    user_input = listen_input(timeout=5, phrase_time_limit=10) # Matched to function definition
    if user_input:
        speak(f"Вы сказали: {user_input}")
    else:
        speak("Кажется, вы ничего не сказали или произошла ошибка при распознавании.")

    speak("Тестирование модуля завершено.")