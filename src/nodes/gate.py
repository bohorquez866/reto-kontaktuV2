from __future__ import annotations

from typing import Literal

from langgraph.types import Command

from src.runtime import get_store
from src.state import OrchestratorState


def _call_id(event: dict) -> str | None:
    telephony = event.get("telephony") or {}
    return telephony.get("call_id")


def gate(state: OrchestratorState) -> Command[
    Literal["classify_signaling", "cancel_reminders", "write_skip", "write_redelivery"]
]:
    event = state["event"]
    campana = state["campana"]
    store = get_store()
    expected_org = campana["campana"]["organization_id"]
    contact_id = event["lead"]["contact_id"]

    if event["organization_id"] != expected_org:
        return Command(
            update={
                "etiqueta": "no_aplica",
                "motivo": "evento de otra organización",
                "confianza": 1.0,
                "call_id": _call_id(event),
                "skip_orders": True,
                "is_foreign_org": True,
                "persist_lead": False,
                "planned_orders": [],
            },
            goto="write_skip",
        )

    processed = store.get_processed(event["idempotency_key"])
    if processed:
        return Command(
            update={
                "etiqueta": processed["etiqueta"],
                "motivo": "reentrega del mismo hecho; no se duplican órdenes",
                "confianza": 1.0,
                "call_id": _call_id(event),
                "skip_orders": True,
                "is_redelivery": True,
                "persist_lead": False,
                "planned_orders": [],
            },
            goto="write_redelivery",
        )

    if event["type"] == "message.received":
        return Command(
            update={
                "etiqueta": "no_aplica",
                "motivo": "el lead respondió al WhatsApp de documentación",
                "confianza": 1.0,
                "call_id": None,
                "is_message": True,
                "persist_lead": False,
                "pending_reminders": store.get_pending_reminders(contact_id),
            },
            goto="cancel_reminders",
        )

    lead = store.get_lead(contact_id)
    return Command(
        update={
            "call_id": _call_id(event),
            "attempts_before": lead["attempts"],
            "cut_count_before": lead["cut_count"],
            "lead_dnc": lead["dnc"],
            "whatsapp_rechazado": lead["whatsapp_rechazado"],
            "persist_lead": True,
            "skip_orders": False,
        },
        goto="classify_signaling",
    )
