import httpx

from dmc_navigator.client import NavigatorClient


def test_search_is_thin_post_wrapper() -> None:
    captured = {}

    def handler(request: httpx.Request):
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = request.read()
        captured["token"] = request.headers["x-api-key"]
        captured["client"] = request.headers["x-dmc-client"]
        return httpx.Response(200, json={"results": []})

    client = NavigatorClient(
        "https://example.test", "scoped-token", transport=httpx.MockTransport(handler)
    )
    try:
        result = client.search(
            "CCO",
            database="enamine-real-v5a",
            scorer="shape",
            quality="balanced",
            limit=100,
            include_synthons=False,
        )
    finally:
        client.close()

    assert result == {"results": []}
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v2/search"
    assert captured["token"] == "scoped-token"
    assert captured["client"] == "navigator-cli"
    assert b'"query_smiles":"CCO"' in captured["body"]
