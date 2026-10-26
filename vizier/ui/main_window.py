"""
Vizier main application window.

A Qt desktop interface for the Vizier local AI agent.  The heavy work
(model loading and agent turns) runs on background threads so the UI
stays responsive.
"""
from __future__ import annotations

import asyncio
import contextlib
import html
import json
import logging
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vizier.config import Config
from vizier.core.agent import VizierAgent
from vizier.core.llm.model_manager import ModelManager
from vizier.logging_setup import (
    install_exception_hook,
    install_faulthandler,
    log_startup_banner,
    setup_logging,
)
from vizier.theme import setup_theme
from vizier.tools import VizierServices
from vizier.ui.branding import (
    CRIMSON_BRIGHT,
    GOLD,
    GOLD_BRIGHT,
    INK,
    IVORY,
    SURFACE,
    BrandHeader,
    OrnamentDivider,
    PalaceBackdrop,
    StatusPill,
    create_splash,
    display_family,
    reveal_window,
)
from vizier.ui.dialogs import (
    AboutDialog,
    ModelManagerDialog,
    SessionBrowserDialog,
    SettingsDialog,
)
from vizier.utils import (
    detect_hardware,
    get_asset_path,
    get_hardware_tier,
)

log = logging.getLogger("vizier.ui")


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class LoadModelWorker(QThread):
    """Loads a GGUF model and prepares the agent off the UI thread."""

    progress = Signal(str)
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, services: VizierServices, model_path: str, yolo: bool):
        super().__init__()
        self.services = services
        self.model_path = model_path
        self.yolo = yolo

    def run(self) -> None:  # pragma: no cover - requires a real model
        try:
            self.progress.emit("Loading model…")
            self.services.config.model_path = self.model_path
            provider = self.services.load_llm(self.model_path)
            asyncio.run(provider.load())

            self.progress.emit("Building tools…")
            self.services.build_tools()
            self.services.connect_mcp_servers()

            self.progress.emit("Starting agent…")
            agent = self.services.create_agent(yolo=self.yolo)
            self.loaded.emit(agent)
        except Exception as exc:
            log.exception("Model load failed")
            self.failed.emit(str(exc))


class ChatWorker(QThread):
    """Runs a single agent turn off the UI thread."""

    chunk = Signal(str)
    tool_started = Signal(str, str)
    tool_finished = Signal(str, str, bool)
    state_changed = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, agent: VizierAgent, text: str):
        super().__init__()
        self.agent = agent
        self.text = text

    def run(self) -> None:
        agent = self.agent

        async def on_chunk(text: str) -> None:
            self.chunk.emit(text)

        def on_tool_start(tool_call) -> None:
            try:
                args = json.dumps(tool_call.arguments, ensure_ascii=False)
            except Exception:
                args = str(tool_call.arguments)
            self.tool_started.emit(tool_call.name, args)

        def on_tool_result(tool_call, result: str, success: bool) -> None:
            self.tool_finished.emit(tool_call.name, str(result), bool(success))

        def on_state(state) -> None:
            self.state_changed.emit(getattr(state, "value", str(state)))

        agent.config.on_llm_chunk = on_chunk
        agent.config.on_tool_start = on_tool_start
        agent.config.on_tool_result = on_tool_result
        agent.config.on_state_change = on_state
        try:
            result = asyncio.run(agent.run(self.text))
            self.completed.emit(result)
        except Exception as exc:
            log.exception("Agent turn failed")
            self.failed.emit(str(exc))
        finally:
            agent.config.on_llm_chunk = None
            agent.config.on_tool_start = None
            agent.config.on_tool_result = None
            agent.config.on_state_change = None


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class VizierWindow(QMainWindow):
    """Main Vizier application window."""

    def __init__(self, config: Config | None = None, model_path: str | None = None):
        super().__init__()
        from vizier.__version__ import __version__

        self.config = config or Config.load()
        self.services = VizierServices(self.config)
        self.model_manager = ModelManager()
        self.agent: VizierAgent | None = None
        self.current_session = None
        self._worker: ChatWorker | None = None
        self._loader: LoadModelWorker | None = None
        self._streaming = False
        self._current_model_path = ""

        self.setWindowTitle(f"Vizier — Royal Advisor {__version__}")
        self.setWindowIcon(self._make_icon())
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        self._build_menu()
        self._build_ui()
        self._populate_tools()
        self._new_session()

        if model_path and Path(model_path).exists():
            self._load_model(model_path)
        elif self.config.model_path and Path(self.config.model_path).exists():
            # Reopen the last model automatically; this is what users expect
            # from a desktop app and avoids a blank first screen.
            QTimer.singleShot(0, lambda: self._load_model(self.config.model_path))

    # -- UI construction --------------------------------------------------

    def _make_icon(self) -> QIcon:
        icon_path = get_asset_path("vizier.ico")
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon
        png_path = get_asset_path("vizier.png")
        if png_path.exists():
            icon = QIcon(str(png_path))
            if not icon.isNull():
                return icon
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(INK))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(SURFACE))
        painter.setPen(QPen(QColor(GOLD), 2))
        painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
        painter.setPen(QColor(GOLD_BRIGHT))
        font = QFont(display_family())
        font.setPixelSize(38)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "V")
        painter.end()
        return QIcon(pixmap)

    def _build_menu(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")

        load_action = QAction("&Load Model…", self)
        load_action.setShortcut("Ctrl+L")
        load_action.triggered.connect(self._choose_model)
        file_menu.addAction(load_action)

        models_action = QAction("Model &Manager…", self)
        models_action.setShortcut("Ctrl+M")
        models_action.triggered.connect(self._open_model_manager)
        file_menu.addAction(models_action)
        file_menu.addSeparator()

        new_action = QAction("&New Chat", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_session)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Session…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_sessions)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Session", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_session)
        file_menu.addAction(save_action)
        file_menu.addSeparator()

        settings_action = QAction("&Settings…", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = bar.addMenu("&Edit")
        clear_action = QAction("&Clear Chat", self)
        clear_action.setShortcut("Ctrl+Shift+Delete")
        clear_action.triggered.connect(self._clear_chat)
        edit_menu.addAction(clear_action)

        view_menu = bar.addMenu("&View")
        self.yolo_action = QAction("&YOLO Mode", self, checkable=True)
        self.yolo_action.setChecked(self.config.yolo_enabled)
        self.yolo_action.toggled.connect(self._set_yolo)
        view_menu.addAction(self.yolo_action)
        folder_action = QAction("Open &Data Folder", self)
        folder_action.triggered.connect(self._open_data_folder)
        view_menu.addAction(folder_action)

        help_menu = bar.addMenu("&Help")
        docs_action = QAction("&Documentation", self)
        docs_action.setShortcut("F1")
        docs_action.triggered.connect(self._open_documentation)
        help_menu.addAction(docs_action)
        about_action = QAction("&About Vizier", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_ui(self) -> None:
        central = PalaceBackdrop()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.brand_header = BrandHeader()
        self.status_pill = StatusPill()
        self.state_label = self.status_pill.label
        self.local_badge = QLabel("●  LOCAL ONLY")
        self.local_badge.setObjectName("Badge")
        self.local_badge.setToolTip(
            "Every prompt, reply, and tool call stays on this machine."
        )
        self.brand_header.add_corner_widget(self.local_badge)
        self.brand_header.add_corner_widget(self.status_pill)
        root.addWidget(self.brand_header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_chat_area())
        splitter.setSizes([292, 908])
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.status = self.statusBar()
        self.status.showMessage("The court is ready. Load a GGUF model to begin.")
        from vizier.__version__ import __version__

        offline = QLabel("NO CLOUD  ·  NO TELEMETRY")
        offline.setStyleSheet(
            "color:#4FD1C5; font-size:8pt; letter-spacing:1px; padding-right:14px;"
        )
        self.status.addPermanentWidget(offline)
        version_label = QLabel(f"v{__version__}")
        version_label.setObjectName("VersionLabel")
        self.status.addPermanentWidget(version_label)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setToolTip("Drop a .gguf model anywhere on this window to load it.")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        eyebrow = QLabel("THE COURT")
        eyebrow.setObjectName("Eyebrow")
        layout.addWidget(eyebrow)
        layout.addWidget(OrnamentDivider())

        # Model group ------------------------------------------------------
        model_group = QGroupBox("Your Advisor")
        model_layout = QVBoxLayout(model_group)
        self.model_label = QLabel("No model loaded")
        self.model_label.setWordWrap(True)
        self.model_label.setStyleSheet(f"color:{IVORY}; font-weight:600;")
        model_layout.addWidget(self.model_label)

        self.model_hint = QLabel("")
        self.model_hint.setWordWrap(True)
        self.model_hint.setStyleSheet(f"color:{GOLD}; font-size:8pt;")
        model_layout.addWidget(self.model_hint)

        self.load_button = QPushButton("Load GGUF Model…")
        self.load_button.setObjectName("primary")
        self.load_button.clicked.connect(self._choose_model)
        model_layout.addWidget(self.load_button)

        self.models_button = QPushButton("Model Manager…")
        self.models_button.clicked.connect(self._open_model_manager)
        model_layout.addWidget(self.models_button)

        layout.addWidget(model_group)

        # Controls group ---------------------------------------------------
        controls = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls)

        self.yolo_checkbox = QCheckBox("YOLO mode (allow dangerous tools)")
        self.yolo_checkbox.setChecked(self.config.yolo_enabled)
        self.yolo_checkbox.setToolTip(
            "When disabled, destructive tools (shell, delete, write) are blocked."
        )
        self.yolo_checkbox.toggled.connect(self._set_yolo)
        controls_layout.addWidget(self.yolo_checkbox)

        temp_row = QHBoxLayout()
        temp_row.addWidget(QLabel("Temperature"))
        self.temp_label = QLabel(f"{self.config.model_temperature:.2f}")
        self.temp_label.setStyleSheet(f"color:{GOLD_BRIGHT}; font-weight:600;")
        temp_row.addStretch(1)
        temp_row.addWidget(self.temp_label)
        controls_layout.addLayout(temp_row)

        self.settings_button = QPushButton("Settings…")
        self.settings_button.clicked.connect(self._open_settings)
        controls_layout.addWidget(self.settings_button)
        layout.addWidget(controls)

        # Tools group ------------------------------------------------------
        tools_group = QGroupBox("Tools")
        tools_layout = QVBoxLayout(tools_group)
        self.tool_list = QListWidget()
        self.tool_list.setAlternatingRowColors(False)
        self.tool_list.itemChanged.connect(self._on_tool_toggled)
        tools_layout.addWidget(self.tool_list)
        layout.addWidget(tools_group, 1)

        # Session buttons --------------------------------------------------
        layout.addWidget(OrnamentDivider())
        self.new_chat_button = QPushButton("New Chat")
        self.new_chat_button.setObjectName("primary")
        self.new_chat_button.clicked.connect(self._new_session)
        layout.addWidget(self.new_chat_button)

        session_row = QHBoxLayout()
        session_row.setSpacing(8)
        self.sessions_button = QPushButton("Sessions…")
        self.sessions_button.clicked.connect(self._open_sessions)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_chat)
        session_row.addWidget(self.sessions_button)
        session_row.addWidget(self.clear_button)
        layout.addLayout(session_row)

        return sidebar

    def _build_chat_area(self) -> QWidget:
        area = QWidget()
        area.setObjectName("ChatArea")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("ChatHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 13, 22, 13)
        header_layout.setSpacing(12)

        title_column = QVBoxLayout()
        title_column.setSpacing(1)
        eyebrow = QLabel("PRIVATE AUDIENCE")
        eyebrow.setObjectName("Eyebrow")
        title_column.addWidget(eyebrow)
        self.chat_title = QLabel("Vizier Chat")
        self.chat_title.setObjectName("ChatTitle")
        title_column.addWidget(self.chat_title)
        header_layout.addLayout(title_column)
        header_layout.addStretch(1)

        chamber = QLabel("●  SEALED CHAMBER")
        chamber.setObjectName("Badge")
        chamber.setToolTip("Sessions and models are stored locally in your data folder.")
        header_layout.addWidget(chamber)
        layout.addWidget(header)

        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("ChatDisplay")
        self.chat_display.setReadOnly(True)
        self.chat_display.setAcceptRichText(True)
        self.chat_display.setMinimumHeight(180)
        layout.addWidget(self.chat_display, 1)

        input_frame = QFrame()
        input_frame.setObjectName("InputBar")
        input_frame.setAttribute(Qt.WA_StyledBackground, True)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(18, 13, 18, 13)
        input_layout.setSpacing(10)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText(
            "Ask Vizier anything…  (Enter to send)"
        )
        self.message_input.setMinimumHeight(40)
        self.message_input.returnPressed.connect(self._send_message)

        self.send_button = QPushButton("Send  ›")
        self.send_button.setObjectName("primary")
        self.send_button.setMinimumHeight(40)
        self.send_button.setMinimumWidth(104)
        self.send_button.clicked.connect(self._send_message)

        input_layout.addWidget(self.message_input, 1)
        input_layout.addWidget(self.send_button)
        layout.addWidget(input_frame)

        return area

    # -- tools / model ----------------------------------------------------

    def _populate_tools(self) -> None:
        self.tool_list.blockSignals(True)
        self.tool_list.clear()
        registry = self.services.registry
        if not registry.names:
            self.services.build_tools()
        grouped = registry.by_category()
        for category in sorted(grouped):
            header = QListWidgetItem(category.upper())
            header.setFlags(Qt.ItemIsEnabled)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            header.setForeground(QColor(GOLD))
            self.tool_list.addItem(header)
            for tool in grouped[category]:
                item = QListWidgetItem(tool.name)
                item.setData(Qt.UserRole, tool.name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.Checked if tool.enabled else Qt.Unchecked
                )
                if tool.dangerous:
                    item.setForeground(QColor(CRIMSON_BRIGHT))
                    item.setToolTip("Dangerous — requires YOLO mode")
                self.tool_list.addItem(item)
        self.tool_list.blockSignals(False)

    def _on_tool_toggled(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.UserRole)
        if not name:
            return
        if item.checkState() == Qt.Checked:
            self.services.registry.enable(str(name))
        else:
            self.services.registry.disable(str(name))

    def _choose_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a GGUF model",
            str(self.config.model_path or Path.home()),
            "GGUF models (*.gguf);;All files (*)",
        )
        if path:
            self._load_model(path)

    def _load_model(self, path: str) -> None:
        if self._loader is not None and self._loader.isRunning():
            QMessageBox.information(self, "Vizier", "A model is already loading.")
            return
        self._current_model_path = path
        self.load_button.setEnabled(False)
        self.models_button.setEnabled(False)
        self.send_button.setEnabled(False)
        self.model_label.setText(f"Loading…\n{Path(path).name}")
        try:
            size_gb = Path(path).stat().st_size / (1024 ** 3)
            self.model_hint.setText(f"{size_gb:.2f} GB on disk")
        except OSError:
            self.model_hint.setText("")
        self.status.showMessage("Loading model…")

        self._loader = LoadModelWorker(
            self.services, path, self.yolo_checkbox.isChecked()
        )
        self._loader.progress.connect(self.status.showMessage)
        self._loader.loaded.connect(self._on_model_loaded)
        self._loader.failed.connect(self._on_model_failed)
        self._loader.finished.connect(self._on_loader_finished)
        self._loader.start()

    def _on_loader_finished(self) -> None:
        if self._loader is not None:
            self._loader.deleteLater()
        self._loader = None

    def _on_model_loaded(self, agent: VizierAgent) -> None:
        self.agent = agent
        self.load_button.setEnabled(True)
        self.models_button.setEnabled(True)
        self.send_button.setEnabled(True)
        self.config.model_path = self._current_model_path
        try:
            self.config.save()
        except Exception:
            log.debug("Could not persist configuration", exc_info=True)

        self.model_label.setText(f"{Path(self._current_model_path).name}")
        self.model_label.setToolTip(self._current_model_path)
        try:
            size_gb = Path(self._current_model_path).stat().st_size / (1024 ** 3)
            self.model_hint.setText(f"{size_gb:.2f} GB on disk")
        except OSError:
            self.model_hint.setText("")
        hw = detect_hardware()
        tier = get_hardware_tier()
        gpu = hw["gpus"][0]["name"] if hw["gpus"] else "CPU"
        self.status.showMessage(
            f"Model loaded — {tier} tier, {gpu}, {hw['ram_gb']} GB RAM"
        )
        self._append_assistant_note(
            f"Model loaded: <b>{html.escape(Path(self._current_model_path).name)}</b>"
        )
        self.message_input.setFocus()

    def _on_model_failed(self, message: str) -> None:
        self.load_button.setEnabled(True)
        self.models_button.setEnabled(True)
        self.send_button.setEnabled(False)
        self.model_label.setText("No model loaded")
        self.model_hint.setText("")
        self.status.showMessage("Model load failed")
        QMessageBox.critical(self, "Model load failed", message)

    # -- dialogs ----------------------------------------------------------

    def _open_model_manager(self) -> None:
        dialog = ModelManagerDialog(
            self.model_manager,
            current_model=self._current_model_path,
            parent=self,
        )
        dialog.model_selected.connect(self._load_model)
        dialog.exec()

    def _open_settings(self) -> None:
        from PySide6.QtWidgets import QDialog

        before = {
            "model_n_ctx": self.config.model_n_ctx,
            "model_n_gpu_layers": self.config.model_n_gpu_layers,
        }
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.config.update(dialog.values())
        try:
            self.config.save()
        except Exception:
            log.warning("Could not save settings", exc_info=True)

        self.temp_label.setText(f"{self.config.model_temperature:.2f}")
        self.yolo_checkbox.blockSignals(True)
        self.yolo_checkbox.setChecked(self.config.yolo_enabled)
        self.yolo_checkbox.blockSignals(False)
        self.yolo_action.blockSignals(True)
        self.yolo_action.setChecked(self.config.yolo_enabled)
        self.yolo_action.blockSignals(False)
        if self.agent is not None:
            self.agent.config.system_prompt = self.config.system_prompt
            self.agent.config.max_tool_rounds = self.config.max_tool_rounds
            self.agent.set_yolo(self.config.yolo_enabled)
        provider = self.services.llm_provider
        if provider is not None:
            provider.config.temperature = self.config.model_temperature
            provider.config.top_p = self.config.model_top_p
            provider.config.repeat_penalty = self.config.model_repeat_penalty
            provider.config.n_ctx = self.config.model_n_ctx
            provider.config.n_gpu_layers = self.config.model_n_gpu_layers

        reload_needed = (
            self.agent is not None
            and any(getattr(self.config, k) != v for k, v in before.items())
        )
        self.status.showMessage("Settings saved.", 5000)
        if reload_needed:
            QMessageBox.information(
                self,
                "Reload required",
                "Context size and GPU layer changes take effect the next time "
                "the model is loaded.",
            )

    def _open_sessions(self) -> None:
        from PySide6.QtWidgets import QDialog

        dialog = SessionBrowserDialog(self.services.session_manager, self)
        if (
            dialog.exec() == QDialog.Accepted
            and dialog.selected_session_id
        ):
            session = self.services.session_manager.load(dialog.selected_session_id)
            if session is not None:
                self._restore_session(session)

    def _restore_session(self, session) -> None:
        from vizier.core.types import Message, Role

        if self.agent is not None and self.current_session is not None:
            try:
                self.services.session_manager.save(
                    self.current_session.id, self.agent.history
                )
            except Exception:
                log.debug("Could not save the previous session", exc_info=True)
        self.current_session = session
        self.chat_display.clear()
        self.chat_title.setText(session.name or "Vizier Chat")
        if self.agent is not None:
            self.agent.history.clear()
            for data in session.messages:
                try:
                    message = Message.from_dict(data)
                except Exception:
                    continue
                self.agent.history.append(message)
                if message.role == Role.USER and message.content:
                    self._append_user_message(message.content)
                elif message.role == Role.ASSISTANT and message.content:
                    self._append_assistant_note(html.escape(message.content))
        self.status.showMessage(
            f"Loaded session “{session.name}” ({len(session.messages)} messages).",
            5000,
        )

    def _open_documentation(self) -> None:
        from vizier.utils import get_resource_dir

        candidates = [
            get_resource_dir() / "README.md",
            get_resource_dir().parent / "README.md",
            Path(__file__).resolve().parents[2] / "README.md",
        ]
        for candidate in candidates:
            if candidate.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(candidate)))
                return
        self._show_about()

    def _open_data_folder(self) -> None:
        from vizier.utils import get_data_dir

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_data_dir())))

    # -- chat -------------------------------------------------------------

    def _new_session(self) -> None:
        if self.agent is not None:
            self.agent.clear_history()
        self.chat_display.clear()
        self.current_session = self.services.session_manager.create(
            name="New chat",
            model_path=self.config.model_path,
            config=self.config,
        )
        self.chat_title.setText("Vizier Chat")
        self._show_welcome()

    def _show_welcome(self) -> None:
        tier = get_hardware_tier()
        hw = detect_hardware()
        gpu = hw["gpus"][0]["name"] if hw["gpus"] else "CPU only"
        lines = [
            "Welcome to <b style='color:#F2D79A;'>Vizier</b>, your local royal advisor.",
            f"<span style='color:#4FD1C5;'>The court is quiet. Detected "
            f"{html.escape(tier)} tier — {html.escape(gpu)}, {hw['ram_gb']} GB RAM.</span>",
        ]
        if not self.config.model_path:
            recommendation = ""
            try:
                models = self.model_manager.recommend_models(tier)
                if models:
                    best = models[0]
                    recommendation = (
                        f"Recommended for this machine: "
                        f"<b>{html.escape(best.display_name)}</b> "
                        f"({best.quant}, ~{best.vram_gb:g} GB VRAM)."
                    )
            except Exception:
                pass
            lines.append(
                "No model is loaded yet. Open <b>File → Model Manager…</b> "
                "to download one, or drop a <code>.gguf</code> file on this window."
            )
            if recommendation:
                lines.append(recommendation)
        else:
            lines.append("Your previous model is loading. This may take a moment.")
        self._append_assistant_note("<br><br>".join(lines))

    def _clear_chat(self) -> None:
        self.chat_display.clear()
        if self.agent is not None:
            self.agent.clear_history()

    def _save_session(self) -> None:
        if self.agent is None or self.current_session is None:
            QMessageBox.information(self, "Vizier", "Nothing to save yet.")
            return
        self.services.session_manager.save(
            self.current_session.id, self.agent.history
        )
        self.status.showMessage("Session saved.", 3000)

    def _set_yolo(self, enabled: bool) -> None:
        self.config.yolo_enabled = enabled
        self.yolo_checkbox.blockSignals(True)
        self.yolo_checkbox.setChecked(enabled)
        self.yolo_checkbox.blockSignals(False)
        self.yolo_action.blockSignals(True)
        self.yolo_action.setChecked(enabled)
        self.yolo_action.blockSignals(False)
        if self.agent is not None:
            self.agent.set_yolo(enabled)
        with contextlib.suppress(Exception):
            self.config.save()

    def _send_message(self) -> None:
        text = self.message_input.text().strip()
        if not text:
            return
        if self.agent is None:
            QMessageBox.information(
                self,
                "No model loaded",
                "Load a GGUF model first (File → Load Model…).",
            )
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self.message_input.clear()
        self._append_user_message(text)
        if (
            self.current_session is not None
            and self.current_session.name in ("", "New chat", "Session")
        ):
            title = text.strip().splitlines()[0][:48]
            self.services.session_manager.rename(self.current_session.id, title)
            self.current_session.name = title
            self.chat_title.setText(title)
        self.send_button.setEnabled(False)
        self.message_input.setEnabled(False)
        self._streaming = False
        self._set_state("THINKING")

        self._worker = ChatWorker(self.agent, text)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.tool_started.connect(self._on_tool_started)
        self._worker.tool_finished.connect(self._on_tool_finished)
        self._worker.state_changed.connect(self._on_state_changed)
        self._worker.completed.connect(self._on_turn_completed)
        self._worker.failed.connect(self._on_turn_failed)
        self._worker.finished.connect(self._on_chat_worker_finished)
        self._worker.start()

    def _on_chat_worker_finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None

    # -- chat rendering ---------------------------------------------------

    def _append_html(self, markup: str) -> None:
        self.chat_display.append(markup)
        self.chat_display.moveCursor(QTextCursor.End)

    def _append_user_message(self, text: str) -> None:
        safe = html.escape(text).replace("\n", "<br>")
        self._append_html(
            '<div style="background:#151228; border-left:3px solid #C8324A; '
            'padding:10px 12px; margin:8px 0; color:#F5EFE2;">'
            '<span style="color:#F2D79A; font-size:9pt; font-weight:bold;'
            ' letter-spacing:1px;">YOU</span><br>' + safe + "</div>"
        )

    def _append_assistant_note(self, markup: str) -> None:
        self._append_html(
            '<div style="background:#0F0D1D; border-left:3px solid #D4A857; '
            'padding:10px 12px; margin:8px 0; color:#B9B2C7;">'
            '<span style="color:#4FD1C5; font-size:9pt; font-weight:bold;'
            ' letter-spacing:1px;">VIZIER</span><br>' + markup + "</div>"
        )

    def _begin_stream(self) -> None:
        if self._streaming:
            return
        self._append_html(
            '<div style="background:#0F0D1D; border-left:3px solid #D4A857; '
            'padding:10px 12px; margin:8px 0; color:#F5EFE2;">'
            '<span style="color:#4FD1C5; font-size:9pt; font-weight:bold;'
            ' letter-spacing:1px;">VIZIER</span><br>'
        )
        self._streaming = True

    def _on_chunk(self, text: str) -> None:
        self._begin_stream()
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _end_stream(self) -> None:
        if self._streaming:
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText("\n")
            self.chat_display.setTextCursor(cursor)
            self._streaming = False

    def _on_tool_started(self, name: str, args: str) -> None:
        self._end_stream()
        self._set_state("TOOLS")
        safe_name = html.escape(name)
        safe_args = html.escape(args)
        if len(safe_args) > 500:
            safe_args = safe_args[:500] + "…"
        self._append_html(
            '<div style="border:1px solid #2A2440; background:#0C0A16; '
            'padding:7px 11px; margin:5px 0; color:#B9B2C7; '
            'font-family:Consolas,monospace; font-size:9px;">'
            f'<b style="color:#4FD1C5;">▶ {safe_name}</b> '
            f'<span style="color:#D4A857;">{safe_args}</span></div>'
        )

    def _on_tool_finished(self, name: str, result: str, success: bool) -> None:
        self._end_stream()
        colour = "#4FD1C5" if success else "#C8324A"
        label = "✓" if success else "✗"
        safe_result = html.escape(result)
        if len(safe_result) > 2000:
            safe_result = safe_result[:2000] + "\n… (truncated)"
        self._append_html(
            '<div style="border:1px solid #2A2440; background:#0C0A16; '
            'padding:7px 11px; margin:5px 0; color:#B9B2C7; '
            'font-family:Consolas,monospace; font-size:9px;">'
            f'<b style="color:{colour};">{label} {html.escape(name)}</b>'
            f'<pre style="color:#B9B2C7; white-space:pre-wrap;">{safe_result}</pre>'
            "</div>"
        )

    def _on_state_changed(self, state: str) -> None:
        self._set_state(state)

    def _on_turn_completed(self, _result: str) -> None:
        self._end_stream()
        self._set_state("IDLE")
        self.send_button.setEnabled(True)
        self.message_input.setEnabled(True)
        self.message_input.setFocus()
        if self.current_session is not None and self.agent is not None:
            try:
                self.services.session_manager.save(
                    self.current_session.id, self.agent.history
                )
            except Exception:
                log.debug("Session save failed", exc_info=True)

    def _on_turn_failed(self, message: str) -> None:
        self._end_stream()
        self._set_state("ERROR")
        self.send_button.setEnabled(True)
        self.message_input.setEnabled(True)
        self._append_assistant_note(
            f'<span style="color:#C8324A;">Error: {html.escape(message)}</span>'
        )

    def _set_state(self, state: str) -> None:
        """Keep the corner pill and the legacy label in sync."""
        self.status_pill.set_state(state)

    # -- misc -------------------------------------------------------------

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if any(u.toLocalFile().lower().endswith(".gguf") for u in urls):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".gguf"):
                self._load_model(path)
                event.acceptProposedAction()
                return

    def closeEvent(self, event) -> None:
        busy = [
            worker
            for worker in (self._worker, self._loader)
            if worker is not None and worker.isRunning()
        ]
        if busy:
            answer = QMessageBox.question(
                self,
                "Vizier is busy",
                "A model is still loading or a reply is being generated.\n\n"
                "Quit anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            for worker in busy:
                worker.requestInterruption()
                if not worker.wait(3000):
                    log.warning("Force-stopping a background worker during shutdown")
                    worker.terminate()
                    worker.wait(2000)
        if self.agent is not None and self.current_session is not None:
            try:
                self.services.session_manager.save(
                    self.current_session.id, self.agent.history
                )
            except Exception:
                log.debug("Session save on exit failed", exc_info=True)
        with contextlib.suppress(Exception):
            self.config.save()
        with contextlib.suppress(Exception):
            self.services.shutdown()
        super().closeEvent(event)


def main(model_path: str | None = None) -> int:
    """Launch the Vizier desktop application."""
    setup_logging(log_name="vizier.ui")
    log_startup_banner("GUI")
    install_faulthandler()
    install_exception_hook()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Vizier")
    app.setApplicationDisplayName("Vizier — Royal Advisor")
    app.setOrganizationName("Vizier Project")
    from vizier import __version__

    app.setApplicationVersion(__version__)
    setup_theme(app)

    started = time.monotonic()
    splash = create_splash(__version__)
    if splash is not None:
        splash.show()
        app.processEvents()

    window = VizierWindow(config=Config.load(), model_path=model_path)
    app.setWindowIcon(window.windowIcon())

    install_exception_hook(window)
    log.info("Main window prepared")

    if splash is not None:
        # Let the splash breathe long enough to be seen even on fast machines.
        remaining = max(0.0, 1.15 - (time.monotonic() - started))
        QTimer.singleShot(int(remaining * 1000), lambda: reveal_window(window, splash))
    else:
        reveal_window(window, None)
    log.info("Main window shown")

    if os.environ.get("VIZIER_SMOKE_TEST"):
        # Used by the build pipeline to verify the packaged GUI can start.
        log.info("Smoke-test mode: quitting automatically")
        QTimer.singleShot(2500, app.quit)
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
