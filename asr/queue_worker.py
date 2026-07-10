"""Последовательная обработка задач транскрибации.

Единственный воркер, читающий задачи из asyncio.Queue.
Обрабатывает их строго последовательно — параллельный инференс
на 1GB RAM приведёт к OOM

Каждый пользователь получает:
1. Мгновенное подтверждение "принято, обрабатываю"
2. Результат отдельным сообщением по готовности
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionTask:
    """Задача на транскрибацию.

    Создаётся при получении аудио от пользователя и помещается в очередь.

    Args:
        user_id: Telegram ID пользователя.
        wav_path: Путь к wav-файлу (16kHz, mono) для распознавания.
        language: Код языка (например "ru") или None для автоопределения.

    Attributes:
        task_id: Уникальный идентификатор задачи (uuid4).
        created_at: Время создания задачи (timestamp).
        completed: Флаг завершения.
        result: Текст расшифровки (после завершения).
        error: Сообщение об ошибке (если была).
    """
    user_id: int
    wav_path: Path
    language: Optional[str] = None

    task_id: str = field(default_factory=lambda: uuid.uuid4().hex, init=False)
    created_at: float = field(default_factory=time.monotonic, init=False)
    completed: bool = False
    result: Optional[str] = None
    error: Optional[str] = None


class TranscriptionQueue:
    """Очередь задач транскрибации с одним воркером.

    Использование:
        queue = TranscriptionQueue(whisper_engine)
        await queue.start()              # запустить воркер
        task = TranscriptionTask(...)
        await queue.put(task)            # добавить задачу
        result = await queue.wait_result(task)  # дождаться результата
        await queue.stop()               # остановить при завершении
    """

    def __init__(self, whisper_engine: object) -> None:
        self._engine = whisper_engine
        self._queue: asyncio.Queue[TranscriptionTask] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._running = False

    async def start(self) -> None:
        """Запустить воркер очереди."""
        if self._running:
            logger.warning("Очередь уже запущена")
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Очередь обработки запущена")

    async def stop(self) -> None:
        """Остановить воркер очереди."""
        self._running = False
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("Очередь обработки остановлена")

    async def put(self, task: TranscriptionTask) -> None:
        """Добавить задачу в очередь."""
        await self._queue.put(task)
        logger.debug(
            "Задача добавлена в очередь: user_id=%d, файл=%s",
            task.user_id,
            task.wav_path.name,
        )

    async def wait_result(self, task: TranscriptionTask, timeout: Optional[float] = None) -> str:
        """Дождаться результата выполнения задачи.

        Args:
            task: Задача, ранее добавленная в очередь.
            timeout: Таймаут ожидания в секундах (по умолчанию QUEUE_TIMEOUT_SECONDS).

        Returns:
            str: Текст расшифровки.

        Raises:
            asyncio.TimeoutError: Если задача не выполнена за отведённое время.
            TranscriptionError: Если задача завершилась с ошибкой.
        """
        timeout = timeout or settings.QUEUE_TIMEOUT_SECONDS
        deadline = time.monotonic() + timeout

        while not task.completed:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError(
                    f"Превышено время ожидания транскрибации ({timeout}с)"
                )
            await asyncio.sleep(0.1)

        if task.error:
            from asr.engine import TranscriptionError
            raise TranscriptionError(task.error)

        assert task.result is not None
        return task.result

    async def _worker_loop(self) -> None:
        """Основной цикл воркера — последовательно обрабатывает задачи."""
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            await self._process_task(task)
            self._queue.task_done()

    async def _process_task(self, task: TranscriptionTask) -> None:
        """Обработать одну задачу (вызов ASR через run_in_executor)."""
        logger.debug(
            "Обработка задачи %s (user_id=%d)", task.task_id, task.user_id
        )
        start = time.monotonic()

        try:
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(
                None,
                self._engine.transcribe,
                task.wav_path,
                task.language,
            )
            task.result = text
            task.completed = True
            elapsed = time.monotonic() - start
            logger.info(
                "Задача %s выполнена за %.2fс (user_id=%d)",
                task.task_id, elapsed, task.user_id,
            )
        except Exception as exc:
            task.error = str(exc)
            task.completed = True
            logger.warning(
                "Задача %s ошибка: %s (user_id=%d)",
                task.task_id, type(exc).__name__, task.user_id,
            )
