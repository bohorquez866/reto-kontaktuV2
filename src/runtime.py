from __future__ import annotations

from pathlib import Path

from src.config import SALIDA_DIR
from src.store import Store

_store: Store | None = None
_salida_dir: Path | None = None


def set_store(store: Store) -> None:
    global _store
    _store = store


def get_store() -> Store:
    if _store is None:
        raise RuntimeError("el almacén SQLite no está inicializado")
    return _store


def set_salida_dir(path: Path | None) -> None:
    global _salida_dir
    _salida_dir = path


def get_salida_dir() -> Path:
    return _salida_dir if _salida_dir is not None else SALIDA_DIR
