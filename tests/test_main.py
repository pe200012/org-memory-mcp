"""Tests for the console entrypoint."""

from __future__ import annotations

import main


def test_main_delegates_to_stdio_server(monkeypatch) -> None:
    calls: list[bool] = []

    def fake_run_stdio_server() -> None:
        calls.append(True)

    monkeypatch.setattr(main, "run_stdio_server", fake_run_stdio_server)

    main.main()

    assert calls == [True]
