from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import ROOT, load_campana
from src.graph import GRAPH
from src.runtime import set_salida_dir, set_store
from src.store import Store


@pytest.fixture(autouse=True)
def no_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def campana() -> dict:
    return load_campana()


@pytest.fixture
def isolated_salida(tmp_path: Path):
    set_salida_dir(tmp_path)
    store = Store(tmp_path / "orquestador.db")
    set_store(store)
    try:
        yield tmp_path, store
    finally:
        store.close()
        set_salida_dir(None)


def load_event(name: str) -> dict:
    return json.loads((ROOT / "eventos" / name).read_text(encoding="utf-8"))


def invoke_event(event: dict, campana: dict) -> dict:
    return GRAPH.invoke(
        {
            "event": event,
            "campana": campana,
            "planned_orders": [],
            "emitted_order_ids": [],
            "pending_reminders": [],
        }
    )


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
