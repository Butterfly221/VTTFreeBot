
<div align="center">
  <h1>🎙️ VTTFreeBot</h1>
  <p>
    <strong>Voice-to-Text Free Bot</strong> — локальная расшифровка голосовых сообщений<br>
    и аудиофайлов в текст. Без внешних API, без отправки данных в облако,
    <br>с гарантией полной конфиденциальности.
  </p>

  <p>
    <a href="#-архитектура">Архитектура</a> •
    <a href="#-ключевые-инженерные-решения">Инженерные решения</a> •
    <a href="#-поддерживаемые-интерфейсы">Поддерживаемые интерфейсы</a> •
    <a href="#-быстрый-старт">Быстрый старт</a> •
    <a href="#-Безопасность-и-конфиденциальность">Безопасность</a> •
    <a href="#-Контакты-и-поддержка">Roadmap</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/ASR-faster--whisper%20(base)-blueviolet?style=flat-square" alt="ASR: faster-whisper">
    <img src="https://img.shields.io/badge/Telegram-aiogram%203.x-0088cc?style=flat-square&logo=telegram" alt="Telegram: aiogram 3.x">
    <img src="https://img.shields.io/badge/Desktop-PyQt6-41cd52?style=flat-square&logo=qt" alt="Desktop: PyQt6">
    <img src="https://img.shields.io/badge/Confidentiality-zero--data--storage-success?style=flat-square" alt="Zero data storage">
    <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square" alt="License: MIT">
  </p>
</div>

---

## 📋 О проекте

**VTTFreeBot** — это мультиплатформенное приложение для расшифровки голосовых сообщений и аудиофайлов в текст. 
Всё работает **полностью локально**: модель faster-whisper запускается на вашем устройстве или сервере, 
никакие данные не покидают его пределы.

Проект родился из простой потребности: существующие Telegram-боты для расшифровки аудио либо 
отправляют данные на внешние API (Microsoft Azure, Google Cloud, Yandex SpeechKit), что нарушает 
конфиденциальность, либо требуют мощного GPU. VTTFreeBot решает обе проблемы — 
он работает на **сервере за $5/мес (1 vCPU, 1GB RAM)** и не требует интернет-соединения после загрузки модели.

### Зачем это нужно

| Сценарий | Проблема | Решение VTTFreeBot |
|---|---|---|
| 🔒 Конфиденциальные переговоры | Нельзя отправлять аудио в облачные API | Локальная модель: данные не покидают сервер |
| 🌐 Ограниченный интернет | API требуют постоянного соединения | Полностью локальный пайплайн |
| 💰 Бюджет | Облачные API стоят денег | Бесплатно, только стоимость сервера |
| 📦 Офлайн-среда | Нет доступа к внешним сервисам | Работает в изолированной сети |

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VTTFreeBot                                   │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐     │
│  │  Telegram    │   │   Desktop    │   │   VK (в разработке)  │     │
│  │  (aiogram)   │   │   (PyQt6)    │   │   (vkbottle)         │     │
│  └──────┬───────┘   └──────┬───────┘   └──────────┬───────────┘     │
│         │                  │                       │                │
│         └──────────────────┴───────────────────────┘                │
│                            │                                        │
│                    ┌───────▼────────┐                               │
│                    │  core/pipeline │  ← Единая точка входа         │
│                    └───────┬────────┘                               │
│                            │                                        │
│              ┌─────────────┼─────────────┐                          │
│              ▼             ▼             ▼                          │
│   ┌──────────────┐ ┌────────────┐ ┌──────────────┐                  │
│   │ audio/       │ │ asr/       │ │ config.py    │                  │
│   │ converter    │ │ engine (   │ │ (settings)   │                  │
│   │ temp_storage │ │ whisper)   │ │              │                  │
│   │              │ │ queue      │ │              │                  │
│   └──────────────┘ └────────────┘ └──────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 🔄 Поток обработки запроса

```
User sends voice  →  TempAudioFile (uuid4, /dev/shm)
                          ↓
                   ffmpeg: ogg/opus/mp3 → 16kHz mono wav
                          ↓
                   Queue worker (asyncio.Queue, 1 worker)
                          ↓
                   faster-whisper (base, int8)
                          ↓
                   Text → response to user
                          ↓
                   Files deleted (guaranteed in try/finally)
```

### 📦 Структура модулей

```
voice2text_bot/
│
├── audio/                    # Слой работы с аудиофайлами
│   ├── converter.py          # ffmpeg-обёртка: любой формат → 16kHz mono wav
│   └── temp_storage.py       # Context manager: гарантированное создание/удаление файлов
│
├── asr/                      # Слой распознавания речи
│   ├── engine.py             # Обёртка над faster-whisper (singleton, ленивая загрузка)
│   └── queue_worker.py       # Последовательная очередь задач (один воркер)
│
├── core/                     # Оркестрация пайплайна
│   └── pipeline.py           # voice_to_text() — единая точка входа
│
├── interfaces/               # Интерфейсы пользователя
│   ├── telegram/             # Aiogram 3.x бот (polling)
│   │   ├── bot.py            # Инициализация, запуск
│   │   ├── handlers.py       # Обработка voice/documents
│   │   └── middlewares.py    # Rate limiting, валидация
│   ├── desktop/              # PyQt6 десктопное приложение
│   │   ├── main.py           # Точка входа
│   │   ├── app.py            # Десктопный транскрайбер
│   │   └── ui.py             # Drag'n'drop, прогресс, результат
│   └── vk/                   # VK Bot (заготовка, vkbottle)
│
├── config.py                 # Pydantic-схема конфигурации (.env)
├── main.py                   # Диспетчер режимов (telegram/desktop/vk)
│
├── AGENTS.md                 # Инструкции для AI-агентов по разработке
├── GUARDRAILS.md             # Политика безопасности и конфиденциальности
├── PLAN.md                   # План разработки
└── requirements/             # Модульные requirements
    ├── base.txt              # faster-whisper, pydantic-settings
    ├── telegram.txt          # aiogram
    ├── desktop.txt           # PyQt6, pyinstaller
    └── vk.txt                # vkbottle
```

---

## 🧠 Ключевые инженерные решения

### 1. Чистая архитектура с жёсткими границами модулей

Код разделён на четыре независимых слоя, каждый со строго определённой зоной ответственности:

- **`audio/`** — не знает о Telegram, ASR, пользователях. Только файлы.
- **`asr/`** — не знает о Telegram, не знает об интерфейсах. Только модель и очередь.
- **`core/pipeline.py`** — единственное место, где `audio/` и `asr/` встречаются.
- **`interfaces/`** — пользовательские интерфейсы, которые только вызывают `core.pipeline`.

Это позволяет:
- Тестировать каждый слой изолированно
- Заменить faster-whisper на другую модель без затрагивания интерфейсов
- Добавить новый интерфейс (например, CLI или REST API) без изменения core-логики

### 2. Оптимизация под ultra-low-resource сервер (1 vCPU / 1 GB RAM)

Самая жёсткая инженерная задача проекта — работа на минимальном железе.

| Проблема | Решение | Обоснование |
|---|---|---|
| Модель не влезает в RAM | `compute_type="int8"` (4-битное квантование) + swap 2GB | Снижает потребление памяти в ~2 раза |
| Параллельный инференс → OOM | Единственный воркер `asyncio.Queue` | Один запрос в память — предсказуемое потребление |
| Multiprocessing неэффективен | `run_in_executor` с thread pool | CPU-bound whisper не масштабируется на 1 ядро |
| Загрузка модели на каждый запрос | Singleton, инициализация при старте процесса | Экономит ~10-30 секунд на каждом запросе |
| Temp-файлы на диске → износ | `TEMP_DIR=/dev/shm` (tmpfs в RAM) | Быстрее, чем диск, и очищается при ребуте |

**Результат**: стабильная работа на RuVDS за ~280 руб/мес.

### 3. Конфиденциальность как архитектура (Privacy by Design)

Проект спроектирован вокруг принципа **zero data storage**:

- **Аудиофайлы** существуют только на время обработки одного запроса
- **Тексты расшифровок** отправляются только в ответ пользователю и немедленно забываются
- **Логи** содержат только метаданные (user_id, размер, длительность), никогда — содержимое
- **Все временные файлы** — через единый context manager с `try/finally`
- Никакой БД, никакого кэша, никакой истории расшифровок

Подробнее — в [GUARDRAILS.md](GUARDRAILS.md).

### 4. Расширяемость без переписывания

Благодаря слоистой архитектуре добавление новых интерфейсов — это просто написание нового модуля в `interfaces/`:

```python
# Пример: как выглядит добавление нового интерфейса
from core.pipeline import voice_to_text

async def my_new_interface(audio_bytes: bytes) -> str:
    return await voice_to_text(
        audio_bytes=audio_bytes,
        file_extension=".mp3",
        user_id=0,
        queue=transcription_queue,
    )
```

### 5. Rate limiting и защита от DoS на уровне middleware

На слабом сервере десять одновременных запросов могут привести к OOM. Защита реализована до того, как запрос достигает пайплайна:
- **Лимит запросов**: N запросов в минуту на `user_id`
- **Лимит размера файла**: отклонение до скачивания
- **Лимит длительности аудио**: отклонение до транскрибации

---

## 🚀 Поддерживаемые интерфейсы

### 🤖 Telegram-бот

Полноценный бот на Aiogram 3.x с polling (не требует вебхука).

```bash
# Установка
pip install -r requirements/telegram.txt

# Настройка
echo "BOT_TOKEN=your_telegram_token" > .env

# Запуск
python main.py   # RUN_MODE=telegram
```

**Функции:**
- Голосовые сообщения (voice) 🔊
- Аудиофайлы (mp3, ogg, wav, flac, m4a, aac, webm) 📁
- Rate limiting (защита от спама)
- Статус «печатает…» во время обработки
- Приветственное сообщение со списком возможностей

### 🖥️ Десктопное приложение (PyQt6)

Локальное приложение с современным тёмным интерфейсом (Catppuccin Mocha).

```bash
pip install -r requirements/desktop.txt
python main.py   # RUN_MODE=desktop
```

**Функции:**
- Drag'n'drop файлов 🎯
- Кнопка «Выбрать файл» 📁
- Progress bar с обратной связью
- Темная тема (Catppuccin Mocha)
- Автоочистка результата
- Поддержка всех популярных форматов

### 📱 VK Bot (в разработке)

На фреймворке vkbottle — в планах.

---

## ⚡ Быстрый старт

### Предварительные требования

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) (в PATH)
- ~2GB свободной RAM (с учётом swap)

### 1. Клонирование и настройка

```bash
git clone https://github.com/Butterfly221/VTTFreeBot.git
cd voice2text_bot
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или .venv\Scripts\activate  # Windows
```

### 2. Установка зависимостей

```bash
# Для Telegram-бота
pip install -r requirements/telegram.txt

# Или для десктопного приложения
pip install -r requirements/desktop.txt
```

### 3. Настройка

```bash
cp .env.example .env
# Отредактируйте .env:
#   BOT_TOKEN=your_telegram_bot_token
#   RUN_MODE=telegram
```

### 4. Запуск

```bash
python main.py
```

При первом запуске faster-whisper автоматически скачает модель `base` (~150MB).

### 5. Деплой на сервер

```bash
# Настройка swap (обязательно для 1GB RAM!)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Создание systemd unit для автозапуска
sudo tee /etc/systemd/system/vttfreebot.service <<EOF
[Unit]
Description=VTTFreeBot - Voice to Text Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/voice2text_bot
ExecStart=/path/to/venv/bin/python main.py
Restart=on-failure
RestartSec=10
EnvironmentFile=/path/to/voice2text_bot/.env
LimitCORE=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now vttfreebot
```

---

## 🔒 Безопасность и конфиденциальность

### Что мы НЕ делаем (намеренно)

- ❌ Не храним аудиофайлы пользователей
- ❌ Не храним тексты расшифровок
- ❌ Не отправляем данные во внешние API
- ❌ Не ведём историю запросов
- ❌ Не логируем содержимое

### Что мы делаем для защиты

| Угроза | Защита |
|---|---|
| Утечка аудио через логи | Только user_id, размер, длительность — никакого содержимого |
| Файлы остаются на диске | tmpfs (/dev/shm) + auto-cleanup в finally |
| Подмена файлов между пользователями | Уникальные имена (uuid4) для каждого файла |
| DoS-атака | Rate limiting до попадания в пайплайн |
| Prompt injection через аудио | Транскрибированный текст — данные, не инструкция |
| Core dump с данными в памяти | `ulimit -c 0` в systemd unit |

Полная модель угроз — в [GUARDRAILS.md](GUARDRAILS.md).

---

## 🧪 Тестирование и качество

Проект разрабатывается с приоритетом тестирования:

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

Каждый модуль покрывается тестами до подключения следующего (в соответствии с [PLAN.md](PLAN.md)):

1. ✅ Конвертация аудио (одиночные файлы, разные форматы, краевые случаи)
2. ✅ Гарантированное удаление temp-файлов (даже при исключениях)
3. 🔄 Интеграционные тесты полного пайплайна

---

## 🗺️ Roadmap

### Текущий спринт

- [x] Telegram-бот (aiogram 3.x)
- [x] Десктопное приложение (PyQt6)
- [x] ASR-движок (faster-whisper base/small, int8)
- [x] Rate limiting и middleware
- [x] Безопасность: zero data storage, защита логов
- [x] План деплоя на RuVDS 1vCPU/1GB RAM

### Ближайшие планы

- [ ] **VK Bot** — интеграция с VK Messenger
- [ ] **Больше форматов** — поддержка видео (mp4, mkv) с извлечением аудиодорожки
- [ ] **Диагностическая команда** — `/stats` с информацией о состоянии очереди
- [ ] **Выбор модели на лету** — возможность для пользователя выбрать tiny/base/small
- [ ] **Локализация ответов** — английский, русский интерфейс
- [ ] **Docker-образ** — многострадальная сборка с ffmpeg и зависимостями
- [ ] **CLI-интерфейс** — для использования в скриптах и CI/CD

### Перспективы

- [ ] Поддержка CUDA при наличии GPU
- [ ] Крупные модели (medium/large) для серверов с GPU
- [ ] Параллельная обработка при масштабировании (больше RAM → больше воркеров)

---

## 🛠️ Технологический стек

| Компонент | Технология | Обоснование |
|---|---|---|
| ASR (ядро) | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2-оптимизация ~4x быстрее OpenAI Whisper |
| Модель | `base` / `small`, `int8` квантование | Влезает в 1GB RAM |
| Telegram | [Aiogram](https://docs.aiogram.dev/) 3.x | Async, зрелый, активно поддерживается |
| Desktop | [PyQt6](https://www.riverbankcomputing.com/static/Docs/PyQt6/) | Кроссплатформенный GUI |
| VK | [vkbottle](https://github.com/vkbottle/vkbottle) 5.x | Async-фреймворк для VK API |
| Конфигурация | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Валидация .env на старте |
| Конвертация | ffmpeg | Промышленный стандарт, поддержка любых форматов |
| Контейнеризация | systemd (минимализм) | Нет оверхеда Docker на 1GB RAM |
| Сборка desktop | PyInstaller | Один .exe/.app для пользователя |


## 📬 Контакты и поддержка

Для обратной связи:
@Butterfly2212 - telegram
https://vk.com/butterfly221 - vk

<div align="center">
  <h3>🎤 Превращаем голос в текст — конфиденциально, локально, бесплатно</h3>
  <p>
    <sub>Сделано с ❤️ для тех, кто ценит приватность и не любит платить за API</sub>
  </p>
</div>
