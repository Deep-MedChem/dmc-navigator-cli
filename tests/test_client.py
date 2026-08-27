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
            shortlist_multiplier=10,
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
    assert b'"shortlist_multiplier":10' in captured["body"]
    assert b'"quality"' not in captured["body"]


def test_search_sends_property_filters_when_requested() -> None:
    captured = {}

    def handler(request: httpx.Request):
        captured.update(request.json() if hasattr(request, "json") else {})
        captured.update(__import__("json").loads(request.read()))
        return httpx.Response(200, json={"results": []})

    client = NavigatorClient(
        "https://example.test", "token", transport=httpx.MockTransport(handler)
    )
    try:
        client.search(
            "CCO", database="enamine-real-v5a", scorer="morgan", shortlist_multiplier=10,
            limit=10, include_synthons=False, property_preset="lipinski-ro5",
            property_constraints={"MolWt": {"max": 450.0}},
            exact_property_postfilter=True,
            admet_acquisition=[
                {"endpoint": "herg", "direction": "minimize", "keep_fraction": 0.5}
            ],
        )
    finally:
        client.close()
    assert captured["property_preset"] == "lipinski-ro5"
    assert captured["property_constraints"] == {"MolWt": {"max": 450.0}}
    assert captured["exact_property_postfilter"] is True
    assert captured["admet_acquisition"] == [
        {"endpoint": "herg", "direction": "minimize", "keep_fraction": 0.5}
    ]
