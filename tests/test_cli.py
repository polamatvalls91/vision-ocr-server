import sys

import pytest

from vision_ocr_server import cli, server


@pytest.fixture
def served(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, host, port: calls.append((host, port)))
    monkeypatch.setattr(cli.sys, "platform", "darwin")
    monkeypatch.delenv("VISION_OCR_TOKEN", raising=False)
    return calls


def test_localhost_by_default(served):
    cli.main([])
    assert served == [("127.0.0.1", 11500)]


def test_lan_is_open_with_a_warning(served, capsys):
    cli.main(["--host", "0.0.0.0"])
    assert served == [("0.0.0.0", 11500)]
    assert "no auth" in capsys.readouterr().err


def test_no_warning_with_a_token_or_on_localhost(served, capsys, monkeypatch):
    cli.main([])
    monkeypatch.setenv("VISION_OCR_TOKEN", "s3cret")
    cli.main(["--host", "0.0.0.0"])
    assert capsys.readouterr().err == ""


def test_options_reach_the_server(served, monkeypatch):
    monkeypatch.setattr(server, "settings", server.Settings())
    monkeypatch.setattr(cli, "settings", server.settings)
    cli.main(["--languages", "es-ES, en-US", "--dpi", "200", "--level", "fast", "--max-pages", "5"])
    assert (server.settings.languages, server.settings.dpi) == (["es-ES", "en-US"], 200)
    assert (server.settings.level, server.settings.max_pages) == ("fast", 5)


def test_not_macos(served, monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "linux")
    with pytest.raises(SystemExit):
        cli.main([])
    assert sys.platform  # the real one is untouched
