import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, data_file: str):
        self.data_file = Path(data_file)
        self.data: dict[str, dict[str, Any]] = {}
        self._save_task: asyncio.Task | None = None

    async def load(self) -> None:
        if self.data_file.exists():
            with self.data_file.open(encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            self.data = {}

    def save(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with self.data_file.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    async def periodic_save(self) -> None:
        while True:
            await asyncio.sleep(300)
            self.save()

    def start_periodic_save(self) -> None:
        if self._save_task is None or self._save_task.done():
            self._save_task = asyncio.create_task(self.periodic_save())

    def stop_periodic_save(self) -> None:
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()

    def get_chat_data(self, chat_id: int) -> dict[str, Any]:
        chat_key = str(chat_id)
        if chat_key not in self.data:
            self.data[chat_key] = {
                "time_from": "09:00",
                "time_to": "21:00",
                "message_text": "Пора отправлять свои фотки",
                "scheduled_today": None,
                "scheduled_tomorrow": None,
                "last_ping": None,
                "registered_users": {},
            }
        return self.data[chat_key]

    def update_chat_data(self, chat_id: int, updates: dict[str, Any]) -> None:
        chat_key = str(chat_id)
        chat_data = self.get_chat_data(chat_id)
        chat_data.update(updates)
        self.data[chat_key] = chat_data

    def set_last_ping(self, chat_id: int, ping_time: datetime) -> None:
        self.update_chat_data(chat_id, {"last_ping": ping_time.isoformat()})

    def get_last_ping(self, chat_id: int) -> datetime | None:
        chat_data = self.get_chat_data(chat_id)
        last_ping_str = chat_data.get("last_ping")
        return self.deserialize_datetime(last_ping_str)

    def register_user(
        self, chat_id: int, user_id: int, username: str | None, full_name: str
    ) -> None:
        chat_data = self.get_chat_data(chat_id)
        if "registered_users" not in chat_data:
            chat_data["registered_users"] = {}

        chat_data["registered_users"][str(user_id)] = {
            "username": username,
            "full_name": full_name,
            "registered_at": datetime.now(UTC).isoformat(),
        }
        self.update_chat_data(chat_id, chat_data)

    def unregister_user(self, chat_id: int, user_id: int) -> bool:
        chat_data = self.get_chat_data(chat_id)
        registered_users = chat_data.get("registered_users", {})
        user_key = str(user_id)

        if user_key in registered_users:
            del registered_users[user_key]
            self.update_chat_data(chat_id, {"registered_users": registered_users})
            return True
        return False

    def is_user_registered(self, chat_id: int, user_id: int) -> bool:
        chat_data = self.get_chat_data(chat_id)
        registered_users = chat_data.get("registered_users", {})
        return str(user_id) in registered_users

    def get_registered_users(self, chat_id: int) -> dict[str, dict[str, Any]]:
        chat_data = self.get_chat_data(chat_id)
        return chat_data.get("registered_users", {})

    def serialize_datetime(self, dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    def deserialize_datetime(self, dt_str: str | None) -> datetime | None:
        return datetime.fromisoformat(dt_str) if dt_str else None

    def write_lock(self, chat_id: int, ping_time: datetime) -> None:
        lock_file = self.data_file.parent / f".lock_{chat_id}"
        lock_file.write_text(ping_time.isoformat(), encoding="utf-8")

    def read_lock(self, chat_id: int) -> datetime | None:
        lock_file = self.data_file.parent / f".lock_{chat_id}"
        try:
            return datetime.fromisoformat(lock_file.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            return None