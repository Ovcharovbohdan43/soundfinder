from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


def _get_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc

    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}")
    return value


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean")


def _parse_player_clients(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return ("android_vr", "tv_embedded", "web_safari")

    clients = tuple(client.strip() for client in raw_value.split(",") if client.strip())
    if not clients:
        raise ConfigError("YT_DLP_PLAYER_CLIENTS must contain at least one client")
    return clients


def _parse_csv_hosts(name: str, raw_value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if raw_value is None or raw_value.strip() == "":
        return default

    hosts: list[str] = []
    for item in raw_value.split(","):
        host = item.strip().lower().removeprefix("http://").removeprefix("https://")
        host = host.split("/", 1)[0].strip(".")
        if host:
            hosts.append(host)

    if not hosts:
        raise ConfigError(f"{name} must contain at least one host suffix")
    return tuple(dict.fromkeys(hosts))


def _parse_admin_ids(raw_value: str | None) -> tuple[int, ...]:
    if raw_value is None or raw_value.strip() == "":
        return ()

    admin_ids: list[int] = []
    for item in raw_value.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            admin_ids.append(int(value))
        except ValueError as exc:
            raise ConfigError("ADMIN_IDS must contain comma-separated Telegram user IDs") from exc

    return tuple(dict.fromkeys(admin_ids))


def _count_ytdlp_cookie_chunks() -> int:
    pattern = re.compile(r"^YT_DLP_COOKIES_B64_(\d+)$")
    return sum(1 for name in os.environ if pattern.match(name))


def get_ytdlp_cookies_source() -> tuple[str | None, str]:
    direct_value = os.getenv("YT_DLP_COOKIES_B64", "").strip()
    if direct_value:
        if _count_ytdlp_cookie_chunks() > 0:
            raise ConfigError(
                "Use either YT_DLP_COOKIES_B64 or numbered YT_DLP_COOKIES_B64_N chunks, not both."
            )
        return direct_value, "YT_DLP_COOKIES_B64"

    chunks: list[tuple[int, str]] = []
    pattern = re.compile(r"^YT_DLP_COOKIES_B64_(\d+)$")
    for name, value in os.environ.items():
        match = pattern.match(name)
        if match is None:
            continue

        chunk = value.strip()
        if not chunk:
            raise ConfigError(f"{name} is empty")
        chunks.append((int(match.group(1)), chunk))

    if not chunks:
        return None, "none"

    chunks.sort(key=lambda item: item[0])
    expected_indexes = list(range(1, len(chunks) + 1))
    actual_indexes = [index for index, _ in chunks]
    if actual_indexes != expected_indexes:
        raise ConfigError(
            "YT_DLP_COOKIES_B64 chunks must be sequential: "
            f"expected {expected_indexes}, got {actual_indexes}"
        )

    return "".join(chunk for _, chunk in chunks), f"YT_DLP_COOKIES_B64 chunks ({len(chunks)})"


@dataclass(frozen=True)
class Settings:
    bot_token: str
    log_level: str
    telegram_max_audio_mb: int
    telegram_max_video_mb: int
    search_results_limit: int
    search_results_page_size: int
    max_query_length: int
    max_duration_seconds: int
    max_concurrent_downloads: int
    max_active_downloads_per_user: int
    max_concurrent_video_downloads: int
    max_active_video_downloads_per_user: int
    data_dir: Path
    tmp_dir: Path
    cache_db_path: Path
    preferred_audio_codec: str
    ytdlp_socket_timeout: int
    ytdlp_cookies_file: str | None
    ytdlp_cookies_b64: str | None
    ytdlp_cookies_source: str
    ytdlp_proxy: str | None
    ytdlp_player_clients: tuple[str, ...]
    imusic_fallback_enabled: bool
    imusic_base_url: str
    imusic_timeout: int
    youtube_search_enabled: bool
    telegram_single_instance_lock: bool
    telegram_lock_stale_seconds: int
    telegram_polling_timeout: int
    telegram_tasks_concurrency_limit: int
    direct_telegram_audio_url_enabled: bool
    youtube_video_download_enabled: bool
    video_status_update_interval_seconds: int
    movie_download_enabled: bool
    max_concurrent_movie_downloads: int
    max_active_movie_downloads_per_user: int
    telegram_max_movie_mb: int
    movie_status_update_interval_seconds: int
    kinogo_base_url: str
    kinogo_timeout: int
    kinogo_allowed_host_suffixes: tuple[str, ...]
    kinogo_proxy: str | None
    admin_ids: tuple[int, ...]
    broadcast_enabled: bool
    broadcast_messages_per_second: int

    @property
    def telegram_max_audio_bytes(self) -> int:
        return self.telegram_max_audio_mb * 1024 * 1024

    @property
    def telegram_max_video_bytes(self) -> int:
        return self.telegram_max_video_mb * 1024 * 1024

    @property
    def telegram_max_movie_bytes(self) -> int:
        return self.telegram_max_movie_mb * 1024 * 1024


def load_settings() -> Settings:
    load_dotenv(dotenv_path=Path(".env"), override=False)

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise ConfigError("BOT_TOKEN is required. Create it in BotFather and set it in .env/Railway.")

    data_dir = Path(os.getenv("DATA_DIR", "data")).resolve()
    tmp_dir = Path(os.getenv("TMP_DIR", "tmp")).resolve()
    cache_db_path = Path(os.getenv("CACHE_DB_PATH", str(data_dir / "cache.sqlite3"))).resolve()
    preferred_audio_codec = os.getenv("PREFERRED_AUDIO_CODEC", "mp3").strip().lower()

    if preferred_audio_codec not in {"mp3", "m4a"}:
        raise ConfigError("PREFERRED_AUDIO_CODEC must be mp3 or m4a")

    cookies_b64, cookies_source = get_ytdlp_cookies_source()
    imusic_fallback_enabled = _get_bool("IMUSIC_FALLBACK_ENABLED", True)
    youtube_search_enabled = _get_bool(
        "YOUTUBE_SEARCH_ENABLED",
        not imusic_fallback_enabled,
    )

    if not imusic_fallback_enabled and not youtube_search_enabled:
        raise ConfigError("Enable IMUSIC_FALLBACK_ENABLED or YOUTUBE_SEARCH_ENABLED")

    return Settings(
        bot_token=bot_token,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        telegram_max_audio_mb=_get_int("TELEGRAM_MAX_AUDIO_MB", 49, minimum=1),
        telegram_max_video_mb=_get_int("TELEGRAM_MAX_VIDEO_MB", 49, minimum=1),
        search_results_limit=_get_int("SEARCH_RESULTS_LIMIT", 30, minimum=1),
        search_results_page_size=_get_int("SEARCH_RESULTS_PAGE_SIZE", 5, minimum=1),
        max_query_length=_get_int("MAX_QUERY_LENGTH", 120, minimum=10),
        max_duration_seconds=_get_int("MAX_DURATION_SECONDS", 900, minimum=30),
        max_concurrent_downloads=_get_int("MAX_CONCURRENT_DOWNLOADS", 4, minimum=1),
        max_active_downloads_per_user=_get_int("MAX_ACTIVE_DOWNLOADS_PER_USER", 1, minimum=1),
        max_concurrent_video_downloads=_get_int("MAX_CONCURRENT_VIDEO_DOWNLOADS", 1, minimum=1),
        max_active_video_downloads_per_user=_get_int(
            "MAX_ACTIVE_VIDEO_DOWNLOADS_PER_USER",
            1,
            minimum=1,
        ),
        data_dir=data_dir,
        tmp_dir=tmp_dir,
        cache_db_path=cache_db_path,
        preferred_audio_codec=preferred_audio_codec,
        ytdlp_socket_timeout=_get_int("YTDLP_SOCKET_TIMEOUT", 20, minimum=5),
        ytdlp_cookies_file=os.getenv("YT_DLP_COOKIES_FILE", "").strip() or None,
        ytdlp_cookies_b64=cookies_b64,
        ytdlp_cookies_source=cookies_source,
        ytdlp_proxy=os.getenv("YT_DLP_PROXY", "").strip() or None,
        ytdlp_player_clients=_parse_player_clients(os.getenv("YT_DLP_PLAYER_CLIENTS")),
        imusic_fallback_enabled=imusic_fallback_enabled,
        imusic_base_url=os.getenv("IMUSIC_BASE_URL", "https://two.imusic.fm/").strip(),
        imusic_timeout=_get_int("IMUSIC_TIMEOUT", 8, minimum=3),
        youtube_search_enabled=youtube_search_enabled,
        telegram_single_instance_lock=_get_bool("TELEGRAM_SINGLE_INSTANCE_LOCK", True),
        telegram_lock_stale_seconds=_get_int("TELEGRAM_LOCK_STALE_SECONDS", 120, minimum=30),
        telegram_polling_timeout=_get_int("TELEGRAM_POLLING_TIMEOUT", 10, minimum=1),
        telegram_tasks_concurrency_limit=_get_int("TELEGRAM_TASKS_CONCURRENCY_LIMIT", 20, minimum=1),
        direct_telegram_audio_url_enabled=_get_bool("DIRECT_TELEGRAM_AUDIO_URL_ENABLED", True),
        youtube_video_download_enabled=_get_bool("YOUTUBE_VIDEO_DOWNLOAD_ENABLED", True),
        video_status_update_interval_seconds=_get_int(
            "VIDEO_STATUS_UPDATE_INTERVAL_SECONDS",
            5,
            minimum=2,
        ),
        movie_download_enabled=_get_bool("MOVIE_DOWNLOAD_ENABLED", True),
        max_concurrent_movie_downloads=_get_int("MAX_CONCURRENT_MOVIE_DOWNLOADS", 1, minimum=1),
        max_active_movie_downloads_per_user=_get_int(
            "MAX_ACTIVE_MOVIE_DOWNLOADS_PER_USER",
            1,
            minimum=1,
        ),
        telegram_max_movie_mb=_get_int("TELEGRAM_MAX_MOVIE_MB", 49, minimum=1),
        movie_status_update_interval_seconds=_get_int(
            "MOVIE_STATUS_UPDATE_INTERVAL_SECONDS",
            5,
            minimum=2,
        ),
        kinogo_base_url=os.getenv("KINOGO_BASE_URL", "https://kinogo.family/").strip(),
        kinogo_timeout=_get_int("KINOGO_TIMEOUT", 15, minimum=3),
        kinogo_allowed_host_suffixes=_parse_csv_hosts(
            "KINOGO_ALLOWED_HOST_SUFFIXES",
            os.getenv("KINOGO_ALLOWED_HOST_SUFFIXES"),
            (
                "kinogo.family",
                "cinemar.cc",
                "cinemar.su",
                "cinemar.one",
                "cinemar.top",
                "api.ortified.ws",
                "interkh.com",
                "host.cinemap.cc",
                "video.cinemap.cc",
                "cfnd.cinemap.cc",
            ),
        ),
        kinogo_proxy=os.getenv("KINOGO_PROXY", "").strip() or None,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS")),
        broadcast_enabled=_get_bool("BROADCAST_ENABLED", True),
        broadcast_messages_per_second=_get_int("BROADCAST_MESSAGES_PER_SECOND", 20, minimum=1),
    )
