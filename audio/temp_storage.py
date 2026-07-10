"""Context manager для temp-файлов (создание / гарантированное удаление).

Единственное место в проекте, где создаются и удаляются временные файлы.
Все временные файлы проходят через этот модуль — никаких разрозненных os.remove().

Использование:
    async with TempAudioFile(original_bytes, suffix=".oga") as tmp:
        # tmp.path — путь к файлу на диске
        result = process(tmp.path)
    # файл гарантированно удалён после выхода из контекста
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


class TempAudioFile:
    """Безопасный временный аудиофайл с гарантированным удалением.

    Создаёт файл с уникальным именем (uuid4) в TEMP_DIR из конфигурации.
    Удаляет файл в блоке finally при выходе из async with.
    Единственное место в проекте, где создаются временные файлы.

    Args:
        data: Сырые байты исходного аудио.
        suffix: Расширение файла (например .oga, .mp3) — опционально.

    Attributes:
        path: Полный путь к созданному временному файлу на диске.
    """

    def __init__(self, data: bytes, suffix: str = "") -> None:
        self._data = data
        self._suffix = suffix
        self.path: Optional[Path] = None

    async def __aenter__(self) -> "TempAudioFile":
        """Создать временный файл с уникальным именем и записать данные."""
        loop = asyncio.get_running_loop()
        self.path = await loop.run_in_executor(None, self._create_file)
        logger.debug("Создан временный файл (размер: %d байт)", len(self._data))
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Гарантированно удалить временный файл, даже при исключении."""
        if self.path is not None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._remove_file)
            self.path = None

    def _create_file(self) -> Path:
        """Создать файл в temp-директории и записать данные (синхронно)."""
        temp_dir = Path(settings.TEMP_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{uuid.uuid4().hex}{self._suffix}"
        filepath = temp_dir / unique_name

        with open(filepath, "wb") as f:
            f.write(self._data)

        return filepath

    def _remove_file(self) -> None:
        """Удалить файл (синхронно). Ошибки если файла нет — игнорируются."""
        if self.path is None:
            return
        try:
            os.remove(self.path)
            logger.debug("Временный файл удалён")
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("Не удалось удалить временный файл: %s", exc)
