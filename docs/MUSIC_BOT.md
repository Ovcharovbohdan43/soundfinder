# Music Bot Documentation

## Назначение

Бот принимает текстовый поисковый запрос в Telegram, находит несколько аудио-кандидатов через `two.imusic.fm`, дает пользователю выбрать результат и отправляет выбранный трек как Telegram audio. В меню также есть отдельный раздел для скачивания YouTube-видео и режим `Скачать фильм/сериал` через Kinogo. YouTube-поиск музыки по умолчанию **не используется**; резервный YouTube-поиск включается только через `YOUTUBE_SEARCH_ENABLED=true`.

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
10. При cache miss и `DIRECT_TELEGRAM_AUDIO_URL_ENABLED=true` бот пробует отправить прямой mp3 URL в Telegram без скачивания на Railway.
11. Если Telegram не принимает URL, `DownloadService` скачивает файл через `two.imusic.fm` и отправляет его обычной загрузкой.
12. При включённом YouTube-поиске скачивание всё равно идёт через `two.imusic.fm` по названию трека.
13. Бот проверяет размер при server-side скачивании, отправляет аудио и сохраняет `file_id` в кэш.
14. Временная папка скачивания удаляется.

Поток YouTube-видео:

1. Пользователь выбирает в меню `Скачать YouTube видео`.
2. Пользователь отправляет YouTube URL.
3. `VideoDownloadService` использует отдельный `video_limiter`, не связанный с музыкальными скачиваниями.
4. `YtDlpClient` скачивает лучший доступный формат, где уже есть видео и звук, с приоритетом MP4.
5. Пока идёт скачивание, bot message обновляется со спинером, процентом и примерным ETA.
6. Если итоговый файл проходит лимит `TELEGRAM_MAX_VIDEO_MB`, бот отправляет его как Telegram video.

Поток фильмов/сериалов:

1. Пользователь выбирает `Скачать фильм/сериал`.
2. `KinogoClient` ищет результаты и показывает пагинированный список.
3. После выбора карточки бот читает плеер 1 и показывает доступные качества.
4. `MovieDownloadService` скачивает HLS через `ffmpeg` в отдельной `movie_limiter` очереди.
5. Если файл проходит `TELEGRAM_MAX_MOVIE_MB`, бот отправляет его в Telegram.

Подробнее: [MOVIE_DOWNLOADS.md](MOVIE_DOWNLOADS.md).

## Как использовать

Команды:

- `/start`: краткая инструкция.
- `/help`: пример запроса и ограничения.
- `/terms`: предупреждение о правах и правилах платформ.
- `/admin`: админ-панель, доступна только пользователям из `ADMIN_IDS`.
- `/stats`: статистика пользователей, посещений и запросов.
- `/broadcast`: создание поста-рассылки от имени бота.

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
TELEGRAM_MAX_VIDEO_MB=49
SEARCH_RESULTS_LIMIT=30
SEARCH_RESULTS_PAGE_SIZE=5
MAX_DURATION_SECONDS=900
MAX_CONCURRENT_DOWNLOADS=4
MAX_ACTIVE_DOWNLOADS_PER_USER=1
MAX_CONCURRENT_VIDEO_DOWNLOADS=1
MAX_ACTIVE_VIDEO_DOWNLOADS_PER_USER=1
TELEGRAM_SINGLE_INSTANCE_LOCK=true
TELEGRAM_LOCK_STALE_SECONDS=120
TELEGRAM_POLLING_TIMEOUT=10
TELEGRAM_TASKS_CONCURRENCY_LIMIT=20
DIRECT_TELEGRAM_AUDIO_URL_ENABLED=true
YOUTUBE_VIDEO_DOWNLOAD_ENABLED=true
VIDEO_STATUS_UPDATE_INTERVAL_SECONDS=5
ADMIN_IDS=123456789
BROADCAST_ENABLED=true
BROADCAST_MESSAGES_PER_SECOND=20
MOVIE_DOWNLOAD_ENABLED=true
MAX_CONCURRENT_MOVIE_DOWNLOADS=1
MAX_ACTIVE_MOVIE_DOWNLOADS_PER_USER=1
TELEGRAM_MAX_MOVIE_MB=49
MOVIE_STATUS_UPDATE_INTERVAL_SECONDS=5
KINOGO_BASE_URL=https://kinogo.family/
KINOGO_TIMEOUT=15
KINOGO_ALLOWED_HOST_SUFFIXES=kinogo.family,cinemar.cc,cinemar.su,cinemar.one,cinemar.top,api.ortified.ws,interkh.com,host.cinemap.cc,video.cinemap.cc,cfnd.cinemap.cc
KINOGO_PROXY=
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
7. Выбрать `Скачать YouTube видео`.
8. Отправить YouTube URL и проверить статус скачивания/отправку видео.
9. Для админ-функций установить `ADMIN_IDS`, отправить `/stats` и протестировать `/broadcast` с отменой.

## Ограничения

- На Railway YouTube часто блокирует datacenter IP. По умолчанию бот YouTube не трогает; cookies нужны только при `YOUTUBE_SEARCH_ENABLED=true`: см. [YOUTUBE_COOKIES.md](YOUTUBE_COOKIES.md).
- Для polling должен быть запущен ровно один экземпляр бота. `railway.json` ограничивает сервис одной репликой, а `TELEGRAM_SINGLE_INSTANCE_LOCK=true` не дает второму процессу стартовать при общем `/app/data` volume.
- При `TelegramConflictError` вне этого проекта проверь, что не запущен локальный бот или второй Railway-сервис с тем же `BOT_TOKEN`.
- Telegram audio upload limit: до 50 MB, в конфиге по умолчанию 49 MB.
- Telegram video upload limit для Bot API также ограничен, поэтому `TELEGRAM_MAX_VIDEO_MB` по умолчанию 49 MB. Видео выше лимита не отправляется без собственного Bot API server/другого транспорта.
- Для YouTube-видео используется отдельная очередь: `MAX_CONCURRENT_VIDEO_DOWNLOADS` и `MAX_ACTIVE_VIDEO_DOWNLOADS_PER_USER`.
- Максимальное качество со звуком выбирается среди форматов, где аудио и видео уже есть вместе. 1080p+ на YouTube часто хранится как отдельное видео без звука и отдельное аудио; такой merge может превысить лимит Telegram.
- Поддерживаемые форматы отправки: `.mp3` и `.m4a`.
- Railway filesystem может быть эфемерным; для постоянного SQLite-кэша нужен Volume на `/app/data`.
- `yt-dlp` зависит от изменений сторонних платформ и требует регулярного обновления.
- `two.imusic.fm` зависит от HTML-структуры сайта. Если сайт изменит атрибуты `data-mp3`, `data-title` или search URL, клиент потребуется обновить.
- `SEARCH_RESULTS_LIMIT` ограничивает максимум результатов, которые бот забирает из ответа iMusic. `SEARCH_RESULTS_PAGE_SIZE` задаёт размер одной страницы кнопок.
- `DIRECT_TELEGRAM_AUDIO_URL_ENABLED=true` ускоряет первую отправку: Telegram сам скачивает mp3 по URL. Если URL недоступен для Telegram, бот автоматически откатывается на server-side download.
- `two.imusic.fm` используется только через публичные прямые mp3-ссылки и не обходит DRM, авторизацию или платный доступ.
- Бот не должен использоваться для обхода DRM, paywall или скачивания контента без разрешения.
- Админ-команды доступны только numeric Telegram IDs из `ADMIN_IDS`; реальные значения не коммитятся.
- Рассылки используют Telegram `copy_message`, поэтому формат поста сохраняется, а получатели видят сообщение от имени бота.

## Затронутые модули

- `src/config.py`
- `src/models.py`
- `src/bot/main.py`
- `src/bot/handlers/start.py`
- `src/bot/handlers/search.py`
- `src/bot/handlers/youtube_video.py`
- `src/bot/handlers/admin.py`
- `src/bot/middleware.py`
- `src/bot/ui.py`
- `src/services/search_service.py`
- `src/services/download_service.py`
- `src/services/container.py`
- `src/infrastructure/yt_dlp_client.py`
- `src/infrastructure/imusic_client.py`
- `src/infrastructure/audio_cache.py`
- `src/infrastructure/rate_limit.py`
- `src/infrastructure/single_instance.py`
- `src/infrastructure/session_store.py`
- `src/infrastructure/user_mode_store.py`
- `src/infrastructure/analytics_store.py`
- `src/infrastructure/broadcast_session_store.py`
- `src/services/broadcast_service.py`
- `src/services/video_download_service.py`
- `railway.json`
- `.env.example`
- `tests/test_config.py`
- `tests/test_search_keyboard.py`
- `tests/test_services.py`
- `tests/test_session_store.py`
- `tests/test_single_instance.py`
- `tests/test_user_mode_store.py`
- `tests/test_video_download_service.py`

## Версия / дата обновления

Версия: 0.2.0  
Дата обновления: 2026-06-13
