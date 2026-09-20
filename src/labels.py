QUEUE_STATUS = {
    "visita_reservada": "successful",
    "documentacion_enviada": "completed",
    "documentacion_pendiente": "completed",
    "callback": "callback_requested",
    "sin_respuesta": "no_answer",
    "ocupado": "no_answer",
    "buzon": "no_answer",
    "cortada": "needs_review",
    "visita_sin_confirmar": "needs_review",
    "otro": "needs_review",
    "persona_equivocada": "failed",
    "no_contactar": "dnc",
    "rechazada": "refused",
    "descartado": "skipped",
}

CUT_LABELS = frozenset({"cortada", "visita_sin_confirmar"})
RETRY_LABELS = frozenset({"sin_respuesta", "ocupado", "buzon"})

TASK_TITLES = {
    "confirmar_visita_direccion": "Confirmar dirección de la visita",
    "verificar_telefono": "Verificar teléfono del lead",
    "enviar_documentacion_email": "Enviar documentación por email",
    "llamar_a_mano": "Llamar a mano al lead",
    "revisar_llamada": "Revisar la llamada",
}

DNC_HINTS = (
    "no me llam",
    "no me volváis a llam",
    "no me vuelvan a llam",
    "no volver a llam",
    "no me contact",
    "no contactar",
    "dadme de baja",
    "denme de baja",
    "dame de baja",
    "darme de baja",
    "quiero la baja",
    "no quiero que me llam",
    "no me escrib",
    "borra mi número",
    "borra mi numero",
)

WA_REJECT_HINTS = (
    "por whatsapp no",
    "whatsapp no",
    "no por whatsapp",
    "no uso whatsapp",
    "el whatsapp no lo uso",
    "nada de whatsapp",
)
