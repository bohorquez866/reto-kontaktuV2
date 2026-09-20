from __future__ import annotations

from tests.conftest import load_event

from src.nodes.plan_orders import plan_orders


def _ops(result):
    return [order["operacion"] for order in result["planned_orders"]]


def _plan(event, campana, etiqueta, **extra):
    state = {
        "event": event,
        "campana": campana,
        "etiqueta": etiqueta,
        "motivo": "test",
        "confianza": 0.9,
        "attempts_before": extra.pop("attempts_before", 0),
        "cut_count_before": extra.pop("cut_count_before", 0),
        "lead_dnc": extra.pop("lead_dnc", False),
        "whatsapp_rechazado": extra.pop("whatsapp_rechazado", False),
        "callback_when": extra.pop("callback_when", None),
        "nota_contexto": extra.pop("nota_contexto", None),
    }
    state.update(extra)
    return plan_orders(state)


def test_ocupado_schedules_plus_60(campana):
    result = _plan(load_event("02-call-ended-tomas.json"), campana, "ocupado")
    assert _ops(result) == ["cerrar_llamada", "programar_llamada"]
    call = result["planned_orders"][1]
    assert call["cuerpo"]["no_antes_de"] == "2026-09-15T11:31:00+02:00"
    assert result["planned_orders"][0]["cuerpo"]["status"] == "no_answer"


def test_visita_reservada_task_due_two_hours_before(campana):
    result = _plan(load_event("07-call-ended-laura.json"), campana, "visita_reservada")
    task = next(order for order in result["planned_orders"] if order["operacion"] == "crear_tarea")
    assert task["cuerpo"]["tipo"] == "confirmar_visita_direccion"
    assert task["cuerpo"]["vence_el"] == "2026-09-17T09:00:00+02:00"


def test_documentacion_enviada_two_reminders(campana):
    result = _plan(load_event("08-call-ended-marcos.json"), campana, "documentacion_enviada")
    reminders = [o for o in result["planned_orders"] if o["operacion"] == "programar_recordatorio"]
    assert len(reminders) == 2
    assert reminders[0]["cuerpo"]["canal"] == "whatsapp_lead"
    assert reminders[0]["cuerpo"]["cuando"] == "2026-09-17T16:42:00+02:00"
    assert reminders[1]["cuerpo"]["canal"] == "tarea_comercial"
    assert reminders[1]["cuerpo"]["cuando"] == "2026-09-18T16:42:00+02:00"
    assert "reminder_id" in reminders[0]


def test_callback_requested_time(campana):
    result = _plan(load_event("09-call-ended-javier.json"), campana, "callback")
    call = next(o for o in result["planned_orders"] if o["operacion"] == "programar_llamada")
    assert call["cuerpo"]["no_antes_de"] == "2026-09-16T18:00:00+02:00"


def test_callback_outside_window_sends_aviso(campana):
    event = load_event("09-call-ended-javier.json")
    result = _plan(event, campana, "callback", callback_when="2026-09-20T11:00:00+02:00")
    ops = _ops(result)
    assert "programar_llamada" in ops
    assert "enviar_plantilla_whatsapp" in ops
    call = next(o for o in result["planned_orders"] if o["operacion"] == "programar_llamada")
    wa = next(o for o in result["planned_orders"] if o["operacion"] == "enviar_plantilla_whatsapp")
    assert call["cuerpo"]["no_antes_de"] == "2026-09-21T10:00:00+02:00"
    assert wa["cuerpo"]["plantilla"] == "aviso_cambio_hora"


def test_exhausted_voicemail_uses_backup(campana):
    result = _plan(load_event("12-call-ended-nuria.json"), campana, "buzon", attempts_before=2)
    ops = _ops(result)
    assert ops == ["cerrar_llamada", "enviar_plantilla_whatsapp"]
    assert result["planned_orders"][1]["cuerpo"]["plantilla"] == "primer_toque_respaldo"


def test_backup_without_whatsapp_creates_manual_task(campana):
    result = _plan(
        load_event("12-call-ended-nuria.json"),
        campana,
        "rechazada",
        whatsapp_rechazado=True,
    )
    tasks = [o for o in result["planned_orders"] if o["operacion"] == "crear_tarea"]
    assert tasks and tasks[0]["cuerpo"]["tipo"] == "llamar_a_mano"


def test_no_contactar_has_no_outbound_call(campana):
    result = _plan(load_event("06-call-ended-pedro.json"), campana, "no_contactar")
    assert _ops(result) == ["cerrar_llamada", "marcar_no_contactar"]
    assert result["planned_orders"][1]["cuerpo"]["canal"] == "todos"


def test_prior_dnc_strips_outbound_orders(campana):
    result = _plan(load_event("02-call-ended-tomas.json"), campana, "ocupado", lead_dnc=True)
    assert _ops(result) == ["cerrar_llamada"]


def test_second_cut_adds_revisar_llamada(campana):
    result = _plan(load_event("04-call-ended-rosa.json"), campana, "cortada", cut_count_before=1)
    tipos = [o["cuerpo"]["tipo"] for o in result["planned_orders"] if o["operacion"] == "crear_tarea"]
    assert "revisar_llamada" in tipos


def test_visita_sin_confirmar_does_not_reserve(campana):
    result = _plan(load_event("11-call-ended-carla.json"), campana, "visita_sin_confirmar")
    assert "crear_tarea" not in _ops(result) or all(
        o["cuerpo"].get("tipo") != "confirmar_visita_direccion"
        for o in result["planned_orders"]
        if o["operacion"] == "crear_tarea"
    )
    call = next(o for o in result["planned_orders"] if o["operacion"] == "programar_llamada")
    assert call["cuerpo"]["no_antes_de"] == "2026-09-15T18:20:00+02:00"


def test_descartado_only_closes(campana):
    result = _plan(load_event("03-call-ended-elena.json"), campana, "descartado")
    assert _ops(result) == ["cerrar_llamada"]
    assert result["planned_orders"][0]["cuerpo"]["status"] == "skipped"
