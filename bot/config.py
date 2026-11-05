"""설정/환경변수 로딩."""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
POSTS_DIR = ROOT / "posts"
TEMPLATES_DIR = ROOT / "templates"


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def env(name: str, required: bool = True, default: str | None = None) -> str | None:
    val = os.environ.get(name, default)
    if required and not val:
        raise SystemExit(f"[설정 오류] 환경변수/Secret '{name}' 이(가) 비어 있습니다. README 의 Secrets 설정을 확인하세요.")
    return val


def read_json(path: Path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
