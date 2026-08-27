from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx

from . import __version__


class NavigatorError(RuntimeError):
    pass


class NavigatorClient:
    def __init__(self, api_url: str, token: str, *, transport=None):
        self._client = httpx.Client(
            base_url=api_url.rstrip("/"),
            headers={
                "x-api-key": token,
                "x-dmc-client": "navigator-cli",
                "user-agent": f"dmc-navigator/{__version__}",
            },
            timeout=45.0,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            detail = error.response.json().get("detail", {})
            message = detail.get("message") if isinstance(detail, dict) else str(detail)
            raise NavigatorError(message or f"API returned {error.response.status_code}") from error
        except (httpx.HTTPError, ValueError) as error:
            raise NavigatorError(f"Platform request failed: {error}") from error

    def catalog(self) -> dict:
        return self._request("GET", "/api/v2/catalog")

    def search(
        self,
        smiles: str,
        *,
        database: str,
        scorer: str,
        shortlist_multiplier: int,
        limit: int,
        include_synthons: bool,
    ) -> dict:
        return self._request(
            "POST",
            "/api/v2/search",
            json={
                "query_smiles": smiles,
                "database_id": database,
                "scorer": scorer,
                "shortlist_multiplier": shortlist_multiplier,
                "limit": limit,
                "include_synthons": include_synthons,
            },
        )


def read_smiles(path: Path) -> Iterator[str]:
    with path.open() as handle:
        for line in handle:
            value = line.strip().split()[0] if line.strip() else ""
            if value and not value.startswith("#"):
                yield value
