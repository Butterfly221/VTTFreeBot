"""Middleware для Telegram-бота.

Rate limiting — защита от DoS на слабом сервере.
"""

import logging
import time
from collections import defaultdict
from typing import Awaitable, Callable, Dict, List

from aiogram import BaseMiddleware
from aiogram.types import Document, Message

from config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов от пользователя.

    Не более USER_RATE_LIMIT_PER_MINUTE запросов в минуту на user_id.
    """

    def __init__(self) -> None:
        self._user_requests: Dict[int, List[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[Message, Dict], Awaitable],
        event: Message,
        data: Dict,
    ) -> None:
        """Проверить rate limit перед передачей события хендлеру."""
        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        if not event.voice and not (event.document and self._is_audio_document(event)):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else 0
        now = time.monotonic()
        window = 60.0

        self._user_requests[user_id] = [
            t for t in self._user_requests[user_id]
            if now - t < window
        ]

        if len(self._user_requests[user_id]) >= settings.USER_RATE_LIMIT_PER_MINUTE:
            logger.info("Rate limit: user_id=%d", user_id)
            await event.answer(
                f"⏳ Слишком много запросов. "
                f"Максимум {settings.USER_RATE_LIMIT_PER_MINUTE} в минуту."
            )
            return

        self._user_requests[user_id].append(now)
        return await handler(event, data)

    @staticmethod
    def _is_audio_document(event: Message) -> bool:
        """Проверить, является ли документ аудиофайлом."""
        if not event.document or not event.document.mime_type:
            return False
        mime: str = event.document.mime_type
        return mime.startswith("audio/") or mime == "application/ogg"
