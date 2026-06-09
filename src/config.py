from __future__ import annotations

import os
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


def _parse_player_clients(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return ("android_vr", "tv_embedded", "web_safari")

    clients = tuple(client.strip() for client in raw_value.split(",") if client.strip())
    if not clients:
        raise ConfigError("YT_DLP_PLAYER_CLIENTS must contain at least one client")
    return clients


@dataclass(frozen=True)
class Settings:
    bot_token: str
    log_level: str
    telegram_max_audio_mb: int
    search_results_limit: int
    max_query_length: int
    max_duration_seconds: int
    max_concurrent_downloads: int
    max_active_downloads_per_user: int
    data_dir: Path
    tmp_dir: Path
    cache_db_path: Path
    preferred_audio_codec: str
    ytdlp_socket_timeout: int
    ytdlp_cookies_file: str | None
    ytdlp_cookies_b64: str | None
    ytdlp_proxy: str | None
    ytdlp_player_clients: tuple[str, ...]

    @property
    def telegram_max_audio_bytes(self) -> int:
        return self.telegram_max_audio_mb * 1024 * 1024


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise ConfigError("BOT_TOKEN is required. Create it in BotFather and set it in .env/Railway.")

    data_dir = Path(os.getenv("DATA_DIR", "data")).resolve()
    tmp_dir = Path(os.getenv("TMP_DIR", "tmp")).resolve()
    cache_db_path = Path(os.getenv("CACHE_DB_PATH", str(data_dir / "cache.sqlite3"))).resolve()
    preferred_audio_codec = os.getenv("PREFERRED_AUDIO_CODEC", "mp3").strip().lower()

    if preferred_audio_codec not in {"mp3", "m4a"}:
        raise ConfigError("PREFERRED_AUDIO_CODEC must be mp3 or m4a")

    return Settings(
        bot_token=bot_token,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        telegram_max_audio_mb=_get_int("TELEGRAM_MAX_AUDIO_MB", 49, minimum=1),
        search_results_limit=_get_int("SEARCH_RESULTS_LIMIT", 5, minimum=1),
        max_query_length=_get_int("MAX_QUERY_LENGTH", 120, minimum=10),
        max_duration_seconds=_get_int("MAX_DURATION_SECONDS", 900, minimum=30),
        max_concurrent_downloads=_get_int("MAX_CONCURRENT_DOWNLOADS", 2, minimum=1),
        max_active_downloads_per_user=_get_int("MAX_ACTIVE_DOWNLOADS_PER_USER", 1, minimum=1),
        data_dir=data_dir,
        tmp_dir=tmp_dir,
        cache_db_path=cache_db_path,
        preferred_audio_codec=preferred_audio_codec,
        ytdlp_socket_timeout=_get_int("YTDLP_SOCKET_TIMEOUT", 20, minimum=5),
        ytdlp_cookies_file=os.getenv("YT_DLP_COOKIES_FILE", "").strip() or None,
        ytdlp_cookies_b64=os.getenv("YT_DLP_COOKIES_B64", "").strip() or None,
        ytdlp_proxy=os.getenv("YT_DLP_PROXY", "").strip() or None,
        ytdlp_player_clients=_parse_player_clients(os.getenv("YT_DLP_PLAYER_CLIENTS")),
    )
