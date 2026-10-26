"""
Secondary windows for Vizier: settings, model manager, session browser, and
the About / diagnostics dialog.

These dialogs are deliberately self-contained: they receive the shared
:class:`~vizier.config.Config` (and service objects where needed), validate
their input, and never perform network calls without an explicit click.
"""
from __future__ import annotations

import html
import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vizier.__version__ import __codename__, __version__
from vizier.config import Config
from vizier.ui.branding import (
    CRIMSON_BRIGHT,
    GOLD,
    GOLD_BRIGHT,
    IVORY_DIM,
    IVORY_MUTED,
    BrandedDialog,
    OrnamentDivider,
)
from vizier.utils import get_data_dir, get_hardware_tier

log = logging.getLogger("vizier.ui.dialogs")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _red_bold_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color:{GOLD}; font-weight:600; letter-spacing:1px;")
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{IVORY_MUTED};")
    return label


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsDialog(BrandedDialog):
    """Edit inference, agent, and safety settings."""

    brand_title = "Settings"

    def __init__(self, config: Config, parent: QWidget | None = None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Vizier Settings")
        self.setMinimumWidth(620)
        self.resize(680, 760)

        layout = QVBoxLayout(self)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 6, 0)
        body_layout.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)

        inference = QGroupBox("Model & inference")
        form = QFormLayout(inference)

        self.model_path = QLabel(config.model_path or "(no model selected)")
        self.model_path.setWordWrap(True)
        self.model_path.setStyleSheet(f"color:{IVORY_DIM};")
        form.addRow("Model", self.model_path)

        self.n_ctx = QSpinBox()
        self.n_ctx.setRange(512, 262144)
        self.n_ctx.setSingleStep(512)
        self.n_ctx.setValue(int(config.model_n_ctx))
        self.n_ctx.setSuffix(" tokens")
        form.addRow("Context window", self.n_ctx)

        self.gpu_layers = QSpinBox()
        self.gpu_layers.setRange(-1, 512)
        self.gpu_layers.setSpecialValueText("Auto / all layers")
        self.gpu_layers.setValue(int(config.model_n_gpu_layers))
        self.gpu_layers.setToolTip(
            "-1 offloads every layer to the GPU. 0 keeps everything on the CPU."
        )
        form.addRow("GPU layers", self.gpu_layers)

        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.05)
        self.temperature.setDecimals(2)
        self.temperature.setValue(float(config.model_temperature))
        form.addRow("Temperature", self.temperature)

        self.top_p = QDoubleSpinBox()
        self.top_p.setRange(0.0, 1.0)
        self.top_p.setSingleStep(0.05)
        self.top_p.setDecimals(2)
        self.top_p.setValue(float(config.model_top_p))
        form.addRow("Top-p", self.top_p)

        self.repeat_penalty = QDoubleSpinBox()
        self.repeat_penalty.setRange(0.5, 2.0)
        self.repeat_penalty.setSingleStep(0.05)
        self.repeat_penalty.setDecimals(2)
        self.repeat_penalty.setValue(float(config.model_repeat_penalty))
        form.addRow("Repeat penalty", self.repeat_penalty)

        body_layout.addWidget(inference)

        agent_group = QGroupBox("Agent")
        agent_form = QFormLayout(agent_group)
        self.max_rounds = QSpinBox()
        self.max_rounds.setRange(1, 100)
        self.max_rounds.setValue(int(config.max_tool_rounds))
        self.max_rounds.setToolTip(
            "Maximum reasoning/tool iterations before the agent stops."
        )
        agent_form.addRow("Max tool rounds", self.max_rounds)

        self.mcp_auto = QCheckBox("Connect to configured MCP servers on startup")
        self.mcp_auto.setChecked(bool(config.mcp_auto_start))
        agent_form.addRow("", self.mcp_auto)

        self.system_prompt = QPlainTextEdit(config.system_prompt)
        self.system_prompt.setMinimumHeight(96)
        agent_form.addRow("System prompt", self.system_prompt)
        body_layout.addWidget(agent_group)

        safety = QGroupBox("Safety")
        safety_layout = QVBoxLayout(safety)
        self.yolo = QCheckBox("YOLO mode — allow dangerous tools")
        self.yolo.setChecked(bool(config.yolo_enabled))
        safety_layout.addWidget(self.yolo)
        safety_layout.addWidget(_hint(
            "When YOLO is off, shell execution, file writes, deletes, and "
            "computer control are blocked before they run. YOLO never sends "
            "anything to the cloud."
        ))
        body_layout.addWidget(safety)

        self.data_dir_label = _hint(f"Data directory: {get_data_dir()}")
        body_layout.addWidget(self.data_dir_label)

        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox()
        defaults_button = buttons.addButton(
            "Restore defaults", QDialogButtonBox.ResetRole
        )
        buttons.addButton(QDialogButtonBox.Cancel)
        save_button = buttons.addButton("Save", QDialogButtonBox.AcceptRole)
        save_button.setObjectName("primary")
        defaults_button.clicked.connect(self._restore_defaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.finalize_brand()

    def _restore_defaults(self) -> None:
        defaults = Config()
        self.n_ctx.setValue(defaults.model_n_ctx)
        self.gpu_layers.setValue(defaults.model_n_gpu_layers)
        self.temperature.setValue(defaults.model_temperature)
        self.top_p.setValue(defaults.model_top_p)
        self.repeat_penalty.setValue(defaults.model_repeat_penalty)
        self.max_rounds.setValue(defaults.max_tool_rounds)
        self.mcp_auto.setChecked(defaults.mcp_auto_start)
        self.system_prompt.setPlainText(defaults.system_prompt)
        self.yolo.setChecked(defaults.yolo_enabled)

    def values(self) -> dict:
        return {
            "model_n_ctx": self.n_ctx.value(),
            "model_n_gpu_layers": self.gpu_layers.value(),
            "model_temperature": round(self.temperature.value(), 2),
            "model_top_p": round(self.top_p.value(), 2),
            "model_repeat_penalty": round(self.repeat_penalty.value(), 2),
            "max_tool_rounds": self.max_rounds.value(),
            "mcp_auto_start": self.mcp_auto.isChecked(),
            "system_prompt": self.system_prompt.toPlainText().strip(),
            "yolo_enabled": self.yolo.isChecked(),
        }


# ---------------------------------------------------------------------------
# Model manager
# ---------------------------------------------------------------------------

class DownloadWorker(QThread):
    """Downloads a GGUF model in the background with cancellation support."""

    progress = Signal(int, int, str)
    finished_ok = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, manager, repo_id: str, filename: str, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.repo_id = repo_id
        self.filename = filename
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _on_progress(self, done: int, total: int, name: str) -> None:
        if self._cancelled:
            raise RuntimeError("download cancelled")
        self.progress.emit(done, total, name)

    def run(self) -> None:  # pragma: no cover - network dependent
        try:
            path = self.manager.download_model(
                self.repo_id,
                self.filename,
                on_progress=self._on_progress,
            )
            self.finished_ok.emit(str(path))
        except Exception as exc:
            if self._cancelled or "cancelled" in str(exc).lower():
                self.cancelled.emit()
            else:
                log.exception("Model download failed")
                self.failed.emit(str(exc))


class ModelManagerDialog(BrandedDialog):
    """Browse hardware-aware recommendations, download models, load local files."""

    model_selected = Signal(str)
    brand_title = "Model Vault"

    def __init__(
        self,
        model_manager,
        current_model: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.manager = model_manager
        self.current_model = current_model
        self._download_worker: DownloadWorker | None = None
        self._selected_download: tuple[str, str] | None = None
        self._pending_load_path: str = ""
        self.selected_path: str = ""

        self.setWindowTitle("Vizier Model Manager")
        self.resize(860, 600)

        layout = QVBoxLayout(self)

        info_row = QHBoxLayout()
        info_row.addWidget(_hint(
            "Vizier runs entirely offline. Recommended models are sized for "
            "this machine; downloads come directly from Hugging Face."
        ), 1)
        self.tier_label = QLabel(f"Hardware tier: {get_hardware_tier()}")
        self.tier_label.setStyleSheet(f"color:{GOLD}; font-weight:600;")
        info_row.addWidget(self.tier_label)
        layout.addLayout(info_row)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_recommended_tab(), "Recommended")
        self.tabs.addTab(self._build_local_tab(), "Local models")
        layout.addWidget(self.tabs, 1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{IVORY_DIM};")
        layout.addWidget(self.status)

        buttons = QDialogButtonBox()
        browse = buttons.addButton("Browse…", QDialogButtonBox.ActionRole)
        self.cancel_button = buttons.addButton(
            "Cancel download", QDialogButtonBox.ActionRole
        )
        self.cancel_button.setVisible(False)
        close = buttons.addButton(QDialogButtonBox.Close)
        browse.clicked.connect(self._browse)
        self.cancel_button.clicked.connect(self._cancel_download)
        close.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_local()
        self.finalize_brand()

    # -- recommended ------------------------------------------------------

    def _build_recommended_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.recommend_table = QTableWidget(0, 4)
        self.recommend_table.setHorizontalHeaderLabels(
            ["Model", "Quant", "Approx. VRAM", "Why"]
        )
        self.recommend_table.verticalHeader().setVisible(False)
        self.recommend_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.recommend_table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        self.recommend_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recommend_table.horizontalHeader().setStretchLastSection(True)
        self.recommend_table.setColumnWidth(0, 260)
        self.recommend_table.setColumnWidth(1, 90)
        self.recommend_table.setColumnWidth(2, 110)
        layout.addWidget(self.recommend_table, 1)

        row = QHBoxLayout()
        self.download_button = QPushButton("Download selected")
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(self._download_selected)
        row.addWidget(self.download_button)
        row.addStretch(1)
        layout.addLayout(row)

        self._populate_recommendations()
        self.recommend_table.itemDoubleClicked.connect(
            lambda *_: self._download_selected()
        )
        return page

    def _populate_recommendations(self) -> None:
        try:
            models = self.manager.recommend_models()
        except Exception as exc:
            log.warning("Could not build recommendations: %s", exc)
            models = []
        self.recommend_table.setRowCount(len(models))
        for row, model in enumerate(models):
            name_item = QTableWidgetItem(model.display_name)
            name_item.setData(Qt.UserRole, (model.name, model.filename))
            name_item.setToolTip(f"{model.name}/{model.filename}")
            self.recommend_table.setItem(row, 0, name_item)
            self.recommend_table.setItem(row, 1, QTableWidgetItem(model.quant))
            self.recommend_table.setItem(
                row, 2, QTableWidgetItem(f"~{model.vram_gb:g} GB")
            )
            self.recommend_table.setItem(row, 3, QTableWidgetItem(model.description))
        if models:
            self.recommend_table.selectRow(0)

    # -- local ------------------------------------------------------------

    def _build_local_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(_hint(
            f"Models are stored in {get_data_dir() / 'models'}. "
            "Drop a .gguf file anywhere on the main window to load it."
        ))
        self.local_list = QListWidget()
        self.local_list.itemDoubleClicked.connect(lambda *_: self._load_selected())
        layout.addWidget(self.local_list, 1)

        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_local)
        load = QPushButton("Load selected")
        load.setObjectName("primary")
        load.clicked.connect(self._load_selected)
        row.addWidget(refresh)
        row.addStretch(1)
        row.addWidget(load)
        layout.addLayout(row)
        return page

    def _refresh_local(self) -> None:
        self.local_list.clear()
        try:
            models = self.manager.refresh_local()
        except Exception as exc:
            log.warning("Could not scan for local models: %s", exc)
            models = []
        for model in models:
            label = f"{model.display_name}  —  {model.vram_gb:g} GB"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, model.local_path)
            if model.local_path == self.current_model:
                item.setText(label + "   (loaded)")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor(CRIMSON_BRIGHT))
            self.local_list.addItem(item)
        if not models:
            placeholder = QListWidgetItem("No .gguf models downloaded yet.")
            placeholder.setFlags(Qt.NoItemFlags)
            self.local_list.addItem(placeholder)

    # -- actions ----------------------------------------------------------

    def _selected_row_data(self) -> tuple[str, str] | None:
        row = self.recommend_table.currentRow()
        if row < 0:
            return None
        item = self.recommend_table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _download_selected(self) -> None:
        if self._download_worker is not None and self._download_worker.isRunning():
            QMessageBox.information(self, "Vizier", "A download is already running.")
            return
        data = self._selected_row_data()
        if not data:
            QMessageBox.information(self, "Vizier", "Select a model first.")
            return
        repo_id, filename = data
        self._selected_download = data
        self._set_downloading(True)
        self.progress.setRange(0, 0)
        self.status.setText(f"Downloading {filename}…")

        self._download_worker = DownloadWorker(self.manager, repo_id, filename, self)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.finished_ok.connect(self._on_downloaded)
        self._download_worker.failed.connect(self._on_download_failed)
        self._download_worker.cancelled.connect(self._on_download_cancelled)
        self._download_worker.finished.connect(self._on_worker_finished)
        self._download_worker.start()

    def _set_downloading(self, active: bool) -> None:
        """Toggle the widgets that only make sense while a download runs."""
        self.download_button.setEnabled(not active)
        self.cancel_button.setVisible(active)
        self.cancel_button.setEnabled(active)
        self.progress.setVisible(active)
        self.recommend_table.setEnabled(not active)

    def _cancel_download(self) -> None:
        worker = self._download_worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling download…")

    def _on_worker_finished(self) -> None:
        # QThread.finished fires after run() returns, so the worker can be
        # dropped without risking "QThread destroyed while running".
        if self._download_worker is not None:
            self._download_worker.deleteLater()
        self._download_worker = None
        if self._pending_load_path:
            path, self._pending_load_path = self._pending_load_path, ""
            self._select_and_close(path)

    def _on_progress(self, done: int, total: int, name: str) -> None:
        if total > 0:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(done / total * 1000))
            self.status.setText(
                f"Downloading {name} — {done / (1024 ** 2):.1f} / "
                f"{total / (1024 ** 2):.1f} MB"
            )
        else:
            self.status.setText(f"Downloading {name} — {done / (1024 ** 2):.1f} MB")

    def _on_downloaded(self, path: str) -> None:
        self._set_downloading(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status.setText(f"Downloaded {Path(path).name}")
        self._refresh_local()
        answer = QMessageBox.question(
            self,
            "Model downloaded",
            f"{Path(path).name} is ready.\n\nLoad it now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            # Wait for QThread.finished before leaving the dialog so the
            # worker is never destroyed while still running.
            self._pending_load_path = path
            self.status.setText(f"Loading {Path(path).name}…")

    def _on_download_failed(self, message: str) -> None:
        self._set_downloading(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status.setText("Download failed.")
        QMessageBox.critical(
            self,
            "Download failed",
            f"Could not download the model.\n\n{message}\n\n"
            "Check your internet connection, or download the .gguf file "
            "manually and drop it on the main window.",
        )

    def _on_download_cancelled(self) -> None:
        self._set_downloading(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status.setText("Download cancelled. Partial files were removed.")

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a GGUF model",
            str(Path.home()),
            "GGUF models (*.gguf);;All files (*)",
        )
        if path:
            self._select_and_close(path)

    def _load_selected(self) -> None:
        item = self.local_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Vizier", "Select a local model first.")
            return
        path = item.data(Qt.UserRole)
        if not path:
            return
        self._select_and_close(str(path))

    def _select_and_close(self, path: str) -> None:
        self.selected_path = path
        self.model_selected.emit(path)
        self.accept()

    def closeEvent(self, event) -> None:
        worker = self._download_worker
        if worker is not None and worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Download in progress",
                "A model download is still running.\n\nCancel it and close?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            worker.cancel()
            self.status.setText("Cancelling download…")
            if not worker.wait(5000):
                QMessageBox.information(
                    self,
                    "Vizier",
                    "The download is still stopping. Please try closing again "
                    "in a moment.",
                )
                event.ignore()
                return
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Session browser
# ---------------------------------------------------------------------------

class SessionBrowserDialog(BrandedDialog):
    """List past sessions and load, rename, or delete them."""

    brand_title = "Sessions"

    def __init__(self, session_manager, parent: QWidget | None = None):
        super().__init__(parent)
        self.manager = session_manager
        self.selected_session_id: str = ""
        self.setWindowTitle("Vizier Sessions")
        self.resize(660, 500)

        layout = QVBoxLayout(self)
        layout.addWidget(_hint(
            "Sessions are saved automatically after each turn and stored "
            "locally in your Vizier data directory."
        ))

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda *_: self._load_selected())
        layout.addWidget(self.list, 1)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(120)
        self.preview.setPlaceholderText("Select a session to preview it.")
        layout.addWidget(self.preview)

        row = QHBoxLayout()
        rename = QPushButton("Rename…")
        rename.clicked.connect(self._rename_selected)
        delete = QPushButton("Delete")
        delete.setObjectName("danger")
        delete.clicked.connect(self._delete_selected)
        row.addWidget(rename)
        row.addWidget(delete)
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        load = QPushButton("Load session")
        load.setObjectName("primary")
        load.clicked.connect(self._load_selected)
        row.addWidget(cancel)
        row.addWidget(load)
        layout.addLayout(row)

        self.list.currentItemChanged.connect(self._update_preview)
        self._refresh()
        self.finalize_brand()

    def _refresh(self) -> None:
        self.list.clear()
        try:
            sessions = self.manager.list_sessions()
        except Exception as exc:
            log.warning("Could not list sessions: %s", exc)
            sessions = []
        for session in sessions:
            label = session.name or "Untitled session"
            stamp = (session.updated or session.created or "")[:19].replace("T", " ")
            count = len(session.messages)
            item = QListWidgetItem(f"{label}   —   {stamp}   ({count} messages)")
            item.setData(Qt.UserRole, session.id)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _current_session(self):
        item = self.list.currentItem()
        if item is None:
            return None
        return self.manager.load(str(item.data(Qt.UserRole)))

    def _update_preview(self, *_args) -> None:
        session = self._current_session()
        if session is None:
            self.preview.clear()
            return
        parts = []
        for message in session.messages[-12:]:
            role = str(message.get("role", "?")).replace("Role.", "")
            content = str(message.get("content") or "")
            if len(content) > 400:
                content = content[:400] + "…"
            parts.append(f"[{role}] {content}")
        self.preview.setPlainText("\n\n".join(parts) or "(empty session)")

    def _load_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        self.selected_session_id = str(item.data(Qt.UserRole))
        self.accept()

    def _rename_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        session = self._current_session()
        if session is None:
            return
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self, "Rename session", "Session name:", text=session.name
        )
        if ok and name.strip():
            self.manager.rename(session.id, name.strip())
            self._refresh()

    def _delete_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        session = self._current_session()
        if session is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete session",
            f"Delete “{session.name}”? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.manager.delete(session.id)
            self._refresh()


# ---------------------------------------------------------------------------
# About / diagnostics
# ---------------------------------------------------------------------------

class AboutDialog(BrandedDialog):
    """Version information, environment details, and a health check."""

    brand_title = "About Vizier"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("About Vizier")
        self.resize(680, 660)

        layout = QVBoxLayout(self)

        subtitle = QLabel(f"Royal Advisor · {__codename__}")
        subtitle.setStyleSheet(
            f"color:{GOLD_BRIGHT}; font-size:11pt; letter-spacing:1px;"
        )
        layout.addWidget(subtitle)
        layout.addWidget(_hint(
            "A 100% local AI agent for computer use, filesystem management, "
            "and general assistance. No cloud. No BYOK. No telemetry."
        ))
        layout.addWidget(OrnamentDivider())

        info = QLabel()
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        info.setText(self._environment_html())
        layout.addWidget(info)

        layout.addWidget(_red_bold_label("Health check"))
        self.checks = QListWidget()
        self.checks.setMaximumHeight(190)
        layout.addWidget(self.checks)
        run = QPushButton("Run self-check")
        run.clicked.connect(self._run_checks)
        layout.addWidget(run, alignment=Qt.AlignLeft)

        buttons = QDialogButtonBox()
        copy = buttons.addButton("Copy diagnostics", QDialogButtonBox.ActionRole)
        log_button = buttons.addButton("Open log folder", QDialogButtonBox.ActionRole)
        close = buttons.addButton(QDialogButtonBox.Close)
        copy.clicked.connect(self._copy_diagnostics)
        log_button.clicked.connect(self._open_log_folder)
        close.clicked.connect(self.accept)
        layout.addWidget(buttons)

        self._run_checks()
        self.finalize_brand()

    def _environment_html(self) -> str:
        from vizier.logging_setup import get_log_file

        try:
            from PySide6 import __version__ as qt_version
        except Exception:
            qt_version = "unknown"
        rows = [
            ("Vizier", f"{__version__} ({__codename__})"),
            ("Python", sys.version.split()[0]),
            ("Qt / PySide6", qt_version),
            ("Platform", sys.platform),
            ("Data directory", str(get_data_dir())),
            ("Log file", str(get_log_file())),
        ]
        return "<table cellspacing='4'>" + "".join(
            f"<tr><td style='color:{GOLD};'><b>{html.escape(k)}</b></td>"
            f"<td style='color:{IVORY_DIM};'>{html.escape(str(v))}</td></tr>"
            for k, v in rows
        ) + "</table>"

    def _run_checks(self) -> None:
        from vizier.diagnostics import FAIL, OK, WARN, run_checks

        self.checks.clear()
        for result in run_checks():
            item = QListWidgetItem(
                f"[{result.symbol}] {result.name}"
                + (f" — {result.detail}" if result.detail else "")
            )
            if result.status == OK:
                item.setForeground(QColor("#4FD1C5"))
            elif result.status == WARN:
                item.setForeground(QColor(GOLD))
            elif result.status == FAIL:
                item.setForeground(QColor(CRIMSON_BRIGHT))
            self.checks.addItem(item)

    def _copy_diagnostics(self) -> None:
        from vizier.diagnostics import run_checks

        lines = [f"Vizier {__version__} ({__codename__})", self._environment_html(), ""]
        lines.extend(
            f"[{result.symbol}] {result.name}: {result.detail}" for result in run_checks()
        )
        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "Vizier", "Diagnostics copied to the clipboard.")

    def _open_log_folder(self) -> None:
        from vizier.logging_setup import get_log_dir

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_log_dir())))
