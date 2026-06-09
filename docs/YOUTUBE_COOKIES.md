# YouTube Cookies для Railway

## Назначение

YouTube часто блокирует скачивание с datacenter IP (Railway, AWS, GCP). Ошибка в логах:

`Sign in to confirm you're not a bot`

Для облачного деплоя обычно нужны cookies авторизованной сессии YouTube.

## Как подготовить cookies

1. Используй отдельный Google/YouTube аккаунт, не основной.
2. Открой YouTube в Firefox и войди в аккаунт.
3. Установи расширение `Get cookies.txt LOCALLY`.
4. Открой любое видео на YouTube.
5. Экспортируй cookies в формате Netscape в файл `cookies.txt`.

## Как закодировать cookies в base64

PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("cookies.txt")) | Set-Clipboard
```

Python:

```powershell
py -c "import base64, pathlib; print(base64.b64encode(pathlib.Path('cookies.txt').read_bytes()).decode())"
```

## Как добавить в Railway

1. Открой сервис бота в Railway.
2. Перейди в `Variables`.
3. Создай переменную `YT_DLP_COOKIES_B64`.
4. Вставь base64-строку целиком, без переносов.
5. Redeploy сервис.

Бот при старте запишет cookies в `/app/data/youtube_cookies.txt`.

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

## Как тестировать

1. Redeploy Railway service.
2. В логах не должно быть warning про отсутствие cookies.
3. Отправь боту поисковый запрос.
4. Выбери трек и проверь, что аудио скачивается.

## Ограничения

- Cookies устаревают. Их нужно обновлять периодически.
- Google может ограничить аккаунт при подозрительной активности.
- Cookies не гарантируют обход блокировки на 100%, но на Railway это обычно обязательный шаг.

## Версия / дата обновления

Версия: 0.1.1  
Дата обновления: 2026-06-09
