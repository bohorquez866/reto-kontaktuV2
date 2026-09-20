from __future__ import annotations

from src.labels import DNC_HINTS, WA_REJECT_HINTS
from src.orders import slots_of, user_text


WRONG_PERSON_HINTS = (
    "se ha equivocado",
    "se han equivocado",
    "aquí no vive",
    "aqui no vive",
    "número equivocado",
    "numero equivocado",
    "no es el lead",
    "no soy ",
)

DISCARDED_HINTS = (
    "ya compré",
    "ya compre",
    "ya he comprado",
    "ya alquilé",
    "ya alquile",
    "ya he alquilado",
    "ya no busco",
    "ya encontré",
    "ya encontre",
    "ya lo tengo",
    "ya hemos firmado",
)

CALLBACK_HINTS = (
    "llámame",
    "llamame",
    "me puedes llamar",
    "puedes llamarme",
    "me llamáis",
    "me llamais",
    "llamar mañana",
    "llamar el ",
    "en otro momento",
    "a otra hora",
)

DOC_HINTS = (
    "documentación",
    "documentacion",
    "nota simple",
    "certificado energético",
    "certificado energetico",
    "enlace",
)

VISIT_HINTS = (
    "visita",
    "verlo",
    "verla",
    "ver el piso",
    "quedamos",
)


def _joined_transcript(event: dict) -> str:
    return " ".join(turn["message"] for turn in (event.get("transcript") or [])).lower()


def _last_user(event: dict) -> str:
    users = [turn["message"] for turn in (event.get("transcript") or []) if turn.get("role") == "user"]
    return users[-1] if users else ""


def _wa_rejected(event: dict) -> bool:
    slots = slots_of(event)
    if slots.get("canal_consentido") == "email":
        return True
    text = user_text(event).lower()
    return any(hint in text for hint in WA_REJECT_HINTS)


def classify_by_rules(event: dict) -> dict:
    users = user_text(event).lower()
    full = _joined_transcript(event)
    slots = slots_of(event)
    last_user = _last_user(event)
    wa_rechazado = _wa_rejected(event)

    if any(hint in users for hint in DNC_HINTS):
        return {
            "etiqueta": "no_contactar",
            "motivo": "el lead pide explícitamente no ser contactado",
            "confianza": 0.96,
            "whatsapp_rechazado": wa_rechazado,
        }

    if any(hint in users for hint in DISCARDED_HINTS):
        return {
            "etiqueta": "descartado",
            "motivo": "el lead ya no busca o ya cerró operación",
            "confianza": 0.9,
            "whatsapp_rechazado": wa_rechazado,
        }

    if any(hint in users for hint in WRONG_PERSON_HINTS):
        return {
            "etiqueta": "persona_equivocada",
            "motivo": "quien contesta no es el lead",
            "confianza": 0.95,
            "whatsapp_rechazado": wa_rechazado,
        }

    docs_sent = bool(slots.get("docs_enviadas")) or "te lo acabo de enviar" in full
    wants_docs = any(hint in users for hint in DOC_HINTS) or slots.get("docs_enviadas") is False
    if docs_sent and not wa_rechazado and (
        slots.get("canal_consentido") == "whatsapp" or "whatsapp" in users
    ):
        return {
            "etiqueta": "documentacion_enviada",
            "motivo": "el agente envió la documentación y el lead aceptó WhatsApp",
            "confianza": 0.94,
            "whatsapp_rechazado": False,
        }
    if wants_docs and wa_rechazado:
        return {
            "etiqueta": "documentacion_pendiente",
            "motivo": "el lead pide documentación y rechaza WhatsApp",
            "confianza": 0.94,
            "whatsapp_rechazado": True,
        }

    if slots.get("callback_when_raw") or any(hint in users for hint in CALLBACK_HINTS):
        return {
            "etiqueta": "callback",
            "motivo": "el lead pide que se le llame en otro momento",
            "confianza": 0.93,
            "callback_when": None,
            "whatsapp_rechazado": wa_rechazado,
        }

    verbal = slots.get("visita_acordada_verbal")
    if verbal or (
        any(hint in users for hint in VISIT_HINTS)
        and not (event.get("agent_outcome") or {}).get("appointment")
        and ("me viene bien" in users or "me va perfecto" in users or "quedamos" in users)
    ):
        return {
            "etiqueta": "visita_sin_confirmar",
            "motivo": "se acordó visita de palabra y no se reservó en el CRM",
            "confianza": 0.92,
            "whatsapp_rechazado": wa_rechazado,
            "nota_contexto": f"visita verbal {verbal}" if verbal else None,
        }

    agent_turns = [turn["message"] for turn in (event.get("transcript") or []) if turn.get("role") == "agent"]
    last_agent = agent_turns[-1] if agent_turns else ""
    cut_off = last_user.endswith(("…", "...")) or last_agent.endswith(("…", "..."))
    if cut_off:
        return {
            "etiqueta": "cortada",
            "motivo": "la llamada se cortó a mitad de la cualificación",
            "confianza": 0.86,
            "whatsapp_rechazado": wa_rechazado,
        }

    return {
        "etiqueta": "otro",
        "motivo": "la conversación no encaja en el catálogo",
        "confianza": 0.55,
        "whatsapp_rechazado": wa_rechazado,
    }
