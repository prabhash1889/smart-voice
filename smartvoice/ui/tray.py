from __future__ import annotations

import logging
import threading

from smartvoice.app import SmartVoiceApp
from smartvoice.audio.recorder import list_input_devices
from smartvoice.storage.config_store import ConfigStore
from smartvoice.storage.history_store import HistoryStore


def run_tray(app_model: SmartVoiceApp) -> int:
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QDialog,
            QFormLayout,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QMenu,
            QMessageBox,
            QPushButton,
            QSystemTrayIcon,
            QTextEdit,
            QVBoxLayout,
        )
        from PySide6.QtGui import QAction, QIcon
    except ModuleNotFoundError as exc:
        raise RuntimeError("PySide6 is required for tray mode. Install with: python -m pip install PySide6") from exc

    qt_app = QApplication.instance() or QApplication([])
    qt_app.setQuitOnLastWindowClosed(False)

    tray = QSystemTrayIcon(QIcon(), qt_app)
    tray.setToolTip("SmartVoice")

    menu = QMenu()
    status_action = QAction("Status: loading model")
    status_action.setEnabled(False)
    menu.addAction(status_action)

    mode_menu = menu.addMenu("Mode")
    mode_actions: list[QAction] = []
    for mode in app_model.config["modes"]["available"]:
        action = QAction(mode, checkable=True)
        action.setChecked(mode == app_model.workflow.mode)

        def set_mode(checked=False, selected_mode=mode):
            del checked
            app_model.workflow.set_mode(selected_mode)
            for item in mode_actions:
                item.setChecked(item.text() == selected_mode)
            status_action.setText(f"Status: {format_state()} ({selected_mode})")

        action.triggered.connect(set_mode)
        mode_actions.append(action)
        mode_menu.addAction(action)

    def show_history() -> None:
        dialog = QDialog()
        dialog.setWindowTitle("SmartVoice History")
        layout = QVBoxLayout(dialog)
        rows = HistoryStore(limit=app_model.config["privacy"]["history_limit"]).recent(30)
        list_widget = QListWidget()
        for row in rows:
            status = "error" if row["error"] else "ok"
            preview = (row["final_text"] or row["error"] or "").replace("\n", " ")[:90]
            list_widget.addItem(f"{row['created_at']} [{status}] {row['mode']} - {preview}")
        detail = QTextEdit()
        detail.setReadOnly(True)

        def selected_row() -> dict | None:
            index = list_widget.currentRow()
            if index < 0 or index >= len(rows):
                return None
            return rows[index]

        def update_detail() -> None:
            row = selected_row()
            if not row:
                detail.setPlainText("")
                return
            detail.setPlainText(row["final_text"] or row["error"] or "")

        def copy_selected() -> None:
            row = selected_row()
            if not row or not row.get("final_text"):
                return
            import pyperclip

            pyperclip.copy(row["final_text"])

        def retry_selected() -> None:
            row = selected_row()
            if row and row.get("final_text"):
                app_model.workflow.injector.inject(row["final_text"])

        list_widget.currentRowChanged.connect(lambda _index: update_detail())
        if rows:
            list_widget.setCurrentRow(0)
        buttons = QHBoxLayout()
        copy_button = QPushButton("Copy")
        retry_button = QPushButton("Retry Paste")
        copy_button.clicked.connect(copy_selected)
        retry_button.clicked.connect(retry_selected)
        buttons.addWidget(copy_button)
        buttons.addWidget(retry_button)
        layout.addWidget(list_widget)
        layout.addWidget(detail)
        layout.addLayout(buttons)
        dialog.resize(720, 420)
        dialog.exec()

    def show_settings() -> None:
        config_store = ConfigStore()
        config = config_store.load()
        dialog = QDialog()
        dialog.setWindowTitle("SmartVoice Settings")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        mic_combo = QComboBox()
        devices = list_input_devices()
        for device in devices:
            mic_combo.addItem(f"{device['id']}: {device['name']}", device["id"])
        current_device = config["audio"].get("input_device_id")
        for index, device in enumerate(devices):
            if device["id"] == current_device:
                mic_combo.setCurrentIndex(index)

        model_combo = QComboBox()
        for model in ["base.en", "small.en", "medium.en"]:
            model_combo.addItem(model)
        model_combo.setCurrentText(config["transcription"].get("model", "small.en"))

        engine_combo = QComboBox()
        for engine in ["faster_whisper", "openai"]:
            engine_combo.addItem(engine)
        engine_combo.setCurrentText(config["transcription"].get("engine", "faster_whisper"))

        openai_model_combo = QComboBox()
        for model in ["gpt-4o-transcribe", "gpt-4o-mini-transcribe"]:
            openai_model_combo.addItem(model)
        openai_model_combo.setCurrentText(config["transcription"].get("openai_model", "gpt-4o-transcribe"))

        vad_checkbox = QCheckBox("Use VAD")
        vad_checkbox.setChecked(bool(config["audio"].get("vad_enabled", True)))
        cloud_checkbox = QCheckBox("Allow cloud transcription")
        cloud_checkbox.setChecked(bool(config["privacy"].get("allow_cloud_transcription", False)))

        form.addRow("Microphone", mic_combo)
        form.addRow("Engine", engine_combo)
        form.addRow("Model", model_combo)
        form.addRow("OpenAI model", openai_model_combo)
        form.addRow("VAD", vad_checkbox)
        form.addRow("Privacy", cloud_checkbox)
        form.addRow("Mode", QLabel(app_model.workflow.mode))
        form.addRow("Hotkey", QLabel(config["hotkeys"]["push_to_talk"]))
        layout.addLayout(form)

        save_button = QPushButton("Save")

        def save_settings() -> None:
            config_store.update(
                {
                    "audio": {
                        "input_device_id": mic_combo.currentData(),
                        "vad_enabled": vad_checkbox.isChecked(),
                    },
                    "privacy": {"allow_cloud_transcription": cloud_checkbox.isChecked()},
                    "transcription": {
                        "engine": engine_combo.currentText(),
                        "model": model_combo.currentText(),
                        "openai_model": openai_model_combo.currentText(),
                    },
                }
            )
            QMessageBox.information(dialog, "SmartVoice", "Settings saved. Restart SmartVoice to apply them.")
            dialog.accept()

        save_button.clicked.connect(save_settings)
        layout.addWidget(save_button)
        dialog.exec()

    menu.addAction("History", show_history)
    menu.addAction("Settings", show_settings)
    menu.addSeparator()
    menu.addAction("Retry last paste", app_model.workflow.retry_injection)
    menu.addAction("Quit", qt_app.quit)
    tray.setContextMenu(menu)
    tray.show()

    def format_state() -> str:
        states = {
            "idle": "ready",
            "loading_model": "loading",
            "recording": "recording",
            "transcribing": "transcribing",
            "processing": "processing",
            "injecting": "pasting",
        }
        return states.get(app_model.workflow.state, app_model.workflow.state)

    def warmup() -> None:
        try:
            app_model.warmup()
            QTimer.singleShot(0, lambda: status_action.setText(f"Status: ready ({app_model.workflow.mode})"))
        except Exception as exc:
            logging.exception("Failed to warm up SmartVoice.")
            message = str(exc)
            QTimer.singleShot(0, lambda: status_action.setText(f"Status: error: {message}"))

    def start_hotkeys() -> None:
        app_model.hotkeys.run_forever()

    threading.Thread(target=warmup, daemon=True).start()
    threading.Thread(target=start_hotkeys, daemon=True).start()

    timer = QTimer()
    timer.timeout.connect(lambda: status_action.setText(f"Status: {format_state()} ({app_model.workflow.mode})"))
    timer.start(500)
    return qt_app.exec()
