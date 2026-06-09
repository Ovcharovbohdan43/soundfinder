# Music Bot Documentation

## Назначение

Бот принимает текстовый поисковый запрос в Telegram, находит несколько аудио-кандидатов через `yt-dlp`, дает пользователю выбрать результат и отправляет выбранный трек как Telegram audio.

## Детальное описание

Поток обработки:

1. Пользователь отправляет текстовый запрос.
2. `SearchService` валидирует длину и нормализует пробелы.
3. `YtDlpClient` выполняет `ytsearchN`.
4. Слишком длинные результаты отфильтровываются.
5. Handler строит inline-кнопки и сохраняет результаты в `SearchSessionStore`.
6. Пользователь выбирает трек.
7. `DownloadLimiter` проверяет per-user и global limits.
8. `AudioCache` пытается найти Telegram `file_id`.
9. При cache miss `DownloadService` скачивает и конвертирует файл.
10. Бот проверяет размер, отправляет аудио и сохраняет `file_id` в кэш.
11. Временная папка скачивания удаляется.

## Как использовать

Команды:

- `/start`: краткая инструкция.
- `/help`: пример запроса и ограничения.
- `/terms`: предупреждение о правах и правилах платформ.

Пример:

```text
daft punk harder better faster stronger
```

После выдачи нажми на кнопку нужного результата.

## Примеры настройки

Railway variables:

```text
BOT_TOKEN=123456:secret
LOG_LEVEL=INFO
TELEGRAM_MAX_AUDIO_MB=49
SEARCH_RESULTS_LIMIT=5
MAX_DURATION_SECONDS=900
MAX_CONCURRENT_DOWNLOADS=2
MAX_ACTIVE_DOWNLOADS_PER_USER=1
PREFERRED_AUDIO_CODEC=mp3
```

## Как тестировать

Unit tests:

```powershell
pytest
```

Manual e2e:

1. Запустить `python -m src.bot.main`.
2. Отправить `/start`.
3. Отправить поисковый запрос.
4. Выбрать результат.
5. Проверить, что пришло аудио.
6. Повторить выбор того же трека и убедиться, что он отправлен из кэша.

## Ограничения

- На Railway YouTube часто блокирует datacenter IP. Для скачивания нужны cookies: см. [YOUTUBE_COOKIES.md](YOUTUBE_COOKIES.md).
- Telegram audio upload limit: до 50 MB, в конфиге по умолчанию 49 MB.
- Поддерживаемые форматы отправки: `.mp3` и `.m4a`.
- Railway filesystem может быть эфемерным; для постоянного SQLite-кэша нужен Volume на `/app/data`.
- `yt-dlp` зависит от изменений сторонних платформ и требует регулярного обновления.
- Бот не должен использоваться для обхода DRM, paywall или скачивания контента без разрешения.

## Затронутые модули

- `src/config.py`
- `src/models.py`
- `src/bot/main.py`
- `src/bot/handlers/start.py`
- `src/bot/handlers/search.py`
- `src/services/search_service.py`
- `src/services/download_service.py`
- `src/services/container.py`
- `src/infrastructure/yt_dlp_client.py`
- `src/infrastructure/audio_cache.py`
- `src/infrastructure/rate_limit.py`
- `src/infrastructure/session_store.py`
- `tests/test_services.py`

## Версия / дата обновления

Версия: 0.1.0  
Дата обновления: 2026-06-09
