from __future__ import annotations

from typing import Any, Literal

from langgraph.types import Command

from src.state import OrchestratorState


def _classified(etiqueta: str, motivo: str, confianza: float) -> dict[str, Any]:
    return {
        "etiqueta": etiqueta,
        "motivo": motivo,
        "confianza": confianza,
    }


def classify_from_signaling(event: dict[str, Any]) -> dict[str, Any] | None:
    telephony = event.get("telephony") or {}
    sip = telephony.get("sip_status_code")
    sip_status = telephony.get("sip_status") or ""
    transcript = event.get("transcript") or []
    amd = telephony.get("amd") or {}
    amd_result = amd.get("result")
    appointment = (event.get("agent_outcome") or {}).get("appointment")

    if sip in (408, 480) and not transcript:
        return _classified(
            "sin_respuesta",
            f"{sip} {sip_status}: sin respuesta".strip(),
            0.97,
        )
    if sip == 486:
        return _classified(
            "ocupado",
            f"{sip} {sip_status}: la línea comunica".strip(),
            0.97,
        )
    if sip == 603:
        return _classified("rechazada", "603 rechazo activo antes de descolgar", 0.97)
    if isinstance(sip, int) and 500 <= sip <= 599:
        return _classified("otro", f"fallo de trunk SIP {sip}", 0.9)
    if amd_result == "machine-ivr":
        return _classified("otro", "contestador IVR; no encaja en el catálogo", 0.88)
    if amd_result in {"machine-vm", "machine-unavailable"}:
        return _classified("buzon", "el AMD detectó buzón de voz", 0.93)
    if appointment:
        return _classified(
            "visita_reservada",
            "la llamada termina con cita creada en el CRM",
            0.99,
        )
    return None


def classify_signaling(
    state: OrchestratorState,
) -> Command[Literal["classify_conversation", "plan_orders"]]:
    result = classify_from_signaling(state["event"])
    if result:
        return Command(update=result, goto="plan_orders")
    return Command(update={}, goto="classify_conversation")
