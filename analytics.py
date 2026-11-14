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
            return (update.callback_query.data or "inline_button")[:64]
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
            [
                "Telegram User ID", "Username", "First Name", "First Seen",
                "Last Seen", "Total Interactions", "Commands", "Text",
                "Images", "Locations", "Buttons", "Last Event Type",
            ],
        )
        daily_sheet = self._worksheet(
            "Daily Activity",
            ["Date (UTC)", "Unique Users", "Interactions", "Commands", "Text", "Images", "Locations", "Buttons"],
        )
        event_types_sheet = self._worksheet(
            "Event Types",
            ["Event Type", "Interactions", "Share of Total"],
        )
        features_sheet = self._worksheet(
            "Feature Usage",
            ["Feature / Action", "Interactions", "Share of Total"],
        )

        stats = self.stats()
        counts = stats["event_counts"]
        with self._connect() as connection:
            all_events = connection.execute(
                "SELECT id, telegram_user_id, chat_id, event_type, created_at, details "
                "FROM events ORDER BY id"
            ).fetchall()
            users = connection.execute(
                """
                SELECT u.telegram_user_id, u.username, u.first_name, u.first_seen, u.last_seen,
                       COUNT(e.id) AS interactions,
                       SUM(e.event_type = 'command') AS commands,
                       SUM(e.event_type = 'text') AS text,
                       SUM(e.event_type = 'image') AS images,
                       SUM(e.event_type = 'location') AS locations,
                       SUM(e.event_type = 'callback') AS buttons,
                       (SELECT event_type FROM events e2
                        WHERE e2.telegram_user_id = u.telegram_user_id
                        ORDER BY e2.id DESC LIMIT 1) AS last_event_type
                FROM users u
                LEFT JOIN events e ON e.telegram_user_id = u.telegram_user_id
                GROUP BY u.telegram_user_id
                ORDER BY u.last_seen DESC
                """
            ).fetchall()
            features = connection.execute(
                """
                SELECT CASE
                           WHEN details <> '' THEN details
                           ELSE event_type
                       END AS feature,
                       COUNT(*) AS interactions
                FROM events
                GROUP BY feature
                ORDER BY interactions DESC, feature
                """
            ).fetchall()
            daily = connection.execute(
                """
                SELECT substr(created_at, 1, 10) AS day,
                       COUNT(DISTINCT telegram_user_id) AS users,
                       COUNT(*) AS interactions,
                       SUM(event_type = 'command') AS commands,
                       SUM(event_type = 'text') AS text,
                       SUM(event_type = 'image') AS images,
                       SUM(event_type = 'location') AS locations,
                       SUM(event_type = 'callback') AS buttons
                FROM events
                GROUP BY day
                ORDER BY day DESC
                """
            ).fetchall()

        overview_rows = [
            ["BURNCARE BOT ANALYTICS", "LIVE DASHBOARD"],
            ["Last updated (UTC)", datetime.now(timezone.utc).isoformat()],
            ["", ""],
            ["KEY METRICS", "VALUE"],
            ["Unique users", stats["users"]],
            ["Total interactions", stats["events"]],
            ["Users today", stats["today_users"]],
            ["Interactions today", stats["today_events"]],
            ["Users this month", stats["month_users"]],
            ["Interactions this month", stats["month_events"]],
        ]
        self._replace_table(overview, overview_rows, f"A1:B{len(overview_rows)}")
        self._format_dashboard(overview, len(overview_rows))

        event_rows = [
            ["Event ID", "User ID", "Chat ID", "Event Type", "Created At", "Details"],
            *[list(row) for row in all_events],
        ]
        self._replace_table(events_sheet, event_rows, f"A1:F{max(1, len(event_rows))}")

        users_sheet.clear()
        user_rows = [
            [
                "Telegram User ID", "Username", "First Name", "First Seen",
                "Last Seen", "Total Interactions", "Commands", "Text",
                "Images", "Locations", "Buttons", "Last Event Type",
            ],
            *[[0 if value is None else value for value in row] for row in users],
        ]
        self._replace_table(users_sheet, user_rows, f"A1:L{max(1, len(user_rows))}")

        daily_rows = [
            ["Date (UTC)", "Unique Users", "Interactions", "Commands", "Text", "Images", "Locations", "Buttons"],
            *[list(row) for row in daily],
        ]
        self._replace_table(daily_sheet, daily_rows, f"A1:H{max(1, len(daily_rows))}")

        event_type_rows = [["Event Type", "Interactions", "Share of Total"]]
        event_type_rows.extend(
            [event_type, count, f"{count / stats['events']:.1%}" if stats["events"] else "0.0%"]
            for event_type, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        )
        self._replace_table(event_types_sheet, event_type_rows, f"A1:C{max(1, len(event_type_rows))}")
        feature_rows = [["Feature / Action", "Interactions", "Share of Total"]]
        feature_rows.extend(
            [
                row["feature"],
                row["interactions"],
                f"{row['interactions'] / stats['events']:.1%}" if stats["events"] else "0.0%",
            ]
            for row in features
        )
        self._replace_table(features_sheet, feature_rows, f"A1:C{max(1, len(feature_rows))}")
        for sheet in (events_sheet, users_sheet, daily_sheet, event_types_sheet, features_sheet):
            self._format_sheet(sheet, len(sheet.get_all_values()[0]) if sheet.get_all_values() else 1)

    @staticmethod
    def _replace_table(worksheet, values: list[list[Any]], range_name: str) -> None:
        worksheet.clear()
        worksheet.update(
            values=values,
            range_name=range_name,
            value_input_option="USER_ENTERED",
        )

    @staticmethod
    def _format_sheet(worksheet, column_count: int) -> None:
        worksheet.freeze(rows=1)
        worksheet.format("1:1", {
            "backgroundColor": {"red": 0.12, "green": 0.28, "blue": 0.45},
            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
            "horizontalAlignment": "CENTER",
        })
        worksheet.format(f"A1:{chr(64 + min(column_count, 26))}1", {
            "backgroundColor": {"red": 0.12, "green": 0.28, "blue": 0.45},
            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
        })
        worksheet.columns_auto_resize(0, column_count)

    @staticmethod
    def _format_dashboard(worksheet, row_count: int) -> None:
        worksheet.format("A1:B1", {
            "backgroundColor": {"red": 0.06, "green": 0.24, "blue": 0.42},
            "textFormat": {
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                "bold": True,
                "fontSize": 14,
            },
            "horizontalAlignment": "CENTER",
        })
        worksheet.format("A4:B4", {
            "backgroundColor": {"red": 0.16, "green": 0.45, "blue": 0.66},
            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
        })
        worksheet.format(f"B5:B{min(row_count, 10)}", {
            "textFormat": {"bold": True, "fontSize": 12},
            "horizontalAlignment": "RIGHT",
        })
        worksheet.columns_auto_resize(0, 2)

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
