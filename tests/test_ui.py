"""Headless tests for the Qt user interface."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from vizier.config import Config
from vizier.theme import setup_theme


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    setup_theme(application)
    return application


@pytest.fixture()
def window(app, tmp_path, monkeypatch):
    monkeypatch.setattr("vizier.utils.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("vizier.config.get_data_dir", lambda: tmp_path)
    from vizier.ui.main_window import VizierWindow

    win = VizierWindow(config=Config())
    try:
        yield win
    finally:
        win.close()


def test_window_builds_with_tools(window) -> None:
    assert "Vizier" in window.windowTitle()
    assert len(window.services.registry.names) >= 10
    assert window.tool_list.count() >= len(window.services.registry.names)
    assert window.state_label.text() == "IDLE"
    assert window.current_session is not None
    assert window.brand_header.wordmark.text() == "VIZIER"


def test_branding_is_headless_safe(app) -> None:
    from vizier.ui import branding

    assert branding.display_family() == "Rakkas"
    assert branding.animations_enabled() is False
    assert branding.create_splash() is None

    wordmark = branding.Wordmark()
    assert wordmark.text() == "VIZIER"
    assert wordmark.sizeHint().width() > 40
    assert wordmark.sizeHint().height() > 20

    widget = branding.BrandHeader("Test")
    assert widget.wordmark.text() == "VIZIER"


def test_chat_rendering(window) -> None:
    window._append_user_message("hello <world>")
    assert "hello <world>" in window.chat_display.toPlainText()

    window._begin_stream()
    window._on_chunk("streamed")
    window._end_stream()
    assert "streamed" in window.chat_display.toPlainText()


def test_yolo_toggle_updates_state(window) -> None:
    window._set_yolo(True)
    assert window.config.yolo_enabled is True
    assert window.yolo_checkbox.isChecked() is True
    assert window.yolo_action.isChecked() is True

    window._set_yolo(False)
    assert window.config.yolo_enabled is False


def test_new_session_and_clear(window) -> None:
    first = window.current_session.id
    window._append_user_message("hello")
    window._new_session()
    assert window.current_session.id != first
    assert window.chat_display.toPlainText().strip() != ""

    window._clear_chat()
    assert window.chat_display.toPlainText() == ""


# ---------------------------------------------------------------------------
# Secondary dialogs
# ---------------------------------------------------------------------------

class _FakeModel:
    def __init__(self, name: str, path: str = "") -> None:
        self.name = name
        self.filename = f"{name}.gguf"
        self.display_name = name
        self.quant = "Q4_K_M"
        self.vram_gb = 5.5
        self.description = "test model"
        self.local_path = path


class _FakeModelManager:
    def __init__(self, local: list[_FakeModel] | None = None) -> None:
        self.local = local or []
        self.downloaded: list[tuple[str, str]] = []

    def recommend_models(self, tier=None):
        return [_FakeModel("Test 8B")]

    def refresh_local(self):
        return list(self.local)

    def download_model(self, repo_id, filename, on_progress=None):
        self.downloaded.append((repo_id, filename))
        return f"/models/{filename}"


class _FakeSession:
    def __init__(self, session_id: str, name: str) -> None:
        self.id = session_id
        self.name = name
        self.updated = "2026-01-02T03:04:05"
        self.created = self.updated
        self.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]


class _FakeSessionManager:
    def __init__(self, sessions: list[_FakeSession]) -> None:
        self.sessions = {session.id: session for session in sessions}
        self.renamed: list[tuple[str, str]] = []
        self.deleted: list[str] = []

    def list_sessions(self):
        return list(self.sessions.values())

    def load(self, session_id):
        return self.sessions.get(session_id)

    def rename(self, session_id, name):
        self.renamed.append((session_id, name))
        self.sessions[session_id].name = name

    def delete(self, session_id):
        self.deleted.append(session_id)
        self.sessions.pop(session_id, None)


@pytest.fixture()
def dialog_env(monkeypatch, tmp_path):
    import vizier.logging_setup
    import vizier.ui.dialogs as dialogs

    monkeypatch.setattr(dialogs, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(dialogs, "get_hardware_tier", lambda: "gpu_8")
    monkeypatch.setattr(
        vizier.logging_setup, "get_log_file", lambda: tmp_path / "vizier.log"
    )
    return dialogs


def test_settings_dialog_roundtrip(app, dialog_env) -> None:
    config = Config()
    config.model_temperature = 0.55
    dialog = dialog_env.SettingsDialog(config)

    assert dialog.brand_header is not None
    assert dialog.brand_header.wordmark.text() == "VIZIER"
    values = dialog.values()
    assert values["model_temperature"] == 0.55
    assert values["yolo_enabled"] is False

    dialog.temperature.setValue(1.25)
    dialog.yolo.setChecked(True)
    assert dialog.values()["model_temperature"] == 1.25
    assert dialog.values()["yolo_enabled"] is True

    dialog._restore_defaults()
    assert dialog.values()["model_temperature"] == 0.7
    assert dialog.values()["yolo_enabled"] is False
    dialog.close()


def test_model_manager_lists_recommendations_and_local(app, dialog_env, tmp_path) -> None:
    local = _FakeModel("Local 3B", str(tmp_path / "local.gguf"))
    manager = _FakeModelManager(local=[local])
    dialog = dialog_env.ModelManagerDialog(manager, current_model=local.local_path)

    assert dialog.brand_header is not None
    assert dialog.brand_header.wordmark.text() == "VIZIER"
    assert dialog.recommend_table.rowCount() == 1
    assert dialog.local_list.count() == 1
    assert "loaded" in dialog.local_list.item(0).text()
    assert dialog.cancel_button.isHidden() is True
    assert dialog.progress.isHidden() is True

    dialog._set_downloading(True)
    assert dialog.download_button.isEnabled() is False
    assert dialog.cancel_button.isHidden() is False
    assert dialog.progress.isHidden() is False

    dialog._on_download_cancelled()
    assert dialog.download_button.isEnabled() is True
    assert dialog.cancel_button.isHidden() is True
    assert "cancelled" in dialog.status.text().lower()

    dialog.close()


def test_model_manager_selects_local_model(app, dialog_env, tmp_path) -> None:
    local = _FakeModel("Local 3B", str(tmp_path / "local.gguf"))
    dialog = dialog_env.ModelManagerDialog(_FakeModelManager(local=[local]))
    emitted: list[str] = []
    dialog.model_selected.connect(emitted.append)

    dialog.local_list.setCurrentRow(0)
    dialog._load_selected()

    assert emitted == [local.local_path]
    assert dialog.selected_path == local.local_path


def test_session_browser_preview_and_rename(app, dialog_env, monkeypatch) -> None:
    session = _FakeSession("abc", "First chat")
    manager = _FakeSessionManager([session])
    dialog = dialog_env.SessionBrowserDialog(manager)

    assert dialog.brand_header is not None
    assert dialog.list.count() == 1
    assert "hello" in dialog.preview.toPlainText()

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        lambda *args, **kwargs: ("Renamed chat", True),
    )
    dialog._rename_selected()
    assert manager.renamed == [("abc", "Renamed chat")]
    assert "Renamed chat" in dialog.list.item(0).text()
    dialog.close()


def test_session_browser_loads_selection(app, dialog_env) -> None:
    session = _FakeSession("abc", "First chat")
    dialog = dialog_env.SessionBrowserDialog(_FakeSessionManager([session]))
    dialog.list.setCurrentRow(0)

    dialog._load_selected()

    assert dialog.selected_session_id == "abc"


def test_about_dialog_with_patched_checks(app, dialog_env, monkeypatch) -> None:
    import vizier.diagnostics as diagnostics

    monkeypatch.setattr(
        diagnostics,
        "run_checks",
        lambda: [
            diagnostics.CheckResult("Python", diagnostics.OK, "3.13"),
            diagnostics.CheckResult("Model", diagnostics.WARN, "none"),
        ],
    )
    dialog = dialog_env.AboutDialog()

    assert dialog.checks.count() == 2
    assert "Vizier" in dialog.windowTitle()
    assert dialog.brand_header is not None
    assert dialog.brand_header.wordmark.text() == "VIZIER"
    assert "github.com/sonamcgoo-dev/vizier" in dialog.repo_link.text()
    dialog.close()

