"""
A.V.I. Memory
Simple local memory system.
"""

import json
from pathlib import Path


class AVIMemory:
    def __init__(self):
        self.memory_file = Path("data/memory.json")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.memory_file.exists():
            self._save({})

    def _load(self):
        try:
            with open(self.memory_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data):
        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def remember(self, key, value):
        data = self._load()
        data[key] = value
        self._save(data)

    def recall(self, key):
        data = self._load()
        return data.get(key)

    def forget(self, key):
        data = self._load()

        if key in data:
            del data[key]
            self._save(data)
            return True

        return False

    def all_memory(self):
        return self._load()


if __name__ == "__main__":
    memory = AVIMemory()

    memory.remember("test", "A.V.I. memory is working.")

    print("Stored:", memory.recall("test"))
    print("All memory:", memory.all_memory())
    