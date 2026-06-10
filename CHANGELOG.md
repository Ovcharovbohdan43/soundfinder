# Changelog

[2026-06-10] - Исправлено: parse real artist and track titles from nested iMusic HTML instead of showing the generic fallback title.

[2026-06-10] - Изменено: `two.imusic.fm` is now the primary search and download provider, YouTube is limited to fallback search, and audio captions now show the bot link instead of technical status text.

[2026-06-10] - Исправлено: filter exported cookies to YouTube/Google only, improve polling startup to reduce Telegram conflicts, and document proxy requirement for datacenter IPs.

[2026-06-09] - Исправлено: Railway variable length limit for YouTube cookies by supporting numbered `YT_DLP_COOKIES_B64_1`, `YT_DLP_COOKIES_B64_2`, ... chunks.

[2026-06-09] - Исправлено: YouTube cloud download failures on Railway via cookies support, improved yt-dlp client options, Node.js runtime in Docker, clearer bot-blocked errors, and YouTube cookies setup guide.

[2026-06-09] - Добавлено: Docker ignore rules to keep local secrets, git metadata, caches and temporary files out of Railway/Docker build contexts.

[2026-06-09] - Добавлено: initial MVP Telegram music bot with aiogram, yt-dlp, ffmpeg conversion, SQLite file_id cache, rate limiting, Railway Docker deploy configuration, tests and documentation.
