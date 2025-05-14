# shared/event_cache.py
import json
import os
from datetime import datetime

class EventCache:
    def __init__(self, cache_file_name="event_cache.json", max_events=100):
        # Помещаем кэш в корень проекта/shared для простоты
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.cache_file = os.path.join(project_root, "shared", cache_file_name)
        self.max_events = max_events
        self.events = self._load_events()

    def _load_events(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except (IOError, json.JSONDecodeError) as e:
            print(f"Ошибка загрузки кэша событий: {e}")
            return []

    def _save_events(self):
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True) # Убедимся, что директория существует
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.events, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Ошибка сохранения кэша событий: {e}")

    def add_event(self, event_data):
        """Добавляет новое событие в кэш."""
        if not isinstance(event_data, dict):
            print(f"Ошибка: event_data должен быть словарем, получено {type(event_data)}")
            return

        # Добавляем временную метку к самому событию, если ее нет
        if "timestamp_added_to_cache" not in event_data:
            event_data["timestamp_added_to_cache"] = datetime.now().isoformat()

        self.events.append(event_data)
        if len(self.events) > self.max_events:
            self.events.pop(0)  # Удаляем самое старое событие
        self._save_events()
        print(f"Событие добавлено в кэш: {event_data.get('name', event_data.get('type', 'Unknown event'))}")


    def get_events(self, limit=None):
        """Возвращает список событий из кэша, опционально последние N."""
        if limit and limit > 0:
            return self.events[-limit:]
        return self.events

    def clear_cache(self):
        """Очищает кэш событий."""
        self.events = []
        self._save_events()
        print("Кэш событий очищен.")

# Пример использования (можно закомментировать или удалить)
if __name__ == '__main__':
    cache = EventCache()
    cache.add_event({"type": "test_event", "data": "Hello World 1"})
    cache.add_event({"type": "test_event_2", "details": "Some details here", "name": "Specific Test"})
    print("Все события:", cache.get_events())
    print("Последние 1:", cache.get_events(limit=1))
    # cache.clear_cache()
    # print("После очистки:", cache.get_events())