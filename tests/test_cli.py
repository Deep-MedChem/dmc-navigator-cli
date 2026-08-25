from typer.testing import CliRunner

from dmc_navigator.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_search_requires_one_input(monkeypatch) -> None:
    monkeypatch.setenv("DMC_NAVIGATOR_TOKEN", "test")
    result = runner.invoke(app, ["search"])
    assert result.exit_code == 2
    assert "Provide exactly one" in result.output


def test_token_is_not_a_command_argument() -> None:
    result = runner.invoke(app, ["auth", "login", "--help"])
    assert "--token-stdin" in result.output
    assert "--token " not in result.output
