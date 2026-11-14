"""Privacy-conscious bot analytics with SQLite storage and Google Sheets sync."""

from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
import sqlite3
from pathlib import Path
from typing import Any, Iterator

from gspread.exceptions import WorksheetNotFound
from telegram import Update

log = logging.getLogger(__name__)


class Analytics:
    def __init__(
        self,
        database_path: str,
        sheets_id: str = "",
        service_account_file: str = "",
    ) -> None:
        self.database_path = Path(database_path)
        self.sheets_id = sheets_id
        self.service_account_file = service_account_file
        self._sheets_lock = asyncio.Lock()
        self._sheets = None
        self._sync_tasks: set[asyncio.Task[None]] = set()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL,
                    chat_id INTEGER,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
                CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
                """
            )

    @staticmethod
    def _event_type(update: Update) -> str:
        if update.callback_query:
            return "callback"
        message = update.effective_message
        if not message:
            return "other"
        if message.photo or message.document:
            return "image"
        if message.location:
            return "location"
        if message.text and message.text.startswith("/"):
            return "command"
        if message.text:
            return "text"
        return "message"

    @staticmethod
    def _details(update: Update) -> str:
        message = update.effective_message
        if message and message.text and message.text.startswith("/"):
            return message.text.split(maxsplit=1)[0][:64]
        if update.callback_query:
            return "inline_button"
        return ""

    def record_update(self, update: Update) -> None:
        user = update.effective_user
        if not user:
            return
        now = datetime.now(timezone.utc).isoformat()
        event_type = self._event_type(update)
        details = self._details(update)
        chat = update.effective_chat
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO users
                    (telegram_user_id, username, first_name, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_seen = excluded.last_seen
                """,
                (user.id, user.username or "", user.first_name or "", now, now),
            )
            cursor = connection.execute(
                """
                INSERT INTO events
                    (telegram_user_id, chat_id, event_type, created_at, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user.id, chat.id if chat else None, event_type, now, details),
            )
            event_id = cursor.lastrowid
        task = asyncio.create_task(self._sync_event(event_id))
        self._sync_tasks.add(task)
        task.add_done_callback(self._sync_tasks.discard)

    def stats(self) -> dict[str, Any]:
        current = datetime.now(timezone.utc)
        today = current.date().isoformat()
        month = current.strftime("%Y-%m")
        with self._connect() as connection:
            users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            events = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            today_users = connection.execute(
                "SELECT COUNT(*) FROM users WHERE substr(last_seen, 1, 10) = ?",
                (today,),
            ).fetchone()[0]
            today_events = connection.execute(
                "SELECT COUNT(*) FROM events WHERE substr(created_at, 1, 10) = ?",
                (today,),
            ).fetchone()[0]
            month_users = connection.execute(
                "SELECT COUNT(*) FROM users WHERE substr(last_seen, 1, 7) = ?",
                (month,),
            ).fetchone()[0]
            month_events = connection.execute(
                "SELECT COUNT(*) FROM events WHERE substr(created_at, 1, 7) = ?",
                (month,),
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT event_type, COUNT(*) AS count FROM events GROUP BY event_type"
            ).fetchall()
        return {
            "users": users,
            "events": events,
            "today_users": today_users,
            "today_events": today_events,
            "month_users": month_users,
            "month_events": month_events,
            "event_counts": Counter({row["event_type"]: row["count"] for row in rows}),
        }

    async def _sync_event(self, event_id: int | None) -> None:
        if not self.sheets_id or not self.service_account_file or event_id is None:
            return
        async with self._sheets_lock:
            try:
                await asyncio.to_thread(self._sync_to_sheets, event_id)
            except Exception:
                log.exception("Google Sheets analytics sync failed for event %s", event_id)

    def _sync_to_sheets(self, event_id: int) -> None:
        import gspread

        if self._sheets is None:
            client = gspread.service_account(filename=self.service_account_file)
            self._sheets = client.open_by_key(self.sheets_id)
        overview = self._worksheet("Overview", ["Metric", "Value"])
        events_sheet = self._worksheet(
            "Events",
            ["Event ID", "User ID", "Chat ID", "Event Type", "Created At", "Details"],
        )
        users_sheet = self._worksheet(
            "Users",
            ["Telegram User ID", "Username", "First Name", "First Seen", "Last Seen"],
        )

        stats = self.stats()
        overview.clear()
        counts = stats["event_counts"]
        overview_rows = [
            ["Metric", "Value"],
            ["Unique users", stats["users"]],
            ["Total interactions", stats["events"]],
            ["Users today", stats["today_users"]],
            ["Interactions today", stats["today_events"]],
            ["Users this month", stats["month_users"]],
            ["Interactions this month", stats["month_events"]],
            ["Commands", counts.get("command", 0)],
            ["Text requests", counts.get("text", 0)],
            ["Images", counts.get("image", 0)],
            ["Locations", counts.get("location", 0)],
            ["Button clicks", counts.get("callback", 0)],
            ["Last updated (UTC)", datetime.now(timezone.utc).isoformat()],
        ]
        overview.update(
            values=overview_rows,
            range_name=f"A1:B{len(overview_rows)}",
            value_input_option="USER_ENTERED",
        )
        with self._connect() as connection:
            event = connection.execute(
                "SELECT id, telegram_user_id, chat_id, event_type, created_at, details "
                "FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
            users = connection.execute(
                "SELECT telegram_user_id, username, first_name, first_seen, last_seen "
                "FROM users ORDER BY first_seen"
            ).fetchall()
        if event:
            events_sheet.append_row(list(event), value_input_option="USER_ENTERED")
        users_sheet.clear()
        users_sheet.update(
            values=[
                ["Telegram User ID", "Username", "First Name", "First Seen", "Last Seen"],
                *[list(row) for row in users],
            ],
            range_name=f"A1:E{len(users) + 1}",
            value_input_option="USER_ENTERED",
        )

    def _worksheet(self, title: str, headers: list[str]):
        try:
            worksheet = self._sheets.worksheet(title)
        except WorksheetNotFound:
            worksheet = self._sheets.add_worksheet(title=title, rows=1000, cols=len(headers))
            worksheet.append_row(headers, value_input_option="USER_ENTERED")
        return worksheet

    async def wait_for_sync(self) -> None:
        if self._sync_tasks:
            await asyncio.gather(*tuple(self._sync_tasks), return_exceptions=True)
