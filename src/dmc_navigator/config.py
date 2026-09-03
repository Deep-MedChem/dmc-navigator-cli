from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from deepmedchem.config import (
    DEFAULT_API_URL,
    DEFAULT_WEB_URL,
    delete_api_key,
    get_stored_api_key,
    save_api_key,
)
from platformdirs import user_config_path


@dataclass(frozen=True)
class Config:
    api_url: str = DEFAULT_API_URL
    web_url: str = DEFAULT_WEB_URL


def config_path() -> Path:
    return user_config_path("dmc-navigator", "Deep MedChem") / "config.json"


def load_config() -> Config:
    path = config_path()
    payload = json.loads(path.read_text()) if path.is_file() else {}
    api_url = os.environ.get("DMC_NAVIGATOR_API_URL", payload.get("api_url", DEFAULT_API_URL))
    web_url = os.environ.get("DMC_NAVIGATOR_WEB_URL", payload.get("web_url", DEFAULT_WEB_URL))
    return Config(api_url=api_url.rstrip("/"), web_url=web_url.rstrip("/"))


def save_api_url(value: str) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    existing = load_config()
    temporary.write_text(
        json.dumps({"api_url": value.rstrip("/"), "web_url": existing.web_url}, indent=2)
        + "\n"
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def get_token() -> str | None:
    return os.environ.get("DMC_NAVIGATOR_TOKEN") or get_stored_api_key()


def save_token(token: str) -> None:
    save_api_key(token)


def delete_token() -> None:
    delete_api_key(include_legacy=True)
