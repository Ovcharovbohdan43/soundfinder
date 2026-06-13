# Admin Broadcasts And Stats

## Назначение

Админ-функции позволяют владельцу бота смотреть статистику и отправлять посты от имени бота всем активным пользователям.

## Детальное описание

Возможности:

1. `/admin` показывает доступные админ-команды.
2. `/stats` показывает пользователей, активность, запросы и успешные отправки за сегодня.
3. `/broadcast` переводит админа в режим создания рассылки.
4. Админ отправляет пост одним сообщением: текст, фото, видео, документ или caption.
5. Бот показывает preview и кнопки `Отправить всем` / `Отмена`.
6. После подтверждения `BroadcastService` копирует исходный пост пользователям через Telegram `copy_message`.
7. Заблокировавшие бота пользователи отмечаются в SQLite и исключаются из будущих рассылок.

Статистика пишется в тот же SQLite файл, что и кэш: `CACHE_DB_PATH`.

## Как использовать

Railway variables:

```text
ADMIN_IDS=123456789
BROADCAST_ENABLED=true
BROADCAST_MESSAGES_PER_SECOND=20
```

`ADMIN_IDS` - comma-separated список Telegram user ID админов. Не используй username, Telegram Bot API надежно проверяет доступ по numeric ID.

## Примеры

Посмотреть статистику:

```text
/stats
```

Создать рекламный пост:

```text
/broadcast
```

Затем отправь боту пост, проверь preview и нажми `Отправить всем`.

## Как тестировать

```powershell
pytest tests/test_analytics_store.py tests/test_broadcast_session_store.py tests/test_config.py -q
```

Manual e2e:

1. Установить `ADMIN_IDS` своим Telegram user ID.
2. Запустить бота.
3. Отправить `/admin`.
4. Отправить `/stats`.
5. Отправить `/broadcast`, затем тестовый пост.
6. Нажать `Отмена` для проверки безопасного сценария.
7. Повторить и нажать `Отправить всем` на малой базе пользователей.

## Ограничения

- Реальные `ADMIN_IDS` и proxy credentials нельзя коммитить.
- Рассылки идут только пользователям, которые ранее писали боту и не заблокировали его.
- Telegram flood limits зависят от нагрузки; `BROADCAST_MESSAGES_PER_SECOND=20` выбран как консервативный дефолт.
- Черновик рассылки хранится в памяти до 30 минут; после рестарта бота нужно создать его заново.
- Статистика дневной активности считается по UTC-дню Unix timestamp.

## Затронутые модули

- `src/bot/handlers/admin.py`
- `src/bot/middleware.py`
- `src/infrastructure/analytics_store.py`
- `src/infrastructure/broadcast_session_store.py`
- `src/services/broadcast_service.py`
- `src/services/container.py`
- `src/config.py`

Версия / дата обновления: 2026-06-13

## Changelog

[2026-06-13] - Добавлено: админ-статистика, сбор активности пользователей и подтверждаемая рассылка постов от имени бота.
