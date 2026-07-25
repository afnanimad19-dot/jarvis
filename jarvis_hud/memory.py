"""Persistent memory: long-term facts about the owner + conversation history.

Stored as plain JSON at jarvis_hud/data/memory.json (git-ignored). Facts are
injected into the system prompt on every request; history is reloaded on
startup so a restart doesn't wipe the conversation.

Facts get in two ways:
- Explicitly: "Jarvis, remember that I ..." (owner command)
- Automatically: the model tags durable facts it learns as <remember>...</remember>
  in its replies; the brain strips the tag and stores the fact.
"""

import json
import os
import threading
import time

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PATH = os.path.join(DATA_DIR, "memory.json")

MAX_FACTS = 200
MAX_HISTORY_TURNS = 40


class Memory:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {"facts": [], "history": []}
        self._load()

    # -- persistence ---------------------------------------------------------

    def _load(self):
        try:
            with open(PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._data["facts"] = list(data.get("facts", []))[:MAX_FACTS]
                self._data["history"] = list(data.get("history", []))[-MAX_HISTORY_TURNS:]
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PATH)

    # -- facts ----------------------------------------------------------------

    def add_fact(self, text: str) -> bool:
        text = " ".join(text.split()).strip(" .")
        if not text:
            return False
        with self._lock:
            if any(f["text"].lower() == text.lower() for f in self._data["facts"]):
                return False
            self._data["facts"].append({"text": text, "ts": int(time.time())})
            self._data["facts"] = self._data["facts"][-MAX_FACTS:]
            self._save()
        return True

    def remove_facts(self, needle: str) -> int:
        needle = needle.lower().strip()
        with self._lock:
            before = len(self._data["facts"])
            self._data["facts"] = [
                f for f in self._data["facts"] if needle not in f["text"].lower()
            ]
            removed = before - len(self._data["facts"])
            if removed:
                self._save()
        return removed

    def clear_facts(self) -> int:
        with self._lock:
            n = len(self._data["facts"])
            self._data["facts"] = []
            self._save()
        return n

    def facts(self) -> list:
        with self._lock:
            return [f["text"] for f in self._data["facts"]]

    def facts_block(self) -> str:
        items = self.facts()
        if not items:
            return ""
        return "\n\nLong-term memory — things you know about the owner:\n" + "\n".join(
            f"- {t}" for t in items
        )

    # -- conversation history --------------------------------------------------

    def save_history(self, history: list):
        """Persist recent turns, dropping image payloads (too large)."""
        slim = []
        for turn in history[-MAX_HISTORY_TURNS:]:
            parts = [p for p in turn.get("content", []) if p.get("type") == "text"]
            if parts:
                slim.append({"role": turn["role"], "content": parts})
        with self._lock:
            self._data["history"] = slim
            self._save()

    def load_history(self) -> list:
        with self._lock:
            return list(self._data["history"])

    def clear_history(self):
        with self._lock:
            self._data["history"] = []
            self._save()
