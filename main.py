"""Точка входа в приложение.

Инициализация бота, загрузка ASR-модели, запуск очереди и polling.
"""
#!/usr/bin/env python3

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import settings

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Настройка логирования — только метаданные, без содержимого."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def main() -> None:
    """Основная функция: инициализация и запуск."""
    setup_logging()
    logger.info("Запуск VTTFreeBot...")

    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан. Укажите в .env")
        return

    # Инициализация бота
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Регистрация health-check
    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        await message.answer(
            "👋 Привет! Я VTTFreeBot — бот для расшифровки голосовых сообщений.\n\n"
            "Отправь мне голосовое сообщение или аудиофайл (mp3, ogg, wav)\n"
            "— я пришлю текст расшифровки.\n\n"
            "⚙️ Бот работает полностью локально, данные не сохраняются."
        )

    # Загрузка ASR-модели
    from asr.engine import TranscriptionError, whisper_engine

    logger.info("Загрузка ASR-модели: %s...", settings.ASR_MODEL_SIZE)
    try:
        whisper_engine.initialize()
    except TranscriptionError as exc:
        logger.error("Ошибка загрузки модели: %s", exc)
        await bot.session.close()
        return

    # Запуск очереди транскрибации
    from asr.queue_worker import TranscriptionQueue

    queue = TranscriptionQueue(whisper_engine)
    await queue.start()

    # Подключаем хендлеры и middleware
    from bot.handlers import router as handlers_router

    # Передаём очередь в хендлеры (через модульную переменную)
    import bot.handlers
    bot.handlers.transcription_queue = queue

    dp.include_router(handlers_router)

    from bot.middlewares import RateLimitMiddleware

    dp.message.middleware(RateLimitMiddleware())

    # Запуск polling
    try:
        logger.info("Бот запущен и готов к работе")
        await dp.start_polling(bot)
    except Exception as exc:
        logger.error("Критическая ошибка: %s", type(exc).__name__)
    finally:
        await queue.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

