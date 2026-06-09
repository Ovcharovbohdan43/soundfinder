from __future__ import annotations

import base64
import binascii
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def prepare_youtube_cookies(
    *,
    data_dir: Path,
    cookies_file: str | None,
    cookies_b64: str | None,
) -> Path | None:
    if cookies_file:
        path = Path(cookies_file).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"YT_DLP_COOKIES_FILE not found: {path}")
        logger.info("Using YouTube cookies from YT_DLP_COOKIES_FILE")
        return path

    if cookies_b64:
        target = data_dir / "youtube_cookies.txt"
        try:
            decoded = base64.b64decode(cookies_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("YT_DLP_COOKIES_B64 must be valid base64") from exc

        if not decoded.strip():
            raise ValueError("YT_DLP_COOKIES_B64 decoded to an empty file")

        target.write_bytes(decoded)
        logger.info("Wrote YouTube cookies from YT_DLP_COOKIES_B64 to %s", target)
        return target

    default_path = data_dir / "youtube_cookies.txt"
    if default_path.is_file():
        logger.info("Using YouTube cookies from %s", default_path)
        return default_path

    return None
