import httpx

from dmc_navigator.auth import browser_login


def test_browser_login_polls_until_key_is_approved(monkeypatch) -> None:
    polls = 0
    opened = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal polls
        assert request.headers["x-dmc-client"] == "navigator-cli"
        if request.url.path.endswith("/start"):
            return httpx.Response(
                200,
                json={
                    "device_code": "device-secret",
                    "user_code": "CHEE-SE",
                    "verification_uri_complete": "https://cheese.test/navigator/login?code=CHEE-SE",
                    "interval": 1,
                },
            )
        polls += 1
        if polls == 1:
            return httpx.Response(202, json={"status": "pending"})
        return httpx.Response(200, json={"api_key": "shared-cheese-key"})

    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    token, code, url = browser_login(
        "https://cheese.test", transport=httpx.MockTransport(handler), sleep=lambda _: None
    )

    assert token == "shared-cheese-key"
    assert code == "CHEE-SE"
    assert opened == [url]
    assert polls == 2
