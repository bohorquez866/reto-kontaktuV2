from __future__ import annotations

from datetime import timedelta
from typing import Any

from src.labels import CUT_LABELS, QUEUE_STATUS, RETRY_LABELS, TASK_TITLES
from src.orders import build_order, nota_contexto, reminder_id_for, slots_of
from src.scheduling import (
    add_business_days,
    add_hours,
    add_minutes,
    add_natural_days,
    format_iso,
    in_window,
    parse_dt,
    resolve_callback_when,
    snap_to_window,
)
from src.state import OrchestratorState


def _event_key(event: dict) -> str:
    return event["idempotency_key"]


def _cerrar(event: dict, etiqueta: str, motivo: str, confianza: float) -> dict[str, Any]:
    telephony = event.get("telephony") or {}
    return build_order(
        event["event_id"],
        _event_key(event),
        "cerrar_llamada",
        {
            "entry_id": event["campaign"]["entry_id"],
            "status": QUEUE_STATUS[etiqueta],
            "etiqueta": etiqueta,
            "motivo": motivo,
            "confianza": confianza,
            "duration_seconds": telephony.get("duration_seconds", 0),
        },
    )


def _programar_llamada(event: dict, when: str, motivo: str, nota: str) -> dict[str, Any]:
    return build_order(
        event["event_id"],
        _event_key(event),
        "programar_llamada",
        {
            "entry_id": event["campaign"]["entry_id"],
            "telefono": event["lead"]["phone"],
            "no_antes_de": when,
            "motivo": motivo,
            "nota_contexto": nota,
        },
    )


def _tarea(event: dict, tipo: str, vence_el: str, detalle: str, suffix: str = "") -> dict[str, Any]:
    return build_order(
        event["event_id"],
        _event_key(event),
        "crear_tarea",
        {
            "contact_id": event["lead"]["contact_id"],
            "call_id": (event.get("telephony") or {}).get("call_id"),
            "tipo": tipo,
            "titulo": TASK_TITLES[tipo],
            "detalle": detalle,
            "vence_el": vence_el,
            "asignada_a": "comercial_asignado",
        },
        suffix=suffix,
    )


def _whatsapp(event: dict, plantilla: str, suffix: str = "") -> dict[str, Any]:
    return build_order(
        event["event_id"],
        _event_key(event),
        "enviar_plantilla_whatsapp",
        {
            "organization_id": event["organization_id"],
            "telefono": event["lead"]["phone"],
            "plantilla": plantilla,
            "parametros": {"nombre": event["lead"].get("full_name") or ""},
            "idioma": event["lead"].get("language") or "es",
        },
        suffix=suffix,
    )


def _recordatorio(
    event: dict,
    canal: str,
    cuando: str,
    suffix: str,
    plantilla: str | None = None,
    tipo_tarea: str | None = None,
) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "contact_id": event["lead"]["contact_id"],
        "canal": canal,
        "cuando": cuando,
        "cancelar_si": "lead_responde",
    }
    if plantilla:
        cuerpo["plantilla"] = plantilla
    if tipo_tarea:
        cuerpo["tipo_tarea"] = tipo_tarea
    order = build_order(
        event["event_id"],
        _event_key(event),
        "programar_recordatorio",
        cuerpo,
        suffix=suffix,
    )
    order["reminder_id"] = reminder_id_for(order["idempotency_key"])
    return order


def _respaldo(event: dict, campana: dict, when: str, wa_rechazado: bool) -> list[dict[str, Any]]:
    if campana.get("canal_respaldo") == "whatsapp" and not wa_rechazado:
        return [_whatsapp(event, "primer_toque_respaldo")]
    return [
        _tarea(
            event,
            "llamar_a_mano",
            when,
            "se agotaron los intentos de voz y el lead rechazó WhatsApp",
            suffix=":respaldo",
        )
    ]


def plan_orders(state: OrchestratorState) -> dict:
    event = state["event"]
    campana = state["campana"]
    etiqueta = state["etiqueta"]
    motivo = state["motivo"]
    confianza = state["confianza"]
    occurred = parse_dt(event["occurred_at"], campana)
    attempts_after = state.get("attempts_before", 0) + 1
    max_attempts = campana["reintentos"]["max_intentos"]
    exhausted = attempts_after >= max_attempts
    wa_rechazado = bool(state.get("whatsapp_rechazado"))
    default_vence = format_iso(
        add_natural_days(occurred, campana["tareas"]["vencimiento_por_defecto_dias"])
    )
    nota = state.get("nota_contexto") or nota_contexto(event, "no se llegó a hablar con el lead")

    orders: list[dict[str, Any]] = [_cerrar(event, etiqueta, motivo, confianza)]

    if etiqueta == "no_contactar":
        orders.append(
            build_order(
                event["event_id"],
                _event_key(event),
                "marcar_no_contactar",
                {
                    "telefono": event["lead"]["phone"],
                    "contact_id": event["lead"]["contact_id"],
                    "canal": "todos",
                    "motivo": motivo,
                    "origen": event.get("idempotency_key"),
                },
            )
        )
    elif etiqueta == "visita_reservada":
        start = parse_dt(event["agent_outcome"]["appointment"]["start_time"], campana)
        vence = start - timedelta(hours=campana["tareas"]["confirmar_visita_margen_horas"])
        orders.append(
            _tarea(
                event,
                "confirmar_visita_direccion",
                format_iso(vence),
                "el lead reservó visita; falta confirmar la dirección exacta",
            )
        )
    elif etiqueta == "documentacion_enviada":
        lead_when = format_iso(add_hours(occurred, campana["recordatorios"]["documentacion_lead_horas"]))
        comercial_when = format_iso(
            add_business_days(
                occurred,
                campana["recordatorios"]["seguimiento_comercial_dias_habiles"],
                campana,
            )
        )
        orders.append(
            _recordatorio(
                event,
                "whatsapp_lead",
                lead_when,
                ":lead",
                plantilla="recordatorio_documentacion",
            )
        )
        orders.append(
            _recordatorio(
                event,
                "tarea_comercial",
                comercial_when,
                ":comercial",
                tipo_tarea="llamar_a_mano",
            )
        )
    elif etiqueta == "callback":
        slots = slots_of(event)
        requested = resolve_callback_when(
            slots.get("callback_when_raw"),
            state.get("callback_when"),
            occurred,
            campana,
        )
        if requested is None:
            requested = add_hours(occurred, campana["reintentos"]["separacion_minima_horas"])
        snapped = snap_to_window(requested, campana)
        orders.append(
            _programar_llamada(
                event,
                format_iso(snapped),
                "callback solicitado",
                nota_contexto(event, "pidió que se le llame en otro momento"),
            )
        )
        if not in_window(requested, campana) and not wa_rechazado:
            orders.append(_whatsapp(event, "aviso_cambio_hora", suffix=":cambio_hora"))
    elif etiqueta in RETRY_LABELS:
        if exhausted:
            orders.extend(_respaldo(event, campana, default_vence, wa_rechazado))
        elif etiqueta == "ocupado":
            when = snap_to_window(add_minutes(occurred, 60), campana)
            orders.append(
                _programar_llamada(
                    event,
                    format_iso(when),
                    "línea comunicando, reintento corto",
                    "no se llegó a hablar con el lead",
                )
            )
        else:
            hours = campana["reintentos"]["separacion_minima_horas"]
            when = snap_to_window(add_hours(occurred, hours), campana)
            motivo_llamada = (
                "buzón de voz, reintento con separación mínima"
                if etiqueta == "buzon"
                else "sin respuesta, reintento con separación mínima"
            )
            orders.append(
                _programar_llamada(event, format_iso(when), motivo_llamada, "no se llegó a hablar con el lead")
            )
    elif etiqueta in CUT_LABELS:
        when = snap_to_window(
            add_minutes(occurred, campana["reintentos"]["cortada_minutos_min"]),
            campana,
        )
        orders.append(
            _programar_llamada(
                event,
                format_iso(when),
                "llamada cortada, recuperación el mismo día",
                nota,
            )
        )
        if state.get("cut_count_before", 0) >= 1:
            orders.append(
                _tarea(
                    event,
                    "revisar_llamada",
                    default_vence,
                    "segunda llamada cortada con el mismo lead",
                    suffix=":n4",
                )
            )
    elif etiqueta == "persona_equivocada":
        orders.append(
            _tarea(
                event,
                "verificar_telefono",
                default_vence,
                "quien contestó no es el lead",
            )
        )
    elif etiqueta == "rechazada":
        orders.extend(_respaldo(event, campana, default_vence, wa_rechazado))
    elif etiqueta == "documentacion_pendiente":
        email = slots_of(event).get("email_declarado")
        detalle = "el lead quiere documentación por email"
        if email:
            detalle += f" ({email})"
        orders.append(_tarea(event, "enviar_documentacion_email", default_vence, detalle))
    elif etiqueta == "otro":
        orders.append(_tarea(event, "revisar_llamada", default_vence, motivo, suffix=":otro"))

    if state.get("lead_dnc") and etiqueta != "no_contactar":
        orders = [order for order in orders if order["operacion"] == "cerrar_llamada"]

    return {
        "planned_orders": orders,
        "attempts_after": attempts_after,
        "nota_contexto": nota,
    }
