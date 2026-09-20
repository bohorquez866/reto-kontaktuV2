from __future__ import annotations

from pathlib import Path

from tests.conftest import invoke_event, load_event, read_jsonl

EXPECTED_LABELS = {
    "01-call-ended-nuria.json": "sin_respuesta",
    "02-call-ended-tomas.json": "ocupado",
    "03-call-ended-elena.json": "persona_equivocada",
    "04-call-ended-rosa.json": "cortada",
    "05-call-ended-nuria.json": "sin_respuesta",
    "06-call-ended-pedro.json": "no_contactar",
    "07-call-ended-laura.json": "visita_reservada",
    "08-call-ended-marcos.json": "documentacion_enviada",
    "09-call-ended-javier.json": "callback",
    "10-call-ended-sonia.json": "buzon",
    "11-call-ended-carla.json": "visita_sin_confirmar",
    "12-call-ended-nuria.json": "buzon",
    "13-call-ended-ivan.json": "documentacion_pendiente",
    "14-message-received-marcos.json": "no_aplica",
    "15-call-ended-javier-reentrega.json": "callback",
    "16-call-ended-alberto.json": "no_aplica",
}

LOTE_ORDER = [
    "01-call-ended-nuria.json",
    "02-call-ended-tomas.json",
    "03-call-ended-elena.json",
    "04-call-ended-rosa.json",
    "05-call-ended-nuria.json",
    "06-call-ended-pedro.json",
    "07-call-ended-laura.json",
    "08-call-ended-marcos.json",
    "09-call-ended-javier.json",
    "10-call-ended-sonia.json",
    "11-call-ended-carla.json",
    "12-call-ended-nuria.json",
    "13-call-ended-ivan.json",
    "14-message-received-marcos.json",
    "15-call-ended-javier-reentrega.json",
    "16-call-ended-alberto.json",
]


def _by_event(ordenes: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for order in ordenes:
        grouped.setdefault(order["event_id"], []).append(order)
    return grouped


def test_tomas_matches_solved_example(isolated_salida, campana):
    tmp_path, _store = isolated_salida
    invoke_event(load_event("02-call-ended-tomas.json"), campana)
    decisions = read_jsonl(tmp_path / "decisiones.jsonl")
    orders = read_jsonl(tmp_path / "ordenes.jsonl")
    assert decisions[0]["etiqueta"] == "ocupado"
    assert [item["operacion"] for item in orders] == ["cerrar_llamada", "programar_llamada"]
    assert orders[1]["cuerpo"]["no_antes_de"] == "2026-09-15T11:31:00+02:00"


def test_redelivery_repeats_label_without_orders(isolated_salida, campana):
    tmp_path, _store = isolated_salida
    invoke_event(load_event("09-call-ended-javier.json"), campana)
    invoke_event(load_event("15-call-ended-javier-reentrega.json"), campana)
    decisions = read_jsonl(tmp_path / "decisiones.jsonl")
    orders = read_jsonl(tmp_path / "ordenes.jsonl")
    assert decisions[1]["event_id"] == "evt_15"
    assert decisions[1]["etiqueta"] == "callback"
    assert decisions[1]["ordenes"] == []
    assert all(item["event_id"] != "evt_15" for item in orders)


def test_foreign_org_writes_no_aplica(isolated_salida, campana):
    tmp_path, _store = isolated_salida
    invoke_event(load_event("16-call-ended-alberto.json"), campana)
    decisions = read_jsonl(tmp_path / "decisiones.jsonl")
    assert decisions[0]["etiqueta"] == "no_aplica"
    assert read_jsonl(tmp_path / "ordenes.jsonl") == []


def test_nuria_third_attempt_uses_backup(isolated_salida, campana):
    tmp_path, store = isolated_salida
    for name in ("01-call-ended-nuria.json", "05-call-ended-nuria.json", "12-call-ended-nuria.json"):
        invoke_event(load_event(name), campana)
    lead = store.get_lead("c_301")
    assert lead["attempts"] == 3
    orders = _by_event(read_jsonl(tmp_path / "ordenes.jsonl"))
    evt12 = [item["operacion"] for item in orders["evt_12"]]
    assert evt12 == ["cerrar_llamada", "enviar_plantilla_whatsapp"]


def test_marcos_message_cancels_both_reminders(isolated_salida, campana):
    tmp_path, store = isolated_salida
    invoke_event(load_event("08-call-ended-marcos.json"), campana)
    invoke_event(load_event("14-message-received-marcos.json"), campana)
    pending = store.get_pending_reminders("c_302")
    assert pending == []
    cancels = [
        item for item in read_jsonl(tmp_path / "ordenes.jsonl") if item["event_id"] == "evt_14"
    ]
    assert len(cancels) == 2
    assert {item["operacion"] for item in cancels} == {"cancelar_recordatorio"}


def test_full_sample_lote(isolated_salida, campana):
    tmp_path, _store = isolated_salida
    for name in LOTE_ORDER:
        invoke_event(load_event(name), campana)
    decisions = read_jsonl(tmp_path / "decisiones.jsonl")
    assert len(decisions) == 16
    by_file = {name: load_event(name)["event_id"] for name in LOTE_ORDER}
    labels = {item["event_id"]: item["etiqueta"] for item in decisions}
    for name, event_id in by_file.items():
        assert labels[event_id] == EXPECTED_LABELS[name]
    orders = _by_event(read_jsonl(tmp_path / "ordenes.jsonl"))
    assert "evt_15" not in orders
    assert "evt_16" not in orders


def test_cli_requires_single_argument():
    from run import main

    assert main([]) == 1
    assert main(["a.json", "b.json"]) == 1
