# client/voice_client/__init__.py
from .main_loop import run_voice_assistant
# Если есть другие важные функции/классы для экспорта из пакета, их тоже можно добавить
# from .tts_stt import speak, listen_input 
# from .utils import ...

__all__ = ['run_voice_assistant'] #, 'speak', 'listen_input', ...]