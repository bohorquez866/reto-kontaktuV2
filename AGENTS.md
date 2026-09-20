# AGENTS.md

Instructions for coding agents working on this repo. The challenge is a post-call orchestrator: one event file in, a decision plus zero or more CRM orders out.

## Hard constraints

- Stack is **Python + LangGraph**. Do not replace the graph with a flat script.
- Do **not** modify `eventos/`, `config/`, or `esquemas/`.
- Do **not** add a server, Postgres, or Redis. Cross-process state is the local SQLite file only.
- Git history must stay intact. The first commit is the unzipped zip, untouched. Do not rebase or force-push that history.
- Prompts used by the code live in `prompts/` and must stay versioned.

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py eventos/01-call-ended-nuria.json
```

Each `run.py` invocation is a new process. Persist anything the next event needs (attempts, reminders, DNC, already-closed calls) in `salida/orquestador.db`.

```bash
pytest
bash scripts/run_lote.sh && python scripts/verify_lote.py
```

Tests must not write to the real `salida/` directory. `tests/conftest.py` points the store and jsonl appends at a temp path. Unset `OPENAI_API_KEY` in tests so conversation classification stays deterministic.

## Architecture

The graph is in `src/graph.py`. Nodes return partial state updates. `gate` and `classify_signaling` route with `Command` — do not also add static edges from those nodes (both paths would run).

```
START → gate
  → write_skip | write_redelivery | cancel_reminders | classify_signaling
classify_signaling → plan_orders | classify_conversation → plan_orders
plan_orders | cancel_reminders → emit_and_persist → END
```

- **Signaling first.** SIP `408`/`480`/`486`/`603`/`5xx`, AMD voicemail/IVR, and a present `appointment` never go to the LLM. See `ejemplo-resuelto/` (Tomás / 486).
- **`uncertain` AMD is a person.** Fall through to the transcript.
- **Conversation.** `classify_conversation` calls `gpt-4o-mini` when `OPENAI_API_KEY` is set. Without a key, the same node uses `classify_by_rules`. `no_contactar` always wins over `descartado`.
- **Orders.** `plan_orders` is the only place that maps etiqueta → CRM operations. Dates use `Europe/Madrid` and `config/campana.yaml`.
- **Emit.** SQLite unique keys are written _before_ appending jsonl so a redelivery cannot duplicate orders.

## Rules that are easy to break

- Every first-seen `call.ended` emits `cerrar_llamada`. Redeliveries and other `organization_id` do not.
- An attempt is every new `call.ended` for `lead.contact_id`. Max is `reintentos.max_intentos` (3). Redeliveries do not count.
- Nuria in the sample batch: two `sin_respuesta` then a `buzon` on the third attempt → WhatsApp backup, not another call.
- `486` is `ocupado`, not `rechazada`. LiveKit puts 486 in `USER_REJECTED`.
- `603` is `rechazada`: backup channel, no voice retry.
- Verbal visit without `appointment` is `visita_sin_confirmar`. Do not book the visit (N5).
- Second `cortada` or `visita_sin_confirmar` for the same lead also creates `revisar_llamada` (N4). So does etiqueta `otro`.
- A lead who rejected WhatsApp gets no documentation/reply templates on that channel (N1). Backup then becomes `llamar_a_mano`.
- `message.received` is `no_aplica` and cancels pending reminders for that `contact_id` using the `reminder_id` we generated earlier.
- Window: Mon–Fri 10:00–20:00 inclusive, Sat 10:00–14:00, Sun none. Saturday is callable but **not** a business day for task/reminder offsets.

## When you change code

1. Prefer a new node or a change inside one node over growing `run.py`.
2. Keep files under ~400 lines.
3. Add or update a test next to the behavior you changed (`tests/test_*.py`).
4. Run `pytest` before you stop. If the change affects labels, dates, or orders, also run the sample lote.
5. Do not commit unless the user asks. Never commit `.env` or `salida/`.
