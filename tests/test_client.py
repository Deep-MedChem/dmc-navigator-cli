import asyncio
import json

import httpx

from dmc_navigator import AsyncDMCClient, DMCClient, Run, Selection
from dmc_navigator.client import NavigatorClient, NavigatorError


def _run_resource(status="queued"):
    terminal = status in {"completed", "completed_with_errors", "failed", "cancelled"}
    return {
        "id": "run_123",
        "object": "run",
        "kind": "selection_batch",
        "status": status,
        "progress": {
            "total": 1,
            "pending": 0 if terminal else 1,
            "running": 0,
            "succeeded": 1 if status == "completed" else 0,
            "failed": 0,
            "cancelled": 0,
        },
        "last_event_sequence": 1,
        "links": {},
    }


def test_simple_methods_use_distinct_public_operations() -> None:
    captured = []

    def handler(request: httpx.Request):
        captured.append((request.method, request.url.path, json.loads(request.read() or b"{}")))
        return httpx.Response(200, json={"results": []})

    with DMCClient(
        api_key="scoped-token",
        api_url="https://example.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        client.search("CCO", database="enamine-real-v5a")
        client.search_cheese("CCO", database="enamine-real-v5a", scorer="shape")
        client.search_substructure(
            "C(=O)N", query_format="smarts", database="enamine-real-v5a"
        )
        client.sample(database="enamine-real-v5a", count=10, seed=42)

    assert [value[1] for value in captured] == [
        "/api/v2/search",
        "/api/v2/search_cheese",
        "/api/v2/search_substructure",
        "/api/v2/sample",
    ]
    assert "scorer" not in captured[0][2]
    assert captured[1][2]["scorer"] == "shape"
    assert captured[2][2]["query"] == {"format": "smarts", "value": "C(=O)N"}
    assert captured[3][2]["seed"] == 42


def test_selection_builder_is_copy_on_write_and_round_trips() -> None:
    base = Selection.from_database("enamine-real-v5a").ranked()
    aspirin = (
        base.reference("aspirin", smiles="CC(=O)Oc1ccccc1C(=O)O")
        .maximize_similarity("rdkit.ecfp4_tanimoto", reference="aspirin")
        .require_different_scaffold("rdkit.bemis_murcko", reference="aspirin")
        .require_pattern("alpha-amino-acid/v1", min_count=1)
        .where("rdkit.mol_wt", gt=250, units="Da")
        .limit(100)
        .shortlist_multiplier(0)
        .max_per_scaffold(5)
        .include("properties", "constraint_evidence", "execution_plan")
    )
    assert base.to_dict()["references"] == []
    payload = aspirin.to_dict()
    assert payload["constraints"]["properties"][0]["operator"] == "gt"
    assert payload["constraints"]["relationships"][0]["operator"] == "different"
    assert payload["execution"]["shortlist_multiplier"] == 0
    assert Selection.model_validate(json.loads(aspirin.to_json())).to_dict() == payload
    loaded_yaml = __import__("yaml").safe_load(aspirin.to_yaml())
    assert Selection.model_validate(loaded_yaml).to_dict() == payload


def test_run_builder_creates_shared_template_and_unique_bindings() -> None:
    template = (
        Selection.from_database("enamine-real-v5a")
        .ranked()
        .maximize_similarity("rdkit.ecfp4_tanimoto", reference="query")
        .limit(10)
    )
    run = Run.selection_batch(
        template=template,
        items={"lead-001": {"query": "CCO"}, "lead-002": {"query": "CCN"}},
    )
    payload = run.to_dict()
    assert payload["schema_version"] == "run/1"
    assert payload["selection_template"]["references"] == []
    assert [item["id"] for item in payload["items"]] == ["lead-001", "lead-002"]


def test_runs_namespace_requires_idempotency_and_follows_result_cursors() -> None:
    paths = []

    def handler(request: httpx.Request):
        paths.append(str(request.url))
        if request.url.path == "/api/v2/runs":
            assert request.headers["idempotency-key"] == "campaign-1"
            return httpx.Response(202, json=_run_resource())
        if request.url.params.get("cursor") == "next":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "b",
                            "input_index": 1,
                            "status": "failed",
                            "error": {"code": "invalid_smiles"},
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "a",
                        "input_index": 0,
                        "status": "succeeded",
                        "result": {"results": []},
                    }
                ],
                "next_cursor": "next",
            },
        )

    selection = Selection.from_database("db").sample().limit(10)
    with DMCClient(
        api_key="token",
        api_url="https://example.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        run = client.runs.create(Run.selection(selection), idempotency_key="campaign-1")
        results = list(client.runs.iter_results(run.id))
    assert [item.id for item in results] == ["a", "b"]
    assert results[0].ok is True
    assert results[1].ok is False
    assert any("cursor=next" in value for value in paths)


def test_async_client_has_matching_simple_search() -> None:
    async def scenario():
        async def handler(request: httpx.Request):
            assert request.url.path == "/api/v2/search"
            return httpx.Response(200, json={"results": [], "request_id": "req_1"})

        async with AsyncDMCClient(
            api_key="token",
            api_url="https://example.test",
            transport=httpx.MockTransport(handler),
        ) as client:
            result = await client.search("CCO", database="db")
            assert result.request_id == "req_1"

    asyncio.run(scenario())


def test_error_does_not_expose_api_key() -> None:
    def handler(_request: httpx.Request):
        return httpx.Response(
            401,
            json={
                "error": {
                    "code": "unauthorized",
                    "message": "A valid API key is required.",
                    "request_id": "req_1",
                }
            },
        )

    client = DMCClient(
        api_key="super-secret",
        api_url="https://example.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        try:
            client.catalog()
        except NavigatorError as error:
            assert error.code == "unauthorized"
            assert error.request_id == "req_1"
            assert "super-secret" not in str(error)
        else:
            raise AssertionError("expected NavigatorError")
    finally:
        client.close()


def test_navigator_client_compatibility_routes_scorers() -> None:
    paths = []

    def handler(request: httpx.Request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"results": []})

    client = NavigatorClient(
        "https://example.test", "token", transport=httpx.MockTransport(handler)
    )
    try:
        client.search(
            "CCO",
            database="db",
            scorer="shape",
            shortlist_multiplier=10,
            limit=20,
            include_synthons=False,
        )
    finally:
        client.close()
    assert paths == ["/api/v2/search_cheese"]
