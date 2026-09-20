from __future__ import annotations

import hashlib
from typing import Any


def orden_id_for(idempotency_key: str) -> str:
    return "ord_" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:8]


def reminder_id_for(seed: str) -> str:
    return "rem_" + hashlib.sha256(seed.encode()).hexdigest()[:12]


def build_order(
    event_id: str,
    event_key: str,
    operacion: str,
    cuerpo: dict[str, Any],
    suffix: str = "",
) -> dict[str, Any]:
    key = f"{event_key}:{operacion}{suffix}"
    return {
        "orden_id": orden_id_for(key),
        "event_id": event_id,
        "operacion": operacion,
        "idempotency_key": key,
        "cuerpo": cuerpo,
    }


def user_text(event: dict[str, Any]) -> str:
    turns = event.get("transcript") or []
    return " ".join(turn["message"] for turn in turns if turn.get("role") == "user")


def slots_of(event: dict[str, Any]) -> dict[str, Any]:
    outcome = event.get("agent_outcome") or {}
    return outcome.get("slots_snapshot") or {}


def nota_contexto(event: dict[str, Any], fallback: str) -> str:
    slots = slots_of(event)
    parts: list[str] = []
    if slots.get("operacion"):
        parts.append(f"operación {slots['operacion']}")
    zonas = slots.get("zonas") or []
    if zonas:
        parts.append("zonas " + ", ".join(str(z) for z in zonas))
    if slots.get("visita_acordada_verbal"):
        parts.append(f"visita verbal {slots['visita_acordada_verbal']}")
    if slots.get("callback_when_raw"):
        parts.append(f"callback {slots['callback_when_raw']}")
    if slots.get("email_declarado"):
        parts.append(f"email {slots['email_declarado']}")
    if slots.get("presupuesto"):
        parts.append(f"presupuesto {slots['presupuesto']}")
    return "; ".join(parts) if parts else fallback
