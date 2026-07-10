"""Инициализация и запуск Telegram-бота (aiogram, polling).

Вызывается из main.py при RUN_MODE=telegram.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import settings
from asr.engine import whisper_engine, TranscriptionError
from asr.queue_worker import TranscriptionQueue
from interfaces.telegram.handlers import router as handlers_router, transcription_queue
from interfaces.telegram.middlewares import RateLimitMiddleware

logger = logging.getLogger(__name__)


async def run() -> None:
    """Запустить Telegram-бота (aiogram polling)."""
    logger.info("Режим: Telegram")

    tg_bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    queue: TranscriptionQueue | None = None

    # Регистрация health-check
    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        await message.answer(
            "👋 Привет! Я VTTFreeBot — бот для расшифровки голосовых сообщений.\n\n"
            "Отправь мне голосовое сообщение или аудиофайл (mp3, ogg, wav)\n"
            "— я пришлю текст расшифровки.\n\n"
            "⚙️ Бот работает полностью локально, данные не сохраняются."
        )

    # Загрузка модели
    logger.info("Загрузка ASR-модели: %s...", settings.ASR_MODEL_SIZE)
    try:
        whisper_engine.initialize()
    except TranscriptionError as exc:
        logger.error("Ошибка загрузки модели: %s", exc)
        await tg_bot.session.close()
        return

    # Очередь
    queue = TranscriptionQueue(whisper_engine)
    await queue.start()

    # Подключаем хендлеры и middleware
    import interfaces.telegram.handlers as tg_handlers
    tg_handlers.transcription_queue = queue

    dp.include_router(handlers_router)
    dp.message.middleware(RateLimitMiddleware())

    try:
        logger.info("Telegram-бот запущен")
        await dp.start_polling(tg_bot)
    except Exception as exc:
        logger.error("Критическая ошибка: %s", type(exc).__name__)
    finally:
        if queue is not None:
            await queue.stop()
        await tg_bot.session.close()
