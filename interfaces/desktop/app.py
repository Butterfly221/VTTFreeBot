"""Логика десктопного приложения.

Связывает core.pipeline с PyQt6 UI.
Для работы с asyncio использует единый event loop на всё приложение.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from audio.converter import SUPPORTED_INPUT_EXTENSIONS
from asr.engine import whisper_engine
from asr.queue_worker import TranscriptionQueue
from config import settings
from core.pipeline import (
    AudioTooLongError,
    InvalidAudioFormatError,
    PipelineError,
    voice_to_text,
)

logger = logging.getLogger(__name__)

# Единый event loop для десктопного приложения
_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_loop() -> asyncio.AbstractEventLoop:
    """Получить или создать event loop."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


class DesktopTranscriber:
    """Основной класс-транскрайбер для десктопного приложения.

    Инициализирует модель при создании и предоставляет
    метод transcribe_file() для расшифровки.
    """

    def __init__(self) -> None:
        self._queue: Optional[TranscriptionQueue] = None
        self._initialized = False

    def initialize(self) -> None:
        """Загрузить модель и запустить очередь (синхронно)."""
        if self._initialized:
            return

        logger.info("Инициализация десктопного режима...")
        loop = _get_loop()

        async def _init() -> None:
            whisper_engine.initialize()
            self._queue = TranscriptionQueue(whisper_engine)
            await self._queue.start()

        loop.run_until_complete(_init())
        self._initialized = True
        logger.info("Инициализация завершена")

    def transcribe_file(
        self,
        file_path: str,
        callback_progress: Optional[callable] = None,
    ) -> str:
        """Транскрибировать аудиофайл в текст (синхронный вызов).

        Args:
            file_path: Путь к аудиофайлу.
            callback_progress: Функция для обновления прогресса в UI.

        Returns:
            str: Распознанный текст.

        Raises:
            PipelineError: Ошибка обработки.
            AudioTooLongError: Аудио слишком длинное.
            InvalidAudioFormatError: Неподдерживаемый формат.
        """
        if not self._initialized:
            raise RuntimeError("Вызовите initialize() перед transcribe_file()")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {path}")

        ext = _get_extension(path.name)
        if not ext or ext not in SUPPORTED_INPUT_EXTENSIONS:
            raise InvalidAudioFormatError(
                f"Формат '{ext}' не поддерживается. "
                f"Допустимые: {', '.join(SUPPORTED_INPUT_EXTENSIONS)}"
            )

        if callback_progress:
            callback_progress("Чтение файла...")

        with open(path, "rb") as f:
            audio_bytes = f.read()

        if callback_progress:
            callback_progress("Конвертация и распознавание...")

        start = time.monotonic()
        loop = _get_loop()

        async def _transcribe() -> str:
            return await voice_to_text(
                audio_bytes=audio_bytes,
                file_extension=ext,
                user_id=0,
                queue=self._queue,
            )

        try:
            text = loop.run_until_complete(_transcribe())
            elapsed = time.monotonic() - start
            logger.info(
                "Десктоп: расшифровка завершена за %.1fс, длина=%d символов",
                elapsed, len(text),
            )
            return text
        except asyncio.TimeoutError:
            raise PipelineError("Превышено время обработки.")


def _get_extension(filename: str) -> str:
    """Извлечь расширение файла."""
    if "." not in filename:
        return ""
    ext = filename.rsplit(".", 1)[-1].lower().strip()
    if not ext:
        return ""
    return f".{ext}"
