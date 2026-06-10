# Music Bot Documentation

## Назначение

Бот принимает текстовый поисковый запрос в Telegram, находит несколько аудио-кандидатов через `two.imusic.fm`, дает пользователю выбрать результат и отправляет выбранный трек как Telegram audio. YouTube по умолчанию **не используется**; резервный YouTube-поиск включается только через `YOUTUBE_SEARCH_ENABLED=true`.

## Детальное описание

Поток обработки:

1. Пользователь отправляет текстовый запрос.
2. `SearchService` валидирует длину и нормализует пробелы.
3. `IMusicClient` выполняет поиск на `two.imusic.fm`.
4. Слишком длинные результаты отфильтровываются.
5. Если iMusic-поиск не дал результата, бот возвращает пустой список. Если iMusic недоступен — ошибку поиска. YouTube-поиск возможен только при `YOUTUBE_SEARCH_ENABLED=true`.
6. Handler сохраняет весь список результатов в `SearchSessionStore` и показывает первую страницу inline-кнопок.
7. Пользователь переключает страницы кнопками `Назад`/`Дальше` или выбирает трек.
8. `DownloadLimiter` проверяет per-user и global limits.
9. `AudioCache` пытается найти Telegram `file_id`.
10. При cache miss `DownloadService` скачивает файл через `two.imusic.fm`.
11. При включённом YouTube-поиске скачивание всё равно идёт через `two.imusic.fm` по названию трека.
12. Бот проверяет размер, отправляет аудио и сохраняет `file_id` в кэш.
13. Временная папка скачивания удаляется.

## Как использовать

Команды:

- `/start`: краткая инструкция.
- `/help`: пример запроса и ограничения.
- `/terms`: предупреждение о правах и правилах платформ.

Пример:

```text
daft punk harder better faster stronger
```

После выдачи нажми на кнопку нужного результата. Если результатов больше одной страницы, используй `Назад` и `Дальше`.

## Примеры настройки

Railway variables:

```text
BOT_TOKEN=123456:secret
LOG_LEVEL=INFO
TELEGRAM_MAX_AUDIO_MB=49
SEARCH_RESULTS_LIMIT=30
SEARCH_RESULTS_PAGE_SIZE=5
MAX_DURATION_SECONDS=900
MAX_CONCURRENT_DOWNLOADS=4
MAX_ACTIVE_DOWNLOADS_PER_USER=1
TELEGRAM_SINGLE_INSTANCE_LOCK=true
TELEGRAM_LOCK_STALE_SECONDS=120
TELEGRAM_POLLING_TIMEOUT=10
TELEGRAM_TASKS_CONCURRENCY_LIMIT=20
PREFERRED_AUDIO_CODEC=mp3
IMUSIC_FALLBACK_ENABLED=true
IMUSIC_BASE_URL=https://two.imusic.fm/
IMUSIC_TIMEOUT=8
YOUTUBE_SEARCH_ENABLED=false
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

- На Railway YouTube часто блокирует datacenter IP. По умолчанию бот YouTube не трогает; cookies нужны только при `YOUTUBE_SEARCH_ENABLED=true`: см. [YOUTUBE_COOKIES.md](YOUTUBE_COOKIES.md).
- Для polling должен быть запущен ровно один экземпляр бота. `railway.json` ограничивает сервис одной репликой, а `TELEGRAM_SINGLE_INSTANCE_LOCK=true` не дает второму процессу стартовать при общем `/app/data` volume.
- При `TelegramConflictError` вне этого проекта проверь, что не запущен локальный бот или второй Railway-сервис с тем же `BOT_TOKEN`.
- Telegram audio upload limit: до 50 MB, в конфиге по умолчанию 49 MB.
- Поддерживаемые форматы отправки: `.mp3` и `.m4a`.
- Railway filesystem может быть эфемерным; для постоянного SQLite-кэша нужен Volume на `/app/data`.
- `yt-dlp` зависит от изменений сторонних платформ и требует регулярного обновления.
- `two.imusic.fm` зависит от HTML-структуры сайта. Если сайт изменит атрибуты `data-mp3`, `data-title` или search URL, клиент потребуется обновить.
- `SEARCH_RESULTS_LIMIT` ограничивает максимум результатов, которые бот забирает из ответа iMusic. `SEARCH_RESULTS_PAGE_SIZE` задаёт размер одной страницы кнопок.
- `two.imusic.fm` используется только через публичные прямые mp3-ссылки и не обходит DRM, авторизацию или платный доступ.
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
- `src/infrastructure/imusic_client.py`
- `src/infrastructure/audio_cache.py`
- `src/infrastructure/rate_limit.py`
- `src/infrastructure/single_instance.py`
- `src/infrastructure/session_store.py`
- `railway.json`
- `.env.example`
- `tests/test_config.py`
- `tests/test_search_keyboard.py`
- `tests/test_services.py`
- `tests/test_session_store.py`
- `tests/test_single_instance.py`

## Версия / дата обновления

Версия: 0.1.2  
Дата обновления: 2026-06-10
