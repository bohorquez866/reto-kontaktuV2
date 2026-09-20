from __future__ import annotations

from src.nodes.classify_rules import classify_by_rules


def _talk(*pairs, **slots):
    transcript = []
    t = 1
    for role, message in pairs:
        transcript.append({"role": role, "message": message, "time_in_call_secs": t})
        t += 5
    return {
        "transcript": transcript,
        "agent_outcome": {"appointment": None, "slots_snapshot": slots},
    }


def test_dnc_wins_over_found_apartment():
    event = _talk(("user", "Ya encontré piso y no me llaméis más. Dadme de baja."))
    assert classify_by_rules(event)["etiqueta"] == "no_contactar"


def test_descartado_without_dnc():
    event = _talk(("user", "Ya no busco, alquilé la semana pasada."))
    assert classify_by_rules(event)["etiqueta"] == "descartado"


def test_persona_equivocada():
    event = _talk(("user", "Aquí no vive ninguna Elena. Se ha equivocado."))
    assert classify_by_rules(event)["etiqueta"] == "persona_equivocada"


def test_documentacion_enviada_from_slots():
    event = _talk(
        ("user", "Sí, mándamelo por WhatsApp."),
        docs_enviadas=True,
        canal_consentido="whatsapp",
    )
    assert classify_by_rules(event)["etiqueta"] == "documentacion_enviada"


def test_documentacion_pendiente_rejects_whatsapp():
    event = _talk(
        ("user", "No, por WhatsApp no. Mándamelo al correo."),
        docs_enviadas=False,
        canal_consentido="email",
    )
    assert classify_by_rules(event)["etiqueta"] == "documentacion_pendiente"
    assert classify_by_rules(event)["whatsapp_rechazado"] is True


def test_callback_from_raw_slot():
    event = _talk(("user", "Llámame mañana."), callback_when_raw="mañana a las seis")
    assert classify_by_rules(event)["etiqueta"] == "callback"


def test_ahora_no_puedo_without_request_is_not_callback():
    event = _talk(("user", "Ahora no puedo, estoy en una reunión."))
    assert classify_by_rules(event)["etiqueta"] != "callback"


def test_visita_sin_confirmar_from_verbal_slot():
    event = _talk(
        ("user", "El jueves a las cinco me viene bien."),
        visita_acordada_verbal="2026-09-17T17:00:00+02:00",
    )
    assert classify_by_rules(event)["etiqueta"] == "visita_sin_confirmar"


def test_cortada_from_cut_off_utterance():
    event = _talk(("user", "Pues entre los dos unos mil dosci…"))
    assert classify_by_rules(event)["etiqueta"] == "cortada"


def test_unmatched_conversation_is_otro():
    event = _talk(("user", "Vale, lo pienso y ya te digo."))
    assert classify_by_rules(event)["etiqueta"] == "otro"
