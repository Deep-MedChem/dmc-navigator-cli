from __future__ import annotations

import time
import webbrowser
from collections.abc import Callable

import httpx

from . import __version__


class LoginError(RuntimeError):
    pass


def browser_login(
    web_url: str,
    *,
    open_browser: bool = True,
    timeout: float = 600,
    transport=None,
    sleep: Callable[[float], None] = time.sleep,
    on_started: Callable[[str, str], None] | None = None,
) -> tuple[str, str, str]:
    """Complete the one-time CHEESE browser approval flow.

    Returns ``(api_key, user_code, verification_url)``. The API key is returned
    only once by the server and must be persisted immediately by the caller.
    """
    headers = {
        "x-dmc-client": "navigator-cli",
        "user-agent": f"dmc-navigator/{__version__}",
    }
    try:
        with httpx.Client(
            base_url=web_url.rstrip("/"), headers=headers, timeout=30, transport=transport
        ) as client:
            started = client.post(
                "/api/navigator/login/start", json={"client_version": __version__}
            )
            started.raise_for_status()
            payload = started.json()
            device_code = payload["device_code"]
            user_code = payload["user_code"]
            verification_url = payload["verification_uri_complete"]
            interval = max(1.0, float(payload.get("interval", 2)))

            if on_started:
                on_started(user_code, verification_url)
            if open_browser:
                webbrowser.open(verification_url)

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                response = client.post(
                    "/api/navigator/login/poll", json={"device_code": device_code}
                )
                if response.status_code == 200:
                    result = response.json()
                    return result["api_key"], user_code, verification_url
                if response.status_code not in {202, 404, 410}:
                    response.raise_for_status()
                if response.status_code in {404, 410}:
                    detail = response.json().get("error", "login session is invalid or expired")
                    raise LoginError(detail)
                sleep(interval)
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise LoginError(f"CHEESE login failed: {error}") from error
    raise LoginError("CHEESE login timed out; run 'navigator auth login' to try again")
