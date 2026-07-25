"""Local reminders with spoken alerts.

Stored in jarvis_hud/data/reminders.json. The vision websocket loop polls
pop_due() and the HUD announces due reminders out loud.

Understood time formats:
    "remind me to call Ali in 20 minutes"
    "remind me to stretch in 2 hours"
    "remind me to join the meeting at 5:30 pm"
    "remind me to send the invoice tomorrow at 10 am"
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PATH = os.path.join(DATA_DIR, "reminders.json")


class ReminderError(RuntimeError):
    pass


def parse_when(raw: str):
    """Returns (clean_text, due_epoch). Raises ReminderError if no time found."""
    text = raw.strip()

    m = re.search(r"\bin\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)\b", text, re.I)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        delta = timedelta(hours=amount) if unit.startswith(("h",)) else timedelta(minutes=amount)
        clean = (text[: m.start()] + text[m.end():]).strip(" ,.")
        return clean or "reminder", time.time() + delta.total_seconds()

    tomorrow = bool(re.search(r"\btomorrow\b", text, re.I))
    m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, re.I)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        due = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        if tomorrow:
            due += timedelta(days=1)
        elif due <= datetime.now():
            due += timedelta(days=1)  # that time already passed today
        clean = re.sub(r"\btomorrow\b", "", text[: m.start()] + text[m.end():], flags=re.I)
        return clean.strip(" ,.") or "reminder", due.timestamp()

    if tomorrow:
        due = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0)
        clean = re.sub(r"\btomorrow\b", "", text, flags=re.I).strip(" ,.")
        return clean or "reminder", due.timestamp()

    raise ReminderError(
        'Tell me when: "in 20 minutes", "in 2 hours", "at 5:30 pm", or "tomorrow at 10 am".'
    )


class Reminders:
    def __init__(self):
        self._lock = threading.Lock()
        self._items = []  # {"text", "due"}
        self._load()

    def _load(self):
        try:
            with open(PATH, encoding="utf-8") as f:
                self._items = [i for i in json.load(f) if isinstance(i, dict)]
        except (FileNotFoundError, json.JSONDecodeError):
            self._items = []

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._items, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PATH)

    def add(self, raw: str) -> dict:
        text, due = parse_when(raw)
        item = {"text": text, "due": due}
        with self._lock:
            self._items.append(item)
            self._items.sort(key=lambda i: i["due"])
            self._save()
        return item

    def pending(self) -> list:
        now = time.time()
        with self._lock:
            return [dict(i) for i in self._items if i["due"] > now]

    def cancel(self, needle: str) -> int:
        needle = needle.lower().strip()
        with self._lock:
            before = len(self._items)
            self._items = [i for i in self._items if needle not in i["text"].lower()]
            removed = before - len(self._items)
            if removed:
                self._save()
        return removed

    def clear(self) -> int:
        with self._lock:
            n = len(self._items)
            self._items = []
            self._save()
        return n

    def pop_due(self) -> list:
        """Due reminders, removed from the store — announce these now."""
        now = time.time()
        with self._lock:
            due = [i for i in self._items if i["due"] <= now]
            if due:
                self._items = [i for i in self._items if i["due"] > now]
                self._save()
        return due
