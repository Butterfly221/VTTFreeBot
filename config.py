"""Конфигурация приложения через переменные окружения.

Все секреты и настройки загружаются отсюда через pydantic-settings.
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация Voice2Text Bot."""

    # Telegram
    BOT_TOKEN: str = ""

    # ASR модель
    ASR_MODEL_SIZE: Literal["tiny", "base", "small"] = "base"
    ASR_COMPUTE_TYPE: Literal["int8", "float16", "float32"] = "int8"
    ASR_MODEL_CACHE_DIR: Path = Path("./model_cache")
    ASR_DEVICE: Literal["cpu", "cuda"] = "cpu"
    ASR_NUM_PROCESSORS: int = 1

    # Лимиты
    MAX_FILE_SIZE_MB: int = 25
    MAX_AUDIO_DURATION_SECONDS: int = 600  # 10 минут
    USER_RATE_LIMIT_PER_MINUTE: int = 5

    # Очередь
    QUEUE_TIMEOUT_SECONDS: int = 600  # таймаут обработки одной задачи

    # Пути
    TEMP_DIR: Path = Path("/dev/shm")  # tmpfs по умолчанию, для Windows переопределить в .env
    WAV_SAMPLE_RATE: int = 16000  # 16 kHz для Whisper

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

