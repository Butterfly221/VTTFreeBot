"""Точка входа для десктопного приложения.

Запускает PyQt6 окно с инициализацией ASR-модели.
Вызывается из main.py при RUN_MODE=desktop.
"""

import logging
import sys

from PyQt6.QtWidgets import QApplication

from interfaces.desktop.app import DesktopTranscriber
from interfaces.desktop.ui import MainWindow

logger = logging.getLogger(__name__)


def run() -> None:
    """Запустить десктопное приложение (синхронный вызов)."""
    try:
        logger.info("Режим: Desktop")

        # Инициализация ASR-модели
        transcriber = DesktopTranscriber()
        transcriber.initialize()

        # Запуск PyQt6
        app = QApplication(sys.argv)
        app.setStyleSheet("""""")  # стили в ui.py
        window = MainWindow(transcriber)
        window.show()

        logger.info("Десктопное приложение запущено")
        sys.exit(app.exec())

    except Exception as exc:
        logger.error("Критическая ошибка: %s", type(exc).__name__)
        sys.exit(1)
