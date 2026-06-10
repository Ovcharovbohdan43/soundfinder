# Telegram Music Search Bot

Telegram-бот на Python + aiogram, который ищет треки по текстовому запросу, скачивает выбранный результат через `yt-dlp`, конвертирует аудио через `ffmpeg` и отправляет файл пользователю.

## Назначение

Проект предназначен для личного или ограниченного использования: быстрый поиск трека по названию/исполнителю и отправка результата в Telegram как аудио.

## Возможности

- Поиск top N результатов через `yt-dlp`.
- Inline-кнопки для выбора конкретного результата.
- Скачивание bestaudio и конвертация в `.mp3` или `.m4a`.
- Проверка лимита размера Telegram перед отправкой.
- SQLite-кэш `telegram_file_id`, чтобы повторно не скачивать уже отправленные треки.
- Ограничение параллельных скачиваний на пользователя и глобально.
- Fallback на `two.imusic.fm`, если YouTube/`yt-dlp` не смог скачать трек.
- Railway-ready Dockerfile с установленным `ffmpeg`.

## Локальный запуск

```powershell
cd "C:\Users\user\Desktop\music-telegram-bot"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Заполни `BOT_TOKEN` в `.env`, затем:

```powershell
python -m src.bot.main
```

## Railway Deploy

1. Создай нового бота через BotFather и получи `BOT_TOKEN`.
2. Создай Railway project и подключи этот репозиторий/папку.
3. Railway автоматически использует `Dockerfile` через `railway.json`.
4. В Variables добавь минимум:
   - `BOT_TOKEN`
   - `YT_DLP_COOKIES_B64_1`, `YT_DLP_COOKIES_B64_2`, ... (обязательно для Railway, иначе YouTube блокирует скачивание)
   - `LOG_LEVEL=INFO`
   - `PREFERRED_AUDIO_CODEC=mp3`
5. Для сохранения SQLite-кэша между рестартами добавь Railway Volume и примонтируй его в `/app/data`.
6. Запусти deploy. Бот работает в polling mode, публичный HTTP endpoint не нужен.

`.dockerignore` исключает локальный `.env`, git metadata, кэши и временные файлы из Docker/Railway build context.

Если в логах видишь `Sign in to confirm you're not a bot`, следуй инструкции в [docs/YOUTUBE_COOKIES.md](docs/YOUTUBE_COOKIES.md).

## Переменные окружения

- `BOT_TOKEN`: обязательный токен Telegram Bot API.
- `TELEGRAM_MAX_AUDIO_MB`: лимит отправляемого файла, по умолчанию 49.
- `SEARCH_RESULTS_LIMIT`: количество вариантов в выдаче.
- `MAX_QUERY_LENGTH`: максимальная длина пользовательского запроса.
- `MAX_DURATION_SECONDS`: максимальная длительность трека.
- `MAX_CONCURRENT_DOWNLOADS`: общий лимит параллельных скачиваний.
- `MAX_ACTIVE_DOWNLOADS_PER_USER`: лимит активных скачиваний на пользователя.
- `DATA_DIR`, `TMP_DIR`, `CACHE_DB_PATH`: пути хранения кэша и временных файлов.
- `PREFERRED_AUDIO_CODEC`: `mp3` или `m4a`.
- `YTDLP_SOCKET_TIMEOUT`: timeout сетевых операций downloader-а.
- `YT_DLP_COOKIES_B64`: base64 cookies YouTube для локального/небольшого значения.
- `YT_DLP_COOKIES_B64_1`, `YT_DLP_COOKIES_B64_2`, ...: chunked base64 cookies для Railway.
- `YT_DLP_COOKIES_FILE`: путь к cookies-файлу вместо base64.
- `YT_DLP_PROXY`: опциональный HTTP/SOCKS proxy.
- `YT_DLP_PLAYER_CLIENTS`: список YouTube client-ов через запятую.
- `IMUSIC_FALLBACK_ENABLED`: включает fallback на `two.imusic.fm`, по умолчанию `true`.
- `IMUSIC_BASE_URL`: базовый URL fallback-сервиса, по умолчанию `https://two.imusic.fm/`.
- `IMUSIC_TIMEOUT`: timeout для поиска/скачивания через fallback.

## Тестирование

```powershell
pytest
```

Тесты проверяют:

- валидацию поискового запроса;
- фильтрацию слишком длинных треков;
- отклонение файлов больше лимита Telegram;
- запись и чтение SQLite-кэша.

## Ограничения и правообладание

Бот не обходит DRM, paywall, приватные ссылки или платный доступ. Используй его только для контента, который разрешено скачивать и распространять. Некоторые платформы могут запрещать скачивание своими правилами использования.

Fallback `two.imusic.fm` использует только публичные прямые ссылки на mp3, найденные на странице поиска. Он не обходит авторизацию, защиту или платный доступ.

Telegram Bot API принимает аудио для музыкального плеера в `.mp3`/`.m4a`; текущий лимит отправки аудио ботом составляет до 50 MB.

## Затронутые модули

- `src/bot/main.py`: запуск aiogram и wiring зависимостей.
- `src/bot/handlers/start.py`: команды `/start`, `/help`, `/terms`.
- `src/bot/handlers/search.py`: поиск, inline-выбор, скачивание и отправка.
- `src/services/search_service.py`: валидация и фильтрация результатов.
- `src/services/download_service.py`: скачивание, проверка размера, cleanup.
- `src/infrastructure/yt_dlp_client.py`: адаптер `yt-dlp`.
- `src/infrastructure/imusic_client.py`: fallback-клиент `two.imusic.fm`.
- `src/infrastructure/audio_cache.py`: SQLite-кэш Telegram `file_id`.
- `src/infrastructure/rate_limit.py`: лимиты активных скачиваний.

## Версия

Версия: 0.1.0  
Дата обновления: 2026-06-09
