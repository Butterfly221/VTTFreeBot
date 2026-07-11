"""Тестовый скрипт для отладки транскрибации."""
import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

from audio.converter import convert_to_wav

wav_file = Path("test_speech.wav")


async def test():
    from asr.engine import whisper_engine

    await convert_to_wav(Path("test2.aac"), wav_file)
    print(f"WAV создан: {wav_file}, размер: {wav_file.stat().st_size}")

    whisper_engine.initialize()
    text = whisper_engine.transcribe(wav_file, language="ru")
    print(f"Текст: '{text}'")
    print(f"Длина текста: {len(text)}")

    wav_file.unlink(missing_ok=True)


asyncio.run(test())
