from typer.main import get_command
from typer.testing import CliRunner

from dmc_navigator.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.2.0"


def test_search_requires_one_input(monkeypatch) -> None:
    monkeypatch.setenv("DMC_NAVIGATOR_TOKEN", "test")
    result = runner.invoke(app, ["search"])
    assert result.exit_code == 2
    assert "Provide exactly one" in result.output


def test_token_is_not_a_command_argument() -> None:
    root = get_command(app)
    login = root.commands["auth"].commands["login"]
    option_names = {name for param in login.params for name in param.opts}
    assert "--token-stdin" in option_names
    assert "--token" not in option_names


def test_login_uses_browser_flow_and_saves_key(monkeypatch) -> None:
    saved = []

    def fake_login(_web_url, **kwargs):
        kwargs["on_started"]("CHEE-SE12", "https://cheese.test/navigator/login")
        return "shared-key", "CHEE-SE12", "https://cheese.test/navigator/login"

    monkeypatch.setattr("dmc_navigator.cli.browser_login", fake_login)
    monkeypatch.setattr("dmc_navigator.cli.save_token", saved.append)
    result = runner.invoke(app, ["auth", "login", "--no-browser"])

    assert result.exit_code == 0
    assert "CHEE-SE12" in result.stdout
    assert saved == ["shared-key"]
