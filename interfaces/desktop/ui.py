"""PyQt6 UI для десктопного приложения VTTFreeBot.

Главное окно: drag'n'drop, выбор файла, прогресс, результат.
"""

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.pipeline import AudioTooLongError, InvalidAudioFormatError, PipelineError
from interfaces.desktop.app import DesktopTranscriber

logger = logging.getLogger(__name__)

# Стили
STYLES = """
QMainWindow {
    background-color: #1e1e2e;
}
QLabel {
    color: #cdd6f4;
    font-size: 14px;
}
QTextEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px;
    font-size: 14px;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #74c7ec;
}
QPushButton:pressed {
    background-color: #89dceb;
}
QProgressBar {
    border: 1px solid #45475a;
    border-radius: 6px;
    text-align: center;
    color: #cdd6f4;
    background-color: #313244;
}
QProgressBar::chunk {
    background-color: #a6e3a1;
    border-radius: 6px;
}
#dropArea {
    border: 2px dashed #585b70;
    border-radius: 12px;
    padding: 30px;
    color: #6c7086;
    font-size: 16px;
}
#dropAreaDrag {
    border: 2px dashed #89b4fa;
    border-radius: 12px;
    padding: 30px;
    color: #89b4fa;
    font-size: 16px;
    background-color: rgba(137, 180, 250, 0.1);
}
"""


class DropArea(QLabel):
    """Область для перетаскивания файлов."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(
            "🎵 Перетащите аудиофайл сюда\n"
            "или нажмите кнопку «Выбрать файл»\n\n"
            "Поддерживаемые форматы:\n"
            "mp3, ogg, wav, flac, m4a, aac, webm"
        )
        self.setMinimumHeight(180)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Обработка входа перетаскиваемого объекта."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setObjectName("dropAreaDrag")
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event) -> None:
        """Обработка ухода перетаскиваемого объекта."""
        self.setObjectName("dropArea")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:
        """Обработка сброса файла."""
        self.setObjectName("dropArea")
        self.style().unpolish(self)
        self.style().polish(self)

        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.parent().parent().process_file(file_path)  # type: ignore


class MainWindow(QMainWindow):
    """Главное окно десктопного приложения."""

    def __init__(self, transcriber: DesktopTranscriber) -> None:
        super().__init__()
        self._transcriber = transcriber
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Создать элементы интерфейса."""
        self.setWindowTitle("VTTFreeBot — Расшифровка аудио")
        self.setMinimumSize(600, 500)
        self.setAcceptDrops(True)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        title = QLabel("🎙️ VTTFreeBot")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Перетащите аудиофайл или выберите его через кнопку"
        )
        subtitle.setStyleSheet("color: #6c7086; font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(subtitle)

        # Область drag'n'drop
        self._drop_area = DropArea()
        layout.addWidget(self._drop_area)

        # Кнопки
        btn_layout = QHBoxLayout()
        select_btn = QPushButton("📁 Выбрать файл")
        select_btn.clicked.connect(self._on_select_file)
        btn_layout.addWidget(select_btn)

        clear_btn = QPushButton("🗑️ Очистить")
        clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(clear_btn)
        layout.addLayout(btn_layout)

        # Прогресс
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #a6e3a1; font-size: 13px;")
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # Результат
        result_label = QLabel("📝 Результат:")
        layout.addWidget(result_label)

        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setMinimumHeight(200)
        layout.addWidget(self._result_text)

    def process_file(self, file_path: str) -> None:
        """Обработать выбранный файл.

        Args:
            file_path: Путь к файлу.
        """
        path = Path(file_path)
        if not path.exists():
            self._show_error(f"Файл не найден: {path}")
            return

        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status_label.setVisible(True)
        self._result_text.clear()

        def update_status(msg: str) -> None:
            self._status_label.setText(msg)

        update_status("⏳ Идёт расшифровка...")
        self._progress.setRange(0, 0)  # indeterminate
        QApplication.processEvents()

        try:
            text = self._transcriber.transcribe_file(
                file_path, callback_progress=update_status
            )

            self._progress.setRange(0, 100)
            self._progress.setValue(100)
            self._status_label.setText("✅ Готово!")
            self._result_text.setText(text)

        except InvalidAudioFormatError as exc:
            self._show_error(str(exc))
        except AudioTooLongError as exc:
            self._show_error(str(exc))
        except PipelineError as exc:
            self._show_error(f"Ошибка обработки: {exc}")
        except FileNotFoundError as exc:
            self._show_error(str(exc))
        except Exception as exc:
            logger.error("Неизвестная ошибка: %s", type(exc).__name__)
            self._show_error(f"Неизвестная ошибка: {exc}")
        finally:
            QApplication.processEvents()

    def _show_error(self, message: str) -> None:
        """Показать ошибку в UI."""
        self._progress.setVisible(False)
        self._status_label.setVisible(False)
        self._result_text.setHtml(
            f'<p style="color:#f38ba8;">❌ {message}</p>'
        )

    def _on_select_file(self) -> None:
        """Обработка кнопки «Выбрать файл»."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите аудиофайл",
            "",
            "Аудиофайлы (*.mp3 *.ogg *.oga *.opus *.wav *.flac *.m4a *.aac *.webm);;"
            "Все файлы (*)",
        )
        if file_path:
            self.process_file(file_path)

    def _on_clear(self) -> None:
        """Очистить результат."""
        self._result_text.clear()
        self._progress.setVisible(False)
        self._status_label.setVisible(False)
