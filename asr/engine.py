"""Обёртка над faster-whisper.

Ленивая загрузка модели один раз при старте процесса (не на каждый запрос).
Синхронная функция транскрибации, обёрнутая в run_in_executor при вызове из async.

Использование:
    engine = WhisperEngine()
    engine.initialize()          # загрузка модели (при старте бота)
    text = engine.transcribe(path_to_wav)  # синхронный вызов
"""

import logging
import time
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Ошибка транскрибации аудио."""


class WhisperEngine:
    """Обёртка над faster-whisper с ленивой загрузкой модели.

    Модель загружается один раз при вызове initialize() и живёт до конца
    процесса. Транскрибация — синхронная блокирующая операция (CPU-bound),
    должна вызываться через run_in_executor из async-кода.
    """

    def __init__(self) -> None:
        self._model: Optional[object] = None

    def initialize(self) -> None:
        """Загрузить модель faster-whisper.

        Должен быть вызван один раз при старте процесса до первой
        транскрибации. В блоке try регистрируем только класс ошибки,
        без пользовательских данных.
        """
        if self._model is not None:
            logger.warning("Модель уже загружена, повторная инициализация")
            return

        from faster_whisper import WhisperModel

        model_path = str(settings.ASR_MODEL_CACHE_DIR / settings.ASR_MODEL_SIZE)

        logger.info(
            "Загрузка модели faster-whisper: %s (device=%s, compute=%s)",
            settings.ASR_MODEL_SIZE,
            settings.ASR_DEVICE,
            settings.ASR_COMPUTE_TYPE,
        )
        start = time.monotonic()

        try:
            self._model = WhisperModel(
                model_size_or_path=settings.ASR_MODEL_SIZE,
                device=settings.ASR_DEVICE,
                compute_type=settings.ASR_COMPUTE_TYPE,
                download_root=str(settings.ASR_MODEL_CACHE_DIR),
                num_workers=settings.ASR_NUM_PROCESSORS,
            )
        except Exception as exc:
            logger.error(
                "Ошибка загрузки модели: %s", type(exc).__name__
            )
            raise TranscriptionError(
                f"Не удалось загрузить модель ASR: {exc}"
            ) from exc

        elapsed = time.monotonic() - start
        logger.info(
            "Модель загружена за %.2fс: %s",
            elapsed,
            settings.ASR_MODEL_SIZE,
        )

    def transcribe(self, wav_path: Path, language: Optional[str] = None) -> str:
        """Транскрибировать wav-файл в текст (синхронно, CPU-bound).

        Args:
            wav_path: Путь к wav-файлу (16kHz, mono).
            language: Код языка (например "ru", "en") или None для автоопределения.

        Returns:
            str: Распознанный текст.

        Raises:
            TranscriptionError: Если модель не загружена или ошибка распознавания.
        """
        if self._model is None:
            raise TranscriptionError(
                "Модель ASR не загружена. Вызовите initialize() перед transcribe()."
            )

        if not wav_path.exists():
            raise TranscriptionError(f"Файл не найден: {wav_path}")

        start = time.monotonic()
        logger.debug("Начало транскрибации: %s", wav_path.name)

        try:
            segments, info = self._model.transcribe(
                str(wav_path),
                language=language,
                beam_size=5,
                vad_filter=True,    # фильтр тишины
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                ),
            )
        except Exception as exc:
            logger.error("Ошибка транскрибации: %s", type(exc).__name__)
            raise TranscriptionError(
                f"Ошибка распознавания речи: {exc}"
            ) from exc

        # Собираем текст из сегментов
        text_parts: list[str] = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        full_text = " ".join(text_parts)
        elapsed = time.monotonic() - start

        # Логируем только метаданные (GUARDRAILS)
        logger.info(
            "Транскрибация: %.2fс, язык=%s, длит=%.1fс, вер=%.2fс",
            elapsed,
            info.language if hasattr(info, "language") else "?",
            info.duration if hasattr(info, "duration") else 0,
            full_text.count(" ") + 1 if full_text else 0,
        )

        return full_text

    @property
    def is_loaded(self) -> bool:
        """Проверить, загружена ли модель."""
        return self._model is not None


# Единственный экземпляр на всё приложение (singleton)
whisper_engine = WhisperEngine()
