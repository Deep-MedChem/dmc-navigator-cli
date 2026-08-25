from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import keyring
from platformdirs import user_config_path

SERVICE = "dmc-navigator"
ACCOUNT = "platform-token"
DEFAULT_API_URL = "https://cheese-new-api.deepmedchem.com"


@dataclass(frozen=True)
class Config:
    api_url: str = DEFAULT_API_URL


def config_path() -> Path:
    return user_config_path("dmc-navigator", "Deep MedChem") / "config.json"


def load_config() -> Config:
    path = config_path()
    payload = json.loads(path.read_text()) if path.is_file() else {}
    api_url = os.environ.get("DMC_NAVIGATOR_API_URL", payload.get("api_url", DEFAULT_API_URL))
    return Config(api_url=api_url)


def save_api_url(value: str) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"api_url": value.rstrip("/")}, indent=2) + "\n")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def get_token() -> str | None:
    return os.environ.get("DMC_NAVIGATOR_TOKEN") or keyring.get_password(SERVICE, ACCOUNT)


def save_token(token: str) -> None:
    keyring.set_password(SERVICE, ACCOUNT, token)


def delete_token() -> None:
    try:
        keyring.delete_password(SERVICE, ACCOUNT)
    except keyring.errors.PasswordDeleteError:
        pass
