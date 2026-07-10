"""Хендлеры Telegram-бота.

Только приём апдейтов и вызов core-пайплайна.
Не имеет доступа к деталям ASR и к путям временных файлов напрямую.
"""

import asyncio
import logging
import time

from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.types import Document, Message, Voice

from core.pipeline import (
    AudioTooLongError,
    InvalidAudioFormatError,
    PipelineError,
    voice_to_text,
)
from config import settings

logger = logging.getLogger(__name__)

router = Router()

# Ссылка на очередь — устанавливается из main.py после инициализации
transcription_queue: object = None


@router.message(lambda msg: msg.voice is not None)
async def handle_voice(message: Message) -> None:
    """Обработка голосового сообщения."""
    voice: Voice = message.voice  # type: ignore[union-attr]
    user_id = message.from_user.id if message.from_user else 0

    logger.info("Голосовое сообщение: user_id=%d, длит=%.1fс", user_id, voice.duration)

    # Скачиваем файл
    file_info = await message.bot.get_file(voice.file_id)
    file_bytes = await message.bot.download_file(file_info.file_path)
    audio_data = file_bytes.read()

    await message.bot.send_chat_action(
        chat_id=message.chat.id, action=ChatAction.TYPING
    )

    await _process_and_respond(
        message=message,
        audio_bytes=audio_data,
        file_extension=".oga",  # Telegram voice всегда ogg/opus
        user_id=user_id,
    )


@router.message(lambda msg: msg.document is not None)
async def handle_document(message: Message) -> None:
    """Обработка аудиофайла, присланного как документ."""
    doc: Document = message.document  # type: ignore[union-attr]
    user_id = message.from_user.id if message.from_user else 0

    # Проверяем размер файла до скачивания
    if doc.file_size and doc.file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(
            f"❌ Файл слишком большой. Максимум {settings.MAX_FILE_SIZE_MB} МБ."
        )
        logger.info(
            "Файл отклонён: user_id=%d, размер=%d, лимит=%dMB",
            user_id, doc.file_size, settings.MAX_FILE_SIZE_MB,
        )
        return

    ext = _get_extension(doc.file_name or "")
    if not ext:
        await message.answer("❌ Не удалось определить формат файла.")
        return

    # Скачиваем
    file_info = await message.bot.get_file(doc.file_id)
    file_bytes = await message.bot.download_file(file_info.file_path)
    audio_data = file_bytes.read()

    await message.bot.send_chat_action(
        chat_id=message.chat.id, action=ChatAction.TYPING
    )

    await _process_and_respond(
        message=message,
        audio_bytes=audio_data,
        file_extension=ext,
        user_id=user_id,
    )


async def _process_and_respond(
    message: Message,
    audio_bytes: bytes,
    file_extension: str,
    user_id: int,
) -> None:
    """Общий пайплайн обработки: транскрибация → ответ.

    Логирует только метаданные.
    """
    start = time.monotonic()
    queue = transcription_queue

    try:
        text = await voice_to_text(
            audio_bytes=audio_bytes,
            file_extension=file_extension,
            user_id=user_id,
            queue=queue,
        )
    except InvalidAudioFormatError as exc:
        await message.answer(f"❌ {exc}")
        return
    except AudioTooLongError as exc:
        await message.answer(f"❌ {exc}")
        return
    except PipelineError as exc:
        await message.answer(f"❌ Ошибка обработки: {exc}")
        logger.warning("PipelineError: user_id=%d, err=%s", user_id, type(exc).__name__)
        return
    except asyncio.TimeoutError:
        await message.answer(
            "⏱️ Превышено время обработки. Попробуйте более короткое аудио."
        )
        logger.warning("Timeout: user_id=%d", user_id)
        return

    elapsed = time.monotonic() - start
    logger.info(
        "Расшифровка отправлена: user_id=%d, время=%.1fс, длина=%d символов",
        user_id, elapsed, len(text),
    )

    await message.answer(
        f"📝 Расшифровка:\n\n{text}",
        disable_web_page_preview=True,
    )


def _get_extension(filename: str) -> str:
    """Извлечь расширение файла из имени."""
    if "." not in filename:
        return ""
    ext = filename.rsplit(".", 1)[-1].lower().strip()
    if not ext:
        return ""
    return f".{ext}"

