from __future__ import annotations

from src.nodes.classify_signaling import classify_from_signaling


def _event(sip=200, transcript=None, amd=None, appointment=None):
    return {
        "telephony": {
            "sip_status_code": sip,
            "sip_status": "OK",
            "amd": amd or {"result": "not_run", "source": "none"},
        },
        "transcript": transcript or [],
        "agent_outcome": {"appointment": appointment, "slots_snapshot": {}},
    }


def test_408_and_480_are_sin_respuesta():
    assert classify_from_signaling(_event(408))["etiqueta"] == "sin_respuesta"
    assert classify_from_signaling(_event(480))["etiqueta"] == "sin_respuesta"


def test_408_with_transcript_falls_through():
    assert classify_from_signaling(_event(408, transcript=[{"role": "user", "message": "hola"}])) is None


def test_486_is_ocupado_even_if_user_rejected():
    event = _event(486)
    event["telephony"]["sip_status"] = "Busy Here"
    event["telephony"]["disconnect_reason"] = "USER_REJECTED"
    assert classify_from_signaling(event)["etiqueta"] == "ocupado"


def test_603_is_rechazada():
    assert classify_from_signaling(_event(603))["etiqueta"] == "rechazada"


def test_5xx_and_ivr_are_otro():
    assert classify_from_signaling(_event(503))["etiqueta"] == "otro"
    assert classify_from_signaling(_event(200, amd={"result": "machine-ivr"}))["etiqueta"] == "otro"


def test_voicemail_is_buzon_regardless_of_source():
    livekit = classify_from_signaling(_event(200, amd={"result": "machine-vm", "source": "livekit_amd"}))
    heuristic = classify_from_signaling(
        _event(200, amd={"result": "machine-unavailable", "source": "heuristic_regex"})
    )
    assert livekit["etiqueta"] == "buzon"
    assert heuristic["etiqueta"] == "buzon"


def test_uncertain_amd_is_treated_as_person():
    assert classify_from_signaling(_event(200, amd={"result": "uncertain"})) is None


def test_appointment_is_visita_reservada():
    result = classify_from_signaling(
        _event(200, appointment={"appointment_id": "apt_1", "start_time": "2026-09-17T11:00:00+02:00"})
    )
    assert result["etiqueta"] == "visita_reservada"
