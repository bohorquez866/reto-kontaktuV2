from __future__ import annotations

from src.orders import build_order
from src.state import OrchestratorState


def cancel_reminders(state: OrchestratorState) -> dict:
    event = state["event"]
    orders = []
    for reminder in state.get("pending_reminders") or []:
        reminder_id = reminder["reminder_id"]
        orders.append(
            build_order(
                event["event_id"],
                event["idempotency_key"],
                "cancelar_recordatorio",
                {
                    "reminder_id": reminder_id,
                    "motivo": "el lead respondió por WhatsApp",
                },
                suffix=f":{reminder_id}",
            )
        )
    return {"planned_orders": orders}
