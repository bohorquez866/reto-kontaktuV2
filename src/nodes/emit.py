from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import SALIDA_DIR
from src.labels import CUT_LABELS
from src.runtime import get_store
from src.state import OrchestratorState


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def emit_and_persist(state: OrchestratorState) -> dict:
    event = state["event"]
    store = get_store()
    emitted: list[str] = []

    for order in state.get("planned_orders") or []:
        key = order["idempotency_key"]
        if not store.save_order(key, order["orden_id"], order["event_id"], order["operacion"]):
            continue
        if order["operacion"] == "programar_recordatorio":
            reminder_id = order.get("reminder_id")
            if reminder_id:
                store.save_reminder(reminder_id, event["lead"]["contact_id"])
        if order["operacion"] == "cancelar_recordatorio":
            store.cancel_reminder(order["cuerpo"]["reminder_id"])
        line = {k: v for k, v in order.items() if k != "reminder_id"}
        _append_jsonl(SALIDA_DIR / "ordenes.jsonl", line)
        emitted.append(order["orden_id"])

    if not state.get("is_redelivery"):
        store.save_processed(event["idempotency_key"], event["event_id"], state["etiqueta"])

    if state.get("persist_lead") and event["type"] == "call.ended":
        lead = store.get_lead(event["lead"]["contact_id"])
        cut_count = lead["cut_count"]
        if state["etiqueta"] in CUT_LABELS:
            cut_count += 1
        store.upsert_lead(
            event["lead"]["contact_id"],
            state.get("attempts_after", lead["attempts"] + 1),
            cut_count,
            lead["dnc"] or state["etiqueta"] == "no_contactar",
            lead["whatsapp_rechazado"] or bool(state.get("whatsapp_rechazado")),
        )

    decision = {
        "event_id": event["event_id"],
        "call_id": state.get("call_id"),
        "etiqueta": state["etiqueta"],
        "motivo": state["motivo"],
        "confianza": state["confianza"],
        "ordenes": emitted,
    }
    _append_jsonl(SALIDA_DIR / "decisiones.jsonl", decision)
    return {"emitted_order_ids": emitted}
