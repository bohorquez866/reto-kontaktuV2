from __future__ import annotations

from typing import Annotated, Any, Optional

import operator
from typing_extensions import TypedDict


class OrchestratorState(TypedDict, total=False):
    event: dict[str, Any]
    campana: dict[str, Any]
    etiqueta: str
    motivo: str
    confianza: float
    call_id: Optional[str]
    skip_orders: bool
    is_redelivery: bool
    is_foreign_org: bool
    is_message: bool
    persist_lead: bool
    attempts_before: int
    attempts_after: int
    cut_count_before: int
    lead_dnc: bool
    whatsapp_rechazado: bool
    callback_when: Optional[str]
    nota_contexto: Optional[str]
    pending_reminders: list[dict[str, Any]]
    planned_orders: list[dict[str, Any]]
    emitted_order_ids: Annotated[list[str], operator.add]
