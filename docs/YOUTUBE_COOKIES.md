# YouTube Cookies для Railway

## Назначение

YouTube часто блокирует скачивание с datacenter IP (Railway, AWS, GCP). Ошибка в логах:

`Sign in to confirm you're not a bot`

Для облачного деплоя обычно нужны cookies авторизованной сессии YouTube.

## Как подготовить cookies

1. Используй отдельный Google/YouTube аккаунт, не основной.
2. Открой YouTube в Firefox и войди в аккаунт.
3. Установи расширение `Get cookies.txt LOCALLY`.
4. Открой `https://www.youtube.com` и убедись, что аккаунт залогинен.
5. Экспортируй cookies **только для текущего сайта YouTube**, не для всех сайтов браузера.
6. Нормальный размер файла обычно 5-50 KB. Если файл больше 200 KB, ты экспортировал лишнее.

## Как закодировать cookies в base64

Railway ограничивает длину одной переменной. Поэтому для больших cookies используй numbered chunks:

```powershell
$path = "cookies.txt"
$chunkSize = 30000
$encoded = [Convert]::ToBase64String([IO.File]::ReadAllBytes($path))
$chunks = [regex]::Matches($encoded, ".{1,$chunkSize}") | ForEach-Object { $_.Value }
for ($i = 0; $i -lt $chunks.Count; $i++) {
  "YT_DLP_COOKIES_B64_$($i + 1)=$($chunks[$i])"
}
```

Если файл маленький и Railway не ругается на лимит, можно использовать одну переменную:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("cookies.txt")) | Set-Clipboard
```

## Как добавить в Railway

1. Открой сервис бота в Railway.
2. Перейди в `Variables`.
3. Создай переменные `YT_DLP_COOKIES_B64_1`, `YT_DLP_COOKIES_B64_2`, `YT_DLP_COOKIES_B64_3` и так далее.
4. Вставь в каждую переменную соответствующий chunk.
5. Redeploy сервис.

Бот при старте запишет cookies в `/app/data/youtube_cookies.txt`.

Важно:
- номера должны идти подряд, без пропусков;
- не используй одновременно `YT_DLP_COOKIES_B64` и `YT_DLP_COOKIES_B64_1...`;
- если cookies есть, но скачивание все равно блокируется, добавь `YT_DLP_PROXY`.

## TelegramConflictError

Если в логах Railway видишь:

`Conflict: terminated by other getUpdates request`

значит с одним `BOT_TOKEN` одновременно работают два polling-процесса.

Что сделать:
1. Останови локальный запуск бота на компьютере.
2. В Railway оставь только один активный deployment/replica.
3. Redeploy сервис.

## Альтернатива: файл на volume

Если у тебя есть Railway Volume на `/app/data`:

1. Загрузи `youtube_cookies.txt` в volume.
2. Убедись, что путь: `/app/data/youtube_cookies.txt`.

Либо задай:

```text
YT_DLP_COOKIES_FILE=/app/data/youtube_cookies.txt
```

## Опционально: proxy

Если cookies недостаточно, можно добавить residential/SOCKS proxy:

```text
YT_DLP_PROXY=socks5://user:pass@host:port
```

## Режим без cookies и proxy

Если cookies и proxy пока недоступны, бот всё равно попробует скачать YouTube-видео в «мягком режиме»:

- несколько fallback player profiles (`android_vr` → `webpage` → `web_safari/mweb`);
- browser-like HTTP headers;
- паузы между запросами и дополнительные extractor retries.

Настройки Railway:

```text
YT_DLP_REQUEST_SLEEP_SECONDS=1
YT_DLP_DOWNLOAD_SLEEP_MIN_SECONDS=1
YT_DLP_DOWNLOAD_SLEEP_MAX_SECONDS=3
YT_DLP_EXTRACTOR_RETRIES=5
YT_DLP_PLAYER_CLIENTS=android_vr,tv_embedded,web_safari
```

Ограничение: если YouTube вернёт `Sign in to confirm you're not a bot` на уровне datacenter IP, мягкий режим не гарантирует успех. В этом случае нужны cookies или `YT_DLP_PROXY`.

## Как тестировать

1. Redeploy Railway service.
2. В логах не должно быть warning про отсутствие cookies.
3. Отправь боту поисковый запрос.
4. Выбери трек и проверь, что аудио скачивается.

## Ограничения

- Cookies устаревают. Их нужно обновлять периодически.
- Google может ограничить аккаунт при подозрительной активности.
- Cookies не гарантируют обход блокировки на 100%, но на Railway это обычно обязательный шаг.
- Без cookies/proxy бот пробует несколько YouTube extraction profiles и мягкие задержки, но datacenter IP всё равно может получить bot-check.

## Версия / дата обновления

Версия: 0.1.2  
Дата обновления: 2026-06-15
