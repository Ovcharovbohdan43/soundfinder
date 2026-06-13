# Movie Downloads Documentation

## Назначение

Режим `Скачать фильм/сериал` позволяет искать контент на Kinogo, выбирать качество из плеера 1 (Cinemar) и скачивать HLS-поток через ffmpeg с отправкой в Telegram.

## Детальное описание

Поток:

1. Пользователь выбирает `Скачать фильм/сериал` в меню.
2. Бот ищет результаты на `kinogo.family`.
3. Пользователь выбирает фильм/сериал из пагинированного списка.
4. `KinogoClient` читает страницу и URL плеера 1 (`cinemar.cc/embed/...`).
5. Из HTML плеера извлекаются доступные HLS-ссылки (`host.cinemap.cc/...m3u8`).
6. Пользователь выбирает качество.
7. `MovieDownloadService` скачивает поток через `ffmpeg` с `Referer: kinogo.family`.
8. Если файл проходит лимит `TELEGRAM_MAX_MOVIE_MB`, бот отправляет его как video/document.

## Как использовать

1. Нажми `Скачать фильм/сериал`.
2. Напиши название, например `матрица`.
3. Выбери результат из списка.
4. Выбери качество.
5. Дождись скачивания и отправки.

## Примеры настройки Railway

```text
MOVIE_DOWNLOAD_ENABLED=true
MAX_CONCURRENT_MOVIE_DOWNLOADS=1
MAX_ACTIVE_MOVIE_DOWNLOADS_PER_USER=1
TELEGRAM_MAX_MOVIE_MB=49
MOVIE_STATUS_UPDATE_INTERVAL_SECONDS=5
KINOGO_BASE_URL=https://kinogo.family/
KINOGO_TIMEOUT=15
```

## Как тестировать

```bash
pytest tests/test_kinogo_client.py tests/test_movie_session_store.py tests/test_movie_download_service.py -q
```

Фикстуры HTML лежат в `tests/fixtures/`.

## Ограничения

- Используй только контент, который разрешено скачивать.
- Полнометражные фильмы часто больше 49 MB и не пройдут лимит Telegram Bot API.
- Cinemar может менять обфускацию HTML; парсер рассчитан на публичные ссылки плеера 1.
- Для cinemar нужен заголовок `Referer` с Kinogo.

## Затронутые модули

- `src/infrastructure/kinogo_client.py`
- `src/infrastructure/movie_session_store.py`
- `src/services/movie_download_service.py`
- `src/bot/handlers/movie.py`

Версия / дата обновления: 2026-06-13

## Changelog

[2026-06-13] – Добавлено: режим скачивания фильмов/сериалов через Kinogo + Cinemar player 1, отдельная очередь и документация.
