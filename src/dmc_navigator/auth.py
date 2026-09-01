"""Navigator browser-login wrapper over :mod:`deepmedchem.auth`."""

from __future__ import annotations

from collections.abc import Callable

from deepmedchem.auth import LoginError
from deepmedchem.auth import browser_login as _browser_login

from . import __version__


def browser_login(
    web_url: str,
    *,
    open_browser: bool = True,
    timeout: float = 600,
    transport=None,
    sleep: Callable[[float], None] | None = None,
    on_started: Callable[[str, str], None] | None = None,
) -> tuple[str, str, str]:
    kwargs = {
        "application": "navigator-cli",
        "application_version": __version__,
        "open_browser": open_browser,
        "timeout": timeout,
        "transport": transport,
        "on_started": on_started,
    }
    if sleep is not None:
        kwargs["sleep"] = sleep
    return _browser_login(web_url, **kwargs)


__all__ = ["LoginError", "browser_login"]
