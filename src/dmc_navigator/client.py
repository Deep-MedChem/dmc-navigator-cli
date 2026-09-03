"""Navigator compatibility facade over the public :mod:`deepmedchem` SDK."""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from pathlib import Path

from deepmedchem import AsyncClient as _PlatformAsyncClient
from deepmedchem import Client as _PlatformClient
from deepmedchem import DeepMedChemError

from . import __version__

NavigatorError = DeepMedChemError


class DMCClient(_PlatformClient):
    """Platform client attributed to the Navigator application."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("application", "navigator-cli")
        kwargs.setdefault("application_version", __version__)
        super().__init__(*args, **kwargs)


class AsyncDMCClient(_PlatformAsyncClient):
    """Asynchronous platform client attributed to the Navigator application."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("application", "navigator-cli")
        kwargs.setdefault("application_version", __version__)
        super().__init__(*args, **kwargs)


class NavigatorClient(DMCClient):
    """Deprecated pre-0.3 compatibility facade."""

    def __init__(self, api_url: str, token: str, *, transport=None):
        warnings.warn(
            "NavigatorClient is deprecated; use deepmedchem.Client.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(api_key=token, api_url=api_url, transport=transport)

    def search(self, smiles: str, *, scorer: str = "morgan", **kwargs):
        unsupported = {
            "property_preset",
            "property_constraints",
            "exact_property_postfilter",
            "admet_acquisition",
        }
        if any(kwargs.pop(name, None) not in (None, {}, [], True) for name in unsupported):
            raise NavigatorError(
                "Legacy property controls moved to the Selection builder.",
                code="deprecated_request",
            )
        if scorer == "morgan":
            return super().search(smiles, **kwargs).raw
        return super().search_cheese(smiles, scorer=scorer, **kwargs).raw


def read_smiles(path: Path) -> Iterator[str]:
    with path.open() as handle:
        for line in handle:
            value = line.strip().split()[0] if line.strip() else ""
            if value and not value.startswith("#"):
                yield value
