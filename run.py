#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

warnings.filterwarnings("ignore", module="urllib3")
warnings.filterwarnings("ignore", category=DeprecationWarning)

from src.config import DB_PATH, SALIDA_DIR, load_campana
from src.graph import GRAPH
from src.runtime import set_salida_dir, set_store
from src.store import Store

load_dotenv()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("uso: python run.py eventos/01-call-ended-nuria.json", file=sys.stderr)
        return 1

    path = Path(args[0])
    try:
        event = json.loads(path.read_text(encoding="utf-8"))
        SALIDA_DIR.mkdir(parents=True, exist_ok=True)
        set_salida_dir(SALIDA_DIR)
        store = Store(DB_PATH)
        set_store(store)
        GRAPH.invoke(
            {
                "event": event,
                "campana": load_campana(),
                "planned_orders": [],
                "emitted_order_ids": [],
                "pending_reminders": [],
            }
        )
        store.close()
        return 0
    except Exception as exc:
        print(f"error procesando {path}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
