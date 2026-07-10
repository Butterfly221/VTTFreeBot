"""
Точка входа в приложение.

Диспетчер режимов: по RUN_MODE из .env запускает нужный интерфейс.
"""
import asyncio
import logging

from config import settings

def setup_logging() -> None:
    """Настройка логирования — только метаданные, без содержимого."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    """Диспетчер: выбор режима по RUN_MODE."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Запуск VTTFreeBot в режиме: %s", settings.RUN_MODE)

    if settings.RUN_MODE == "telegram":
        if not settings.BOT_TOKEN:
            logger.error("BOT_TOKEN не задан для режима telegram")
        return
        from interfaces.telegram.bot import run
        asyncio.run(run())

    elif settings.RUN_MODE == "vk":
        if not settings.VK_TOKEN:
            logger.error("VK_TOKEN не задан для режима vk")
        return
        from interfaces.vk.bot import run
        asyncio.run(run())

    elif settings.RUN_MODE == "desktop":
        from interfaces.desktop.main import run
        run()

    else:
        logger.error("Неизвестный RUN_MODE: %s", settings.RUN_MODE)
if __name__ == "__main__":
    main()

