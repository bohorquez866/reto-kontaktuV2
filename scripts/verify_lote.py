#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_campana
from src.nodes.classify_rules import classify_by_rules
from src.nodes.classify_signaling import classify_from_signaling
from src.scheduling import format_iso, parse_dt, parse_spanish_callback, snap_to_window


EXPECTED_LABELS = {
    "evt_01": "sin_respuesta",
    "evt_02": "ocupado",
    "evt_03": "persona_equivocada",
    "evt_04": "cortada",
    "evt_05": "sin_respuesta",
    "evt_06": "no_contactar",
    "evt_07": "visita_reservada",
    "evt_08": "documentacion_enviada",
    "evt_09": "callback",
    "evt_10": "buzon",
    "evt_11": "visita_sin_confirmar",
    "evt_12": "buzon",
    "evt_13": "documentacion_pendiente",
    "evt_14": "no_aplica",
    "evt_15": "callback",
    "evt_16": "no_aplica",
}

EXPECTED_OPS = {
    "evt_01": ["cerrar_llamada", "programar_llamada"],
    "evt_02": ["cerrar_llamada", "programar_llamada"],
    "evt_03": ["cerrar_llamada", "crear_tarea"],
    "evt_04": ["cerrar_llamada", "programar_llamada"],
    "evt_05": ["cerrar_llamada", "programar_llamada"],
    "evt_06": ["cerrar_llamada", "marcar_no_contactar"],
    "evt_07": ["cerrar_llamada", "crear_tarea"],
    "evt_08": ["cerrar_llamada", "programar_recordatorio", "programar_recordatorio"],
    "evt_09": ["cerrar_llamada", "programar_llamada"],
    "evt_10": ["cerrar_llamada", "programar_llamada"],
    "evt_11": ["cerrar_llamada", "programar_llamada"],
    "evt_12": ["cerrar_llamada", "enviar_plantilla_whatsapp"],
    "evt_13": ["cerrar_llamada", "crear_tarea"],
    "evt_14": ["cancelar_recordatorio", "cancelar_recordatorio"],
    "evt_15": [],
    "evt_16": [],
}

EXPECTED_WHEN = {
    "evt_01": "2026-09-15T12:12:00+02:00",
    "evt_02": "2026-09-15T11:31:00+02:00",
    "evt_04": "2026-09-15T12:17:00+02:00",
    "evt_05": "2026-09-15T14:20:00+02:00",
    "evt_09": "2026-09-16T18:00:00+02:00",
    "evt_10": "2026-09-15T19:30:00+02:00",
    "evt_11": "2026-09-15T18:20:00+02:00",
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"falta {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check_scheduling_helpers() -> list[str]:
    errors: list[str] = []
    campana = load_campana()
    occurred = parse_dt("2026-09-15T17:05:00+02:00", campana)
    parsed = parse_spanish_callback("mañana a las seis", occurred)
    if parsed is None or format_iso(parsed) != "2026-09-16T18:00:00+02:00":
        errors.append(f"callback 'mañana a las seis' -> {parsed}")
    sunday = parse_dt("2026-09-20T11:00:00+02:00", campana)
    snapped = snap_to_window(sunday, campana)
    if format_iso(snapped) != "2026-09-21T10:00:00+02:00":
        errors.append(f"domingo 11:00 debería ir a lunes 10:00, fue {snapped}")

    rejected = classify_from_signaling(
        {"telephony": {"sip_status_code": 603, "sip_status": "Decline", "amd": {}}, "transcript": [], "agent_outcome": {}}
    )
    if not rejected or rejected["etiqueta"] != "rechazada":
        errors.append(f"SIP 603 debía ser rechazada, fue {rejected}")
    trunk = classify_from_signaling(
        {"telephony": {"sip_status_code": 503, "sip_status": "Service Unavailable", "amd": {}}, "transcript": [], "agent_outcome": {}}
    )
    if not trunk or trunk["etiqueta"] != "otro":
        errors.append(f"SIP 5xx debía ser otro, fue {trunk}")
    ivr = classify_from_signaling(
        {
            "telephony": {"sip_status_code": 200, "amd": {"result": "machine-ivr"}},
            "transcript": [],
            "agent_outcome": {},
        }
    )
    if not ivr or ivr["etiqueta"] != "otro":
        errors.append(f"machine-ivr debía ser otro, fue {ivr}")

    from src.nodes.plan_orders import plan_orders

    rosa = json.loads((ROOT / "eventos/04-call-ended-rosa.json").read_text(encoding="utf-8"))
    second_cut = plan_orders(
        {
            "event": rosa,
            "campana": campana,
            "etiqueta": "cortada",
            "motivo": "segunda cortada",
            "confianza": 0.8,
            "cut_count_before": 1,
            "attempts_before": 1,
            "lead_dnc": False,
            "whatsapp_rechazado": False,
        }
    )
    n4_tipos = [
        order["cuerpo"].get("tipo")
        for order in second_cut["planned_orders"]
        if order["operacion"] == "crear_tarea"
    ]
    if "revisar_llamada" not in n4_tipos:
        errors.append("N4: la segunda cortada debía crear revisar_llamada")

    discarded = classify_by_rules(
        {
            "transcript": [
                {"role": "user", "message": "Ya no busco, alquilé la semana pasada.", "time_in_call_secs": 10}
            ],
            "agent_outcome": {"appointment": None, "slots_snapshot": {}},
        }
    )
    if discarded["etiqueta"] != "descartado":
        errors.append(f"descartado esperado, fue {discarded['etiqueta']}")
    return errors


def main() -> int:
    errors = check_scheduling_helpers()
    decisiones = load_jsonl(ROOT / "salida" / "decisiones.jsonl")
    ordenes = load_jsonl(ROOT / "salida" / "ordenes.jsonl")
    by_event = defaultdict(list)
    for order in ordenes:
        by_event[order["event_id"]].append(order)

    if len(decisiones) != 16:
        errors.append(f"se esperaban 16 decisiones, hay {len(decisiones)}")

    for decision in decisiones:
        event_id = decision["event_id"]
        expected = EXPECTED_LABELS.get(event_id)
        if expected and decision["etiqueta"] != expected:
            errors.append(f"{event_id}: etiqueta {decision['etiqueta']} != {expected}")
        ops = [order["operacion"] for order in by_event[event_id]]
        if event_id in EXPECTED_OPS and ops != EXPECTED_OPS[event_id]:
            errors.append(f"{event_id}: operaciones {ops} != {EXPECTED_OPS[event_id]}")
        if event_id in EXPECTED_WHEN:
            calls = [o for o in by_event[event_id] if o["operacion"] == "programar_llamada"]
            if not calls or calls[0]["cuerpo"]["no_antes_de"] != EXPECTED_WHEN[event_id]:
                got = calls[0]["cuerpo"]["no_antes_de"] if calls else None
                errors.append(f"{event_id}: no_antes_de {got} != {EXPECTED_WHEN[event_id]}")

    laura = [o for o in by_event["evt_07"] if o["operacion"] == "crear_tarea"]
    if laura and laura[0]["cuerpo"]["vence_el"] != "2026-09-17T09:00:00+02:00":
        errors.append(f"evt_07 vence_el {laura[0]['cuerpo']['vence_el']}")

    marcos = [o for o in by_event["evt_08"] if o["operacion"] == "programar_recordatorio"]
    if len(marcos) == 2:
        if marcos[0]["cuerpo"]["cuando"] != "2026-09-17T16:42:00+02:00":
            errors.append(f"recordatorio lead {marcos[0]['cuerpo']['cuando']}")
        if marcos[1]["cuerpo"]["cuando"] != "2026-09-18T16:42:00+02:00":
            errors.append(f"recordatorio comercial {marcos[1]['cuerpo']['cuando']}")

    reminder_ids = {o.get("reminder_id") for o in marcos}
    # reminder_id is not in jsonl; recover from cancel bodies
    cancelled = [o["cuerpo"]["reminder_id"] for o in by_event["evt_14"]]
    if len(cancelled) != 2:
        errors.append("evt_14 debía cancelar 2 recordatorios")
    if len(set(cancelled)) != len(cancelled):
        errors.append("evt_14 canceló el mismo reminder dos veces")

    ejemplo_dec = json.loads((ROOT / "ejemplo-resuelto/salida/decisiones.jsonl").read_text())
    ours_02 = next(d for d in decisiones if d["event_id"] == "evt_02")
    if ours_02["etiqueta"] != ejemplo_dec["etiqueta"]:
        errors.append("evt_02 no coincide con el ejemplo resuelto en etiqueta")
    ejemplo_ord = [
        json.loads(line)
        for line in (ROOT / "ejemplo-resuelto/salida/ordenes.jsonl").read_text().splitlines()
        if line.strip()
    ]
    ours_02_ord = by_event["evt_02"]
    if [o["operacion"] for o in ours_02_ord] != [o["operacion"] for o in ejemplo_ord]:
        errors.append("evt_02 operaciones distintas al ejemplo")
    if ours_02_ord and ours_02_ord[1]["cuerpo"]["no_antes_de"] != ejemplo_ord[1]["cuerpo"]["no_antes_de"]:
        errors.append("evt_02 no_antes_de distinto al ejemplo")

    if errors:
        print("FALLÓ la verificación:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("lote de ejemplo: 16/16 decisiones y órdenes esperadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
