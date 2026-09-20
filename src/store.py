from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_events (
    idempotency_key TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    etiqueta TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emitted_orders (
    idempotency_key TEXT PRIMARY KEY,
    orden_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    operacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    reminder_id TEXT PRIMARY KEY,
    contact_id TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lead_state (
    contact_id TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 0,
    cut_count INTEGER NOT NULL DEFAULT 0,
    dnc INTEGER NOT NULL DEFAULT 0,
    whatsapp_rechazado INTEGER NOT NULL DEFAULT 0
);
"""


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get_processed(self, idempotency_key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT idempotency_key, event_id, etiqueta FROM processed_events WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None

    def save_processed(self, idempotency_key: str, event_id: str, etiqueta: str) -> None:
        self._conn.execute(
            """
            INSERT INTO processed_events (idempotency_key, event_id, etiqueta)
            VALUES (?, ?, ?)
            ON CONFLICT(idempotency_key) DO UPDATE SET
                event_id = excluded.event_id,
                etiqueta = excluded.etiqueta
            """,
            (idempotency_key, event_id, etiqueta),
        )
        self._conn.commit()

    def order_exists(self, idempotency_key: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM emitted_orders WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return row is not None

    def save_order(self, idempotency_key: str, orden_id: str, event_id: str, operacion: str) -> bool:
        try:
            self._conn.execute(
                """
                INSERT INTO emitted_orders (idempotency_key, orden_id, event_id, operacion)
                VALUES (?, ?, ?, ?)
                """,
                (idempotency_key, orden_id, event_id, operacion),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_pending_reminders(self, contact_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT reminder_id, contact_id, status
            FROM reminders
            WHERE contact_id = ? AND status = 'scheduled'
            """,
            (contact_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_reminder(self, reminder_id: str, contact_id: str) -> None:
        self._conn.execute(
            """
            INSERT INTO reminders (reminder_id, contact_id, status)
            VALUES (?, ?, 'scheduled')
            ON CONFLICT(reminder_id) DO UPDATE SET status = 'scheduled'
            """,
            (reminder_id, contact_id),
        )
        self._conn.commit()

    def cancel_reminder(self, reminder_id: str) -> None:
        self._conn.execute(
            "UPDATE reminders SET status = 'cancelled' WHERE reminder_id = ?",
            (reminder_id,),
        )
        self._conn.commit()

    def get_lead(self, contact_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            """
            SELECT contact_id, attempts, cut_count, dnc, whatsapp_rechazado
            FROM lead_state WHERE contact_id = ?
            """,
            (contact_id,),
        ).fetchone()
        if not row:
            return {
                "contact_id": contact_id,
                "attempts": 0,
                "cut_count": 0,
                "dnc": False,
                "whatsapp_rechazado": False,
            }
        return {
            "contact_id": row["contact_id"],
            "attempts": row["attempts"],
            "cut_count": row["cut_count"],
            "dnc": bool(row["dnc"]),
            "whatsapp_rechazado": bool(row["whatsapp_rechazado"]),
        }

    def upsert_lead(
        self,
        contact_id: str,
        attempts: int,
        cut_count: int,
        dnc: bool,
        whatsapp_rechazado: bool,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO lead_state (contact_id, attempts, cut_count, dnc, whatsapp_rechazado)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(contact_id) DO UPDATE SET
                attempts = excluded.attempts,
                cut_count = excluded.cut_count,
                dnc = excluded.dnc,
                whatsapp_rechazado = excluded.whatsapp_rechazado
            """,
            (contact_id, attempts, cut_count, int(dnc), int(whatsapp_rechazado)),
        )
        self._conn.commit()
