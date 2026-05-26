import json
import time
from pathlib import Path

class HistoryStore:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self):
        if not self.filepath.exists() or self.filepath.stat().st_size == 0:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def add_event(self, event_type, details):
        """Adds a new historical event."""
        self._ensure_file()
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                events = json.load(f)
        except Exception:
            events = []

        new_event = {
            "id": int(time.time() * 1000),
            "timestamp": int(time.time()),
            "event_type": event_type,
            "details": details
        }
        events.insert(0, new_event)  # Prepend for newest-first order

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        return new_event

    def get_all_events(self):
        """Returns all events."""
        self._ensure_file()
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def clear_history(self):
        """Clears all historical events."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    def delete_event(self, event_id):
        """Deletes a historical event by ID."""
        self._ensure_file()
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                events = json.load(f)
        except Exception:
            return False

        filtered_events = [e for e in events if e.get("id") != event_id]
        deleted = len(events) != len(filtered_events)

        if deleted:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(filtered_events, f, ensure_ascii=False, indent=2)
        return deleted
