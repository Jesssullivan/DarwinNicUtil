"""
Tests for TUI state helpers and keyboard-driven control flow.
"""

from collections.abc import Iterable

import pytest
from rich.console import Console
from rich.text import Text

from darwin_mgmt_nic import tui


def make_console() -> Console:
    return Console(force_terminal=True, width=100, height=30, record=True)


def key_reader(keys: Iterable[str]):
    iterator = iter(keys)
    return lambda: next(iterator)


class TestProgressAndSpinner:
    def test_progress_indicator_clamps_step_and_renders_labels(self):
        progress = tui.ProgressIndicator()

        progress.set_step(-10)
        assert progress.current == 0
        assert "Baseline" in str(progress.render())

        progress.set_step(999)
        assert progress.current == len(progress.STEPS) - 1
        rendered = str(progress.render())
        assert "Done" in rendered
        assert "Baseline" in rendered

    def test_spinner_render_tracks_active_and_ready_states(self):
        spinner = tui.SpinnerState()

        assert "Ready" in str(spinner.render())

        spinner.set("Scanning interfaces")
        first = str(spinner.render())
        second = str(spinner.render())

        assert "Scanning interfaces" in first
        assert "Scanning interfaces" in second
        assert first != second

        spinner.clear()
        assert "Ready" in str(spinner.render())


class TestLayout:
    def test_layout_updates_regions_and_resizes(self, monkeypatch):
        sizes = iter([(100, 30), (72, 22)])
        monkeypatch.setattr(tui, "get_terminal_size", lambda: next(sizes))

        layout = tui.TUILayout(make_console())

        assert layout.layout["header"].name == "header"
        assert layout.layout["progress"].name == "progress"
        assert layout.layout["body"].name == "body"
        assert layout.layout["status"].name == "status"

        layout.update_step(3, "Cable Check")
        assert layout.progress.current == 2
        assert layout._step_title == "Cable Check"

        body = Text("Body content")
        layout.update_body(body)
        assert layout._body_content is body

        layout.update_status("Working", spinner=True)
        assert layout.spinner.active is True
        assert layout.spinner.message == "Working"

        layout.show_error("Failure", "Details")
        layout.show_success("Recovered", "Done")
        layout.resize()

        assert layout._width == 72
        assert layout._height == 22
        assert layout.get_layout() is layout.layout


class TestAppControlFlow:
    def test_terminal_size_check_reports_small_and_acceptable_sizes(self, monkeypatch):
        monkeypatch.setattr(tui, "get_terminal_size", lambda: (40, 10))
        app = tui.TUIApp(make_console())

        ok, message = app.check_terminal_size()

        assert ok is False
        assert "Terminal too small" in message

        monkeypatch.setattr(tui, "get_terminal_size", lambda: (100, 30))

        ok, message = app.check_terminal_size()

        assert ok is True
        assert message == ""

    def test_confirm_handles_yes_no_defaults_and_interrupts(self, monkeypatch):
        monkeypatch.setattr(tui, "get_terminal_size", lambda: (100, 30))
        app = tui.TUIApp(make_console())

        monkeypatch.setattr(tui, "read_single_key", key_reader(["x", "y"]))
        assert app.confirm("Continue?") is True

        monkeypatch.setattr(tui, "read_single_key", key_reader(["n"]))
        assert app.confirm("Continue?", default=True) is False

        monkeypatch.setattr(tui, "read_single_key", key_reader(["\n"]))
        assert app.confirm("Continue?", default=True) is True

        monkeypatch.setattr(tui, "read_single_key", key_reader(["q"]))
        with pytest.raises(KeyboardInterrupt):
            app.confirm("Continue?")

    def test_prompt_text_supports_editing_default_and_cancel(self, monkeypatch):
        monkeypatch.setattr(tui, "get_terminal_size", lambda: (100, 30))
        app = tui.TUIApp(make_console())

        monkeypatch.setattr(tui, "read_single_key", key_reader(["a", "b", "\x7f", "c", "\n"]))
        assert app.prompt_text("Name") == "ac"

        monkeypatch.setattr(tui, "read_single_key", key_reader(["x", "\x15", "z", "\n"]))
        assert app.prompt_text("Name") == "z"

        monkeypatch.setattr(tui, "read_single_key", key_reader(["\x1b"]))
        assert app.prompt_text("Name", default="fallback") == "fallback"

    def test_wait_for_key_and_spinner_helper(self, monkeypatch):
        monkeypatch.setattr(tui, "get_terminal_size", lambda: (100, 30))
        app = tui.TUIApp(make_console())

        monkeypatch.setattr(tui, "read_single_key", key_reader(["k"]))
        assert app.wait_for_key() == "k"

        assert app.run_with_spinner("Working", lambda value: value * 2, 4) == 8
        assert app.tui.spinner.active is False

        monkeypatch.setattr(tui, "read_single_key", key_reader(["\x03"]))
        with pytest.raises(KeyboardInterrupt):
            app.wait_for_key()


def test_build_content_converts_strings_and_keeps_renderables():
    marker = Text("Existing")
    content = tui.build_content("plain", marker)

    assert len(content.renderables) == 2
    assert isinstance(content.renderables[0], Text)
    assert str(content.renderables[0]) == "plain"
    assert content.renderables[1] is marker
