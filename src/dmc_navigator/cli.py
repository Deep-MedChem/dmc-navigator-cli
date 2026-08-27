from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .auth import LoginError, browser_login
from .client import NavigatorClient, NavigatorError, read_smiles
from .config import delete_token, get_token, load_config, save_api_url, save_token

app = typer.Typer(
    no_args_is_help=True,
    invoke_without_command=True,
    help="DMC Navigator remote client",
)
auth_app = typer.Typer(no_args_is_help=True)
config_app = typer.Typer(no_args_is_help=True)
app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")


def emit(payload, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
    elif isinstance(payload, str):
        typer.echo(payload)
    else:
        typer.echo(json.dumps(payload, indent=2))


def client() -> NavigatorClient:
    token = get_token()
    if not token:
        raise typer.BadParameter(
            "Not authenticated. Run 'navigator auth login' or set "
            "DMC_NAVIGATOR_TOKEN."
        )
    config = load_config()
    return NavigatorClient(config.api_url, token)


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
    api = client()
    try:
        emit(api.catalog(), json_output)
    except NavigatorError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    finally:
        api.close()


def _parse_property_args(values: list[str]) -> dict[str, dict[str, float]]:
    """Parse repeatable DESCRIPTOR:MIN:MAX search windows."""

    parsed: dict[str, dict[str, float]] = {}
    for raw in values:
        parts = raw.split(":")
        if len(parts) != 3 or not parts[0].strip():
            raise typer.BadParameter(
                f"Invalid --property {raw!r}; expected DESCRIPTOR:MIN:MAX."
            )
        descriptor, lower, upper = (part.strip() for part in parts)
        if not lower and not upper:
            raise typer.BadParameter(f"Invalid --property {raw!r}; provide a bound.")
        try:
            incoming = {
                **({"min": float(lower)} if lower else {}),
                **({"max": float(upper)} if upper else {}),
            }
        except ValueError as error:
            raise typer.BadParameter(f"Invalid numeric bound in --property {raw!r}.") from error
        current = parsed.setdefault(descriptor, {})
        if "min" in incoming:
            current["min"] = max(current.get("min", float("-inf")), incoming["min"])
        if "max" in incoming:
            current["max"] = min(current.get("max", float("inf")), incoming["max"])
        if current.get("min", float("-inf")) > current.get("max", float("inf")):
            raise typer.BadParameter(f"Contradictory --property bounds for {descriptor!r}.")
    return parsed


def _parse_admet_acquisition(values: list[str]) -> list[dict[str, object]]:
    """Parse repeatable ENDPOINT:DIRECTION:KEEP_FRACTION acquisition requests."""

    parsed: list[dict[str, object]] = []
    for raw in values:
        try:
            endpoint, direction, fraction_text = (part.strip() for part in raw.split(":"))
            fraction = float(fraction_text)
        except ValueError as error:
            raise typer.BadParameter(
                f"Invalid --admet-acquisition {raw!r}; expected "
                "ENDPOINT:minimize|maximize:KEEP_FRACTION."
            ) from error
        if not endpoint or direction not in {"minimize", "maximize"} or not 0 < fraction <= 1:
            raise typer.BadParameter(
                f"Invalid --admet-acquisition {raw!r}; KEEP_FRACTION must be in (0, 1]."
            )
        parsed.append(
            {"endpoint": endpoint, "direction": direction, "keep_fraction": fraction}
        )
    if len(parsed) > 4:
        raise typer.BadParameter("At most four --admet-acquisition objectives are supported.")
    return parsed


@app.command()
def search(
    smiles: Annotated[str | None, typer.Option(help="One query SMILES.")] = None,
    input_file: Annotated[Path | None, typer.Option("--input", exists=True, dir_okay=False)] = None,
    database: Annotated[str, typer.Option()] = "enamine-real-v5a",
    scorer: Annotated[str, typer.Option()] = "shape",
    limit: Annotated[int, typer.Option(min=1, max=200)] = 100,
    shortlist_multiplier: Annotated[
        int,
        typer.Option(
            min=1,
            max=200,
            help="Morgan proposals per requested neighbor (default 10, the Fast setting).",
        ),
    ] = 10,
    include_synthons: Annotated[bool, typer.Option()] = False,
    property_preset: Annotated[
        str | None,
        typer.Option(help="Property preset: lipinski-ro5 or navigator-druglike-v1."),
    ] = None,
    property: Annotated[
        list[str] | None,
        typer.Option("--property", help="DESCRIPTOR:MIN:MAX; repeat for multiple windows."),
    ] = None,
    exact_property_postfilter: Annotated[
        bool,
        typer.Option(
            "--exact-property-postfilter/--no-exact-property-postfilter",
            help="Verify requested descriptor bounds on assembled products.",
        ),
    ] = True,
    admet_acquisition: Annotated[
        list[str] | None,
        typer.Option(
            "--admet-acquisition",
            help=(
                "Approximate CP16 acquisition ENDPOINT:DIRECTION:KEEP_FRACTION; repeat up "
                "to four times. This is not an authoritative safety filter."
            ),
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    if bool(smiles) == bool(input_file):
        raise typer.BadParameter("Provide exactly one of --smiles or --input.")
    if scorer not in {"shape", "esp", "morgan"}:
        raise typer.BadParameter("--scorer must be shape, esp, or morgan")
    if property_preset not in {None, "lipinski-ro5", "navigator-druglike-v1"}:
        raise typer.BadParameter(
            "--property-preset must be lipinski-ro5 or navigator-druglike-v1"
        )
    property_constraints = _parse_property_args(property or [])
    admet_objectives = _parse_admet_acquisition(admet_acquisition or [])
    queries = [smiles] if smiles else list(read_smiles(input_file))
    api = client()
    try:
        results = [
            api.search(
                value,
                database=database,
                scorer=scorer,
                shortlist_multiplier=shortlist_multiplier,
                limit=limit,
                include_synthons=include_synthons,
                property_preset=property_preset,
                property_constraints=property_constraints,
                exact_property_postfilter=exact_property_postfilter,
                admet_acquisition=admet_objectives,
            )
            for value in queries
        ]
        emit(results[0] if len(results) == 1 else {"queries": results}, json_output)
    except NavigatorError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    finally:
        api.close()
