"""SQLite persistence for company-specific user changes and future events."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.core.config import DATABASE_PATH


class SQLiteStore:
    def __init__(self, path: Path = DATABASE_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS category_overrides (
                    company_id TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (company_id, operation_id)
                );
                CREATE TABLE IF NOT EXISTS recurring_overrides (
                    company_id TEXT NOT NULL,
                    recurring_id TEXT NOT NULL,
                    confirmed INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (company_id, recurring_id)
                );
                CREATE TABLE IF NOT EXISTS future_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    amount REAL NOT NULL CHECK (amount > 0),
                    direction TEXT NOT NULL CHECK (direction IN ('поступление', 'списание')),
                    category TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'ручной ввод',
                    status TEXT NOT NULL CHECK (status IN ('Ожидается', 'Подтверждено', 'Исполнено', 'Отменено')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_events_company_date ON future_events(company_id, event_date);
            """)

    def get_category_overrides(self, company_id: str) -> dict[str, str]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT operation_id, category FROM category_overrides WHERE company_id = ?",
                (company_id,),
            ).fetchall()
        return {str(row["operation_id"]): str(row["category"]) for row in rows}

    def set_category(self, company_id: str, operation_id: str, category: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO category_overrides(company_id, operation_id, category)
                   VALUES (?, ?, ?)
                   ON CONFLICT(company_id, operation_id)
                   DO UPDATE SET category=excluded.category, updated_at=CURRENT_TIMESTAMP""",
                (company_id, operation_id, category),
            )

    def recurring_confirmation(self, company_id: str) -> dict[str, bool]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT recurring_id, confirmed FROM recurring_overrides WHERE company_id = ?",
                (company_id,),
            ).fetchall()
        return {str(row["recurring_id"]): bool(row["confirmed"]) for row in rows}

    def set_recurring(self, company_id: str, recurring_id: str, confirmed: bool) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO recurring_overrides(company_id, recurring_id, confirmed)
                   VALUES (?, ?, ?)
                   ON CONFLICT(company_id, recurring_id)
                   DO UPDATE SET confirmed=excluded.confirmed, updated_at=CURRENT_TIMESTAMP""",
                (company_id, recurring_id, int(confirmed)),
            )

    def list_events(self, company_id: str, include_cancelled: bool = True) -> list[dict]:
        query = "SELECT * FROM future_events WHERE company_id = ?"
        if not include_cancelled:
            query += " AND status != 'Отменено'"
        query += " ORDER BY event_date, id"
        with self.connection() as connection:
            rows = connection.execute(query, (company_id,)).fetchall()
        return [dict(row) for row in rows]

    def create_event(self, company_id: str, event: dict) -> dict:
        with self.connection() as connection:
            cursor = connection.execute(
                """INSERT INTO future_events(company_id, event_date, amount, direction, category, event_type,
                   description, source, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company_id, event["date"].isoformat(), event["amount"], event["direction"],
                    event["category"], event["event_type"], event["description"], event["source"], event["status"],
                ),
            )
            event_id = cursor.lastrowid
        return next(item for item in self.list_events(company_id) if item["id"] == event_id)

    def update_event(self, company_id: str, event_id: int, changes: dict) -> dict | None:
        existing = next((item for item in self.list_events(company_id) if item["id"] == event_id), None)
        if existing is None:
            return None
        fields = {
            "date": "event_date", "amount": "amount", "direction": "direction", "category": "category",
            "event_type": "event_type", "description": "description", "source": "source", "status": "status",
        }
        for key, value in changes.items():
            if value is not None and key in fields:
                existing[fields[key]] = value.isoformat() if key == "date" else value
        with self.connection() as connection:
            connection.execute(
                """UPDATE future_events SET event_date=?, amount=?, direction=?, category=?, event_type=?,
                   description=?, source=?, status=? WHERE id=? AND company_id=?""",
                (existing["event_date"], existing["amount"], existing["direction"], existing["category"],
                 existing["event_type"], existing["description"], existing["source"], existing["status"],
                 event_id, company_id),
            )
        return next(item for item in self.list_events(company_id) if item["id"] == event_id)

    def cancel_event(self, company_id: str, event_id: int) -> dict | None:
        return self.update_event(company_id, event_id, {"status": "Отменено"})
