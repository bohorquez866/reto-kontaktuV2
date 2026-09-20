from __future__ import annotations

import json
import os
from typing import Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config import load_prompt
from src.labels import DNC_HINTS, WA_REJECT_HINTS
from src.nodes.classify_rules import classify_by_rules
from src.orders import slots_of, user_text
from src.state import OrchestratorState


CONVERSATION_LABELS = Literal[
    "no_contactar",
    "descartado",
    "persona_equivocada",
    "documentacion_enviada",
    "documentacion_pendiente",
    "callback",
    "visita_sin_confirmar",
    "cortada",
    "otro",
]


class ConversationResult(BaseModel):
    etiqueta: CONVERSATION_LABELS
    motivo: str = Field(description="Una frase. Texto libre.")
    confianza: float = Field(ge=0, le=1)
    callback_when: Optional[str] = Field(
        default=None,
        description="ISO-8601 con offset si la etiqueta es callback, si no null.",
    )
    nota_contexto: Optional[str] = None
    whatsapp_rechazado: bool = False


def _format_transcript(event: dict) -> str:
    lines = []
    for turn in event.get("transcript") or []:
        lines.append(f"[{turn['time_in_call_secs']}s] {turn['role']}: {turn['message']}")
    return "\n".join(lines) if lines else "(sin transcripción)"


def _dnc_override(event: dict) -> bool:
    text = user_text(event).lower()
    return any(hint in text for hint in DNC_HINTS)


def _wa_rejected(event: dict, model_flag: bool) -> bool:
    if model_flag:
        return True
    slots = slots_of(event)
    if slots.get("canal_consentido") == "email":
        return True
    text = user_text(event).lower()
    return any(hint in text for hint in WA_REJECT_HINTS)


def _call_llm(event: dict) -> ConversationResult:
    model_name = os.environ.get("MODELO", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0).with_structured_output(ConversationResult)
    payload = {
        "occurred_at": event["occurred_at"],
        "lead_name": event["lead"].get("full_name"),
        "slots_snapshot": slots_of(event),
        "appointment": (event.get("agent_outcome") or {}).get("appointment"),
        "telephony": {
            "sip_status_code": (event.get("telephony") or {}).get("sip_status_code"),
            "hung_up_by": (event.get("telephony") or {}).get("hung_up_by"),
            "disconnect_reason": (event.get("telephony") or {}).get("disconnect_reason"),
            "amd": (event.get("telephony") or {}).get("amd"),
        },
        "transcript": _format_transcript(event),
    }
    return llm.invoke(
        [
            SystemMessage(content=load_prompt()),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, indent=2)),
        ]
    )


def classify_conversation(state: OrchestratorState) -> dict:
    event = state["event"]
    fallback = classify_by_rules(event)
    etiqueta = fallback["etiqueta"]
    motivo = fallback["motivo"]
    confianza = fallback["confianza"]
    callback_when = fallback.get("callback_when")
    nota = fallback.get("nota_contexto")
    wa_flag = bool(fallback.get("whatsapp_rechazado"))

    if os.environ.get("OPENAI_API_KEY"):
        result = _call_llm(event)
        etiqueta = result.etiqueta
        motivo = result.motivo
        confianza = result.confianza
        callback_when = result.callback_when or callback_when
        nota = result.nota_contexto or nota
        wa_flag = result.whatsapp_rechazado or wa_flag

    if _dnc_override(event):
        etiqueta = "no_contactar"
        motivo = "el lead pide explícitamente no ser contactado"
        confianza = max(confianza, 0.95)

    return {
        "etiqueta": etiqueta,
        "motivo": motivo,
        "confianza": confianza,
        "callback_when": callback_when,
        "nota_contexto": nota,
        "whatsapp_rechazado": _wa_rejected(event, wa_flag) or state.get("whatsapp_rechazado", False),
    }
