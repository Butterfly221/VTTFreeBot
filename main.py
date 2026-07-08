"""Точка входа в приложение.

Инициализация бота, регистрация хендлеров и запуск polling.
На этом этапе — только health-check хендлер без ASR-логики.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import settings

logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Health-check: просто отвечаем, что бот жив."""
    await message.answer(
        "👋 Привет! Я бот для расшифровки голосовых сообщений.\n"
        "Отправь мне голосовое сообщение или аудиофайл — я верну текст.\n\n"
        "⚙️ Режим обслуживания — бот запущен, ASR пока не подключён."
    )


async def main() -> None:
    """Основная функция: запуск polling."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Запуск бота...")

    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан. Укажите в .env")
        return

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
