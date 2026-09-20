# Orquestador post-llamada

Programa que clasifica un evento de llamada o WhatsApp y escribe las órdenes de CRM que correspondan.

## Cómo se ejecuta

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # OPENAI_API_KEY y MODELO=gpt-4o-mini
python run.py eventos/01-call-ended-nuria.json
```

Cada invocación es un proceso nuevo. El estado (intentos, recordatorios, reentregas, DNC) vive en `salida/orquestador.db`. Las decisiones y órdenes se anexan a `salida/decisiones.jsonl` y `salida/ordenes.jsonl`.

Lote de ejemplo:

```bash
bash scripts/run_lote.sh
python scripts/verify_lote.py
```

El visor estático: abre `visor/index.html` y carga la carpeta `salida/`.

## Modelo

`gpt-4o-mini`. La taxonomía es cerrada y la salida es JSON estructurado; no hace falta un modelo más grande. La señalización SIP/AMD y la cita creada se resuelven sin LLM. Si no hay `OPENAI_API_KEY`, la conversación se clasifica con las reglas del catálogo (mismo nodo del grafo).

## Qué dejé fuera

- Servidor HTTP o cola: el contrato es un proceso por evento.
- Checkpointer de LangGraph: no sobrevive entre procesos; el estado cruzado va a SQLite.
- Reservar visitas a posteriori (N5).
- WhatsApp de respaldo si el lead rechazó ese canal: se crea una tarea `llamar_a_mano` para no perderlo.

## Cómo lo comprobé

`scripts/verify_lote.py` recorre las 16 decisiones del lote, las operaciones, las fechas de reintento (Nuria, Tomás, Rosa, Javier, Sonia, Carla), el vencimiento de la visita de Laura, los dos recordatorios de Marcos y que evt_14 los cancela, y que la reentrega y la otra organización no emiten órdenes. evt_02 se compara con `ejemplo-resuelto/`. Los casos sin evento de ejemplo (603, callback fuera de ventana, `descartado`, `5xx`, segunda cortada) están en las reglas, no solo en el lote.
