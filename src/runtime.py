from __future__ import annotations

from src.store import Store

_store: Store | None = None


def set_store(store: Store) -> None:
    global _store
    _store = store


def get_store() -> Store:
    if _store is None:
        raise RuntimeError("el almacén SQLite no está inicializado")
    return _store
