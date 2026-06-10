# Changelog

[2026-06-10] - Добавлено: iMusic fallback downloader for YouTube failures using public direct mp3 links from two.imusic.fm with timeout, host validation, tests, and configuration.

[2026-06-10] - Ð˜ÑÐ¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¾: filter exported cookies to YouTube/Google only, improve polling startup to reduce Telegram conflicts, and document proxy requirement for datacenter IPs.

[2026-06-09] - Ð˜ÑÐ¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¾: Railway variable length limit for YouTube cookies by supporting numbered `YT_DLP_COOKIES_B64_1`, `YT_DLP_COOKIES_B64_2`, ... chunks.

[2026-06-09] - Ð˜ÑÐ¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¾: YouTube cloud download failures on Railway via cookies support, improved yt-dlp client options, Node.js runtime in Docker, clearer bot-blocked errors, and YouTube cookies setup guide.

[2026-06-09] - Ð”Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾: Docker ignore rules to keep local secrets, git metadata, caches and temporary files out of Railway/Docker build contexts.

[2026-06-09] - Ð”Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾: initial MVP Telegram music bot with aiogram, yt-dlp, ffmpeg conversion, SQLite file_id cache, rate limiting, Railway Docker deploy configuration, tests and documentation.
