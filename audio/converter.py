"""ffmpeg-обёртка: любой вход → 16kHz mono wav.

Не знает о Telegram и о модели — чистая работа с файлами.
Принимает путь к любому аудиофайлу, возвращает путь к wav-файлу.
"""


import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Разрешённые форматы на входе (Telegram voice = ogg/opus, документы = mp3 и др.)
SUPPORTED_INPUT_EXTENSIONS: tuple[str, ...] = (
    ".oga", ".ogg", ".opus",
    ".mp3", ".mp4", ".m4a", ".aac",
    ".wav", ".flac", ".webm",
)


class FFmpegError(Exception):
    """Ошибка конвертации аудио через ffmpeg."""


def _convert_sync(input_path: Path, output_path: Path) -> None:
    """Синхронный вызов ffmpeg для конвертации в 16kHz mono wav.

    Args:
        input_path: Путь к исходному аудиофайлу.
        output_path: Путь для сохранения wav-файла.

    Raises:
        FFmpegError: Если ffmpeg не найден, вернул ошибку или файл не создан.
    """
    cmd = [
        "ffmpeg",
        "-y",                # перезаписать выходной файл, если существует
        "-i", str(input_path),  # входной файл
        "-ar", str(settings.WAV_SAMPLE_RATE),  # частота дискретизации
        "-ac", "1",          # mono
        "-f", "wav",         # формат wav
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=settings.QUEUE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        raise FFmpegError(
            "ffmpeg не найден. Убедитесь, что ffmpeg установлен и доступен в PATH."
        ) from None
    except subprocess.TimeoutExpired:
        raise FFmpegError(
            f"Конвертация аудио превысила таймаут {settings.QUEUE_TIMEOUT_SECONDS}с"
        ) from None

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[:500]
        logger.warning(
            "FFmpeg ошибка (код %d): %s", result.returncode, stderr
        )
        raise FFmpegError(
            f"Ошибка ffmpeg: код {result.returncode}. "
            "Возможно, файл повреждён или имеет неподдерживаемый формат."
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise FFmpegError("ffmpeg не создал выходной wav-файл.")


async def convert_to_wav(input_path: Path, output_path: Path) -> Path:
    """Конвертировать аудиофайл в 16kHz mono wav.

    Args:
        input_path: Путь к исходному файлу (любой поддерживаемый формат).
        output_path: Путь для сохранения wav-файла.

    Returns:
        Path: Путь к созданному wav-файлу (тот же output_path).

    Raises:
        FFmpegError: Если конвертация не удалась.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _convert_sync, input_path, output_path)

    duration_sec = _get_duration_sync(output_path)
    logger.info(
        "Конвертация завершена: %s → %s (%.1fс, %d Гц, mono)",
        input_path.name, output_path.name, duration_sec, settings.WAV_SAMPLE_RATE,
    )
    return output_path


def _get_duration_sync(wav_path: Path) -> float:
    """Получить длительность wav-файла в секундах через ffprobe.

    Args:
        wav_path: Путь к wav-файлу.

    Returns:
        float: Длительность в секундах или 0.0, если не удалось определить.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(wav_path),
            ],
            capture_output=True,
            timeout=10,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return 0.0