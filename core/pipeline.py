"""Оркестрация пайплайна транскрибации.

Единственное место, где audio/ и asr/ вызываются вместе.
voice_to_text(file_bytes) -> str — единственная точка входа для bot/.
Единственное место с гарантией удаления файлов (try/finally).

Поток:
    bytes (audio) → TempAudioFile (сохранение) → convert_to_wav (ffmpeg) →
    → queue (транскрибация) → TempAudioFile (авто-удаление в finally)
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from audio.converter import convert_to_wav, FFmpegError
from audio.temp_storage import TempAudioFile
from config import settings

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Общая ошибка пайплайна транскрибации."""


class AudioTooLongError(PipelineError):
    """Аудио превышает максимальную длительность."""


class InvalidAudioFormatError(PipelineError):
    """Неподдерживаемый формат аудио."""


async def voice_to_text(
    audio_bytes: bytes,
    file_extension: str,
    user_id: int,
    queue: object,
    language: Optional[str] = None,
) -> str:
    """Транскрибировать аудио в текст.

    Args:
        audio_bytes: Сырые байты аудиофайла.
        file_extension: Расширение файла (".oga", ".mp3", ".wav" и т.п.).
        user_id: Telegram ID пользователя (для логирования).
        queue: Экземпляр TranscriptionQueue для постановки задачи.
        language: Код языка или None для автоопределения.

    Returns:
        str: Распознанный текст.

    Raises:
        InvalidAudioFormatError: Неподдерживаемый формат.
        AudioTooLongError: Аудио длиннее MAX_AUDIO_DURATION_SECONDS.
        PipelineError: Любая другая ошибка пайплайна.
    """
    from audio.converter import SUPPORTED_INPUT_EXTENSIONS

    ext = file_extension.lower()
    if ext not in SUPPORTED_INPUT_EXTENSIONS:
        raise InvalidAudioFormatError(
            f"Формат '{ext}' не поддерживается. "
            f"Допустимые: {', '.join(SUPPORTED_INPUT_EXTENSIONS)}"
        )

    # Сохраняем входящий файл во временную директорию
    async with TempAudioFile(audio_bytes, suffix=ext) as input_tmp:
        assert input_tmp.path is not None

        # Конвертируем в wav (создаём второй временный файл)
        wav_path = input_tmp.path.with_suffix(".wav")
        try:
            await convert_to_wav(input_tmp.path, wav_path)
        except FFmpegError as exc:
            # Если wav всё же создался (частично) — удаляем
            _try_remove(wav_path)
            raise PipelineError(str(exc)) from exc

        # Проверяем длительность
        duration = _get_duration(wav_path)
        if duration > settings.MAX_AUDIO_DURATION_SECONDS:
            _try_remove(wav_path)
            raise AudioTooLongError(
                f"Аудио длительностью {duration:.0f}с превышает лимит "
                f"в {settings.MAX_AUDIO_DURATION_SECONDS}с"
            )

        # Создаём задачу и отправляем в очередь
        from asr.queue_worker import TranscriptionTask

        task = TranscriptionTask(
            user_id=user_id,
            wav_path=wav_path,
            language=language,
        )
        await queue.put(task)

        try:
            text = await queue.wait_result(task)
        except Exception as exc:
            raise PipelineError(str(exc)) from exc
        finally:
            # Гарантированно удаляем wav после обработки
            _try_remove(wav_path)

    # input_tmp удалён автоматически при выходе из async with
    return text


def _try_remove(path: Path) -> None:
    """Безопасно удалить файл, игнорируя ошибки."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


async def _get_duration(wav_path: Path) -> float:
    """Получить длительность wav-файла.

    Использует синхронную ffprobe через run_in_executor.
    """
    from audio.converter import _get_duration_sync

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_duration_sync, wav_path)
