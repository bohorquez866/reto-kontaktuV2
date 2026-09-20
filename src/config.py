from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SALIDA_DIR = ROOT / "salida"
CAMPANA_PATH = ROOT / "config" / "campana.yaml"
PROMPT_PATH = ROOT / "prompts" / "classify_conversation.md"
DB_PATH = SALIDA_DIR / "orquestador.db"


def load_campana() -> dict:
    with CAMPANA_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def timezone_name(campana: dict) -> str:
    return campana["campana"]["zona_horaria"]
