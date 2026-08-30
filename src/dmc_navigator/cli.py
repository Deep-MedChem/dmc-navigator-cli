from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from pydantic import BaseModel

from . import __version__
from .auth import LoginError, browser_login
from .client import DMCClient, NavigatorError, read_smiles
from .config import delete_token, get_token, load_config, save_api_url, save_token
from .selection import Run, Selection

app = typer.Typer(no_args_is_help=True, invoke_without_command=True, help="DMC developer CLI")
auth_app = typer.Typer(no_args_is_help=True)
config_app = typer.Typer(no_args_is_help=True)
selection_app = typer.Typer(no_args_is_help=True)
run_app = typer.Typer(no_args_is_help=True)
app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")
app.add_typer(selection_app, name="selection")
app.add_typer(run_app, name="run")


def emit(payload, json_output: bool = False) -> None:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json", exclude_none=True)
    elif hasattr(payload, "to_dict"):
        payload = payload.to_dict()
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
    elif isinstance(payload, str):
        typer.echo(payload)
    else:
        typer.echo(json.dumps(payload, indent=2))


def client() -> DMCClient:
    token = get_token()
    if not token:
        raise typer.BadParameter(
            "Not authenticated. Run 'navigator auth login' or set DMC_NAVIGATOR_TOKEN."
        )
    config = load_config()
    return DMCClient(api_key=token, api_url=config.api_url)


def _load_document(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise typer.BadParameter(f"Could not read {path}: {error}") from error
    if not isinstance(payload, dict):
        raise typer.BadParameter("Document must contain a JSON/YAML object.")
    return payload


def _idempotency(payload: dict[str, Any], prefix: str = "navigator") -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(canonical.encode()).hexdigest()[:32]}"


@app.callback()
def root(
    version: Annotated[bool, typer.Option("--version", help="Show version and exit.")] = False,
):
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@auth_app.command("login")
def auth_login(
    token_stdin: Annotated[
        bool, typer.Option("--token-stdin", help="Read an API key from stdin (automation).")
    ] = False,
    no_browser: Annotated[
        bool, typer.Option("--no-browser", help="Print the approval URL without opening it.")
    ] = False,
    timeout: Annotated[
        int, typer.Option(min=30, max=1800, help="Browser login timeout in seconds.")
    ] = 600,
):
    if token_stdin:
        token = sys.stdin.read().strip()
        if not token:
            raise typer.BadParameter("stdin did not contain an API key")
    else:
        config = load_config()
        typer.echo("Opening CHEESE to approve Navigator login…")

        def show_approval(user_code: str, verification_url: str) -> None:
            typer.echo(f"Approval code: {user_code}")
            typer.echo(f"Approval URL: {verification_url}")

        try:
            token, _, _ = browser_login(
                config.web_url,
                open_browser=not no_browser,
                timeout=timeout,
                on_started=show_approval,
            )
        except LoginError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(1) from error
    save_token(token)
    typer.echo("Authenticated. CHEESE API key saved in the OS credential store.")


@auth_app.command("status")
def auth_status(json_output: Annotated[bool, typer.Option("--json")] = False):
    config = load_config()
    emit(
        {"authenticated": bool(get_token()), "api_url": config.api_url, "web_url": config.web_url},
        json_output,
    )


@auth_app.command("logout")
def auth_logout():
    delete_token()
    typer.echo("Local credentials removed.")


@config_app.command("set-api-url")
def set_api_url(url: str):
    if not url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        raise typer.BadParameter("API URL must use HTTPS (HTTP is allowed only for localhost).")
    save_api_url(url)
    typer.echo(f"API URL set to {url.rstrip('/')}")


@app.command()
def doctor(json_output: Annotated[bool, typer.Option("--json")] = False):
    config = load_config()
    report = {
        "version": __version__,
        "api_url": config.api_url,
        "authenticated": bool(get_token()),
        "scientific_dependencies_installed": False,
    }
    if report["authenticated"]:
        api = client()
        try:
            report["catalog"] = api.catalog()
            report["platform_reachable"] = True
        except NavigatorError as error:
            report["platform_reachable"] = False
            report["error"] = str(error)
        finally:
            api.close()
    emit(report, json_output)


@app.command()
def catalog(json_output: Annotated[bool, typer.Option("--json")] = False):
    with client() as api:
        try:
            emit(api.catalog(), json_output)
        except NavigatorError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(1) from error


@app.command()
def search(
    smiles: Annotated[str | None, typer.Option(help="One query SMILES.")] = None,
    input_file: Annotated[Path | None, typer.Option("--input", exists=True, dir_okay=False)] = None,
    database: Annotated[str, typer.Option()] = "enamine-real-v5a",
    limit: Annotated[int, typer.Option(min=1, max=200)] = 20,
    shortlist_multiplier: Annotated[int, typer.Option(min=1, max=200)] = 10,
    include_synthons: Annotated[bool, typer.Option()] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    if bool(smiles) == bool(input_file):
        raise typer.BadParameter("Provide exactly one of --smiles or --input.")
    with client() as api:
        try:
            if smiles:
                emit(
                    api.search(
                        smiles,
                        database=database,
                        limit=limit,
                        shortlist_multiplier=shortlist_multiplier,
                        include_synthons=include_synthons,
                    ),
                    json_output,
                )
                return
            queries = list(read_smiles(input_file))
            template = (
                Selection.from_database(database)
                .ranked()
                .maximize_similarity("rdkit.ecfp4_tanimoto", reference="query")
                .limit(limit)
            )
            if include_synthons:
                template = template.include("synthons")
            specification = Run.selection_batch(
                template=template,
                items={
                    f"query-{index:04d}": {"query": value}
                    for index, value in enumerate(queries)
                },
                metadata={"source": str(input_file)},
            )
            run = api.runs.create(
                specification,
                idempotency_key=_idempotency(specification.to_dict(), "navigator-search"),
            )
            emit(run, json_output)
        except (NavigatorError, ValueError) as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(1) from error


@app.command("search-cheese")
def search_cheese(
    smiles: Annotated[str, typer.Option(help="One query SMILES.")],
    scorer: Annotated[str, typer.Option(help="shape or esp")] = "shape",
    database: Annotated[str, typer.Option()] = "enamine-real-v5a",
    limit: Annotated[int, typer.Option(min=1, max=200)] = 20,
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    if scorer not in {"shape", "esp"}:
        raise typer.BadParameter("--scorer must be shape or esp")
    with client() as api:
        emit(
            api.search_cheese(
                smiles, database=database, scorer=scorer, limit=limit
            ),
            json_output,
        )


@app.command("search-substructure")
def search_substructure(
    query: Annotated[str, typer.Option()],
    query_format: Annotated[str, typer.Option()] = "smarts",
    database: Annotated[str, typer.Option()] = "enamine-real-v5a",
    limit: Annotated[int, typer.Option(min=1, max=200)] = 100,
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    with client() as api:
        emit(
            api.search_substructure(
                query, query_format=query_format, database=database, limit=limit
            ),
            json_output,
        )


@app.command()
def sample(
    database: Annotated[str, typer.Option()] = "enamine-real-v5a",
    count: Annotated[int, typer.Option(min=1, max=1000)] = 100,
    seed: Annotated[int | None, typer.Option()] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    with client() as api:
        emit(api.sample(database=database, count=count, seed=seed), json_output)


@selection_app.command("validate")
def selection_validate(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    selection = Selection.model_validate(_load_document(path))
    with client() as api:
        emit(api.selections.validate(selection), json_output)


@selection_app.command("estimate")
def selection_estimate(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    selection = Selection.model_validate(_load_document(path))
    with client() as api:
        emit(api.selections.estimate(selection), json_output)


@selection_app.command("execute")
def selection_execute(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    idempotency_key: Annotated[str | None, typer.Option()] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    selection = Selection.model_validate(_load_document(path))
    with client() as api:
        estimate = api.selections.estimate(selection)
        if estimate.execution_tier == "synchronous":
            emit(api.selections.create(selection), json_output)
        else:
            specification = Run.selection(selection)
            emit(
                api.runs.create(
                    specification,
                    idempotency_key=idempotency_key
                    or _idempotency(specification.to_dict(), "navigator-selection"),
                ),
                json_output,
            )


@selection_app.command("export")
def selection_export(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
):
    selection = Selection.model_validate(_load_document(path))
    if output_format == "json":
        typer.echo(selection.to_json())
    elif output_format == "yaml":
        typer.echo(selection.to_yaml(), nl=False)
    else:
        raise typer.BadParameter("--format must be json or yaml")


@run_app.command("estimate")
def run_estimate(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    specification = Run.model_validate(_load_document(path))
    with client() as api:
        emit(api.runs.estimate(specification), json_output)


@run_app.command("create")
def run_create(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    idempotency_key: Annotated[str | None, typer.Option()] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    specification = Run.model_validate(_load_document(path))
    with client() as api:
        emit(
            api.runs.create(
                specification,
                idempotency_key=idempotency_key or _idempotency(specification.to_dict()),
            ),
            json_output,
        )


@run_app.command("status")
def run_status(run_id: str, json_output: Annotated[bool, typer.Option("--json")] = False):
    with client() as api:
        emit(api.runs.retrieve(run_id), json_output)


@run_app.command("watch")
def run_watch(run_id: str, after: Annotated[int, typer.Option(min=0)] = 0):
    with client() as api:
        for event in api.runs.watch(run_id, after=after):
            emit(event, json_output=True)


@run_app.command("results")
def run_results(
    run_id: str,
    order: Annotated[str, typer.Option()] = "completion",
):
    had_errors = False
    with client() as api:
        for item in api.runs.iter_results(run_id, order=order):
            emit(item, json_output=True)
            had_errors = had_errors or not item.ok
    if had_errors:
        raise typer.Exit(2)


@run_app.command("cancel")
def run_cancel(run_id: str, json_output: Annotated[bool, typer.Option("--json")] = False):
    with client() as api:
        emit(api.runs.cancel(run_id), json_output)
