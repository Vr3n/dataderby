"""Download fixturedownload.com fixture CSVs and cache them on disk.

Only the UTC export is used; Asia/Kolkata is derived locally. See ``parse.py`` for why.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

URL_TEMPLATE = "https://fixturedownload.com/download/{slug}-UTC.csv"
USER_AGENT = "dataderby/0.1 (fixture calendar ingestion)"
# 404/410: not published. 406: the site rejects our Accept header, so a retry is futile.
_PERMANENT_HTTP = frozenset({404, 406, 410})


class DownloadError(RuntimeError):
    """Raised when a fixture export cannot be retrieved."""


def fetch_csv(
    slug: str,
    *,
    retries: int = 3,
    timeout: float = 30.0,
    backoff: float = 2.0,
) -> bytes:
    """Download one competition's UTC CSV export.

    Args:
        slug: The source's season slug, for example ``epl-2026``.
        retries: Total attempts for transient failures.
        timeout: Socket timeout in seconds.
        backoff: Base delay between attempts, multiplied by the attempt number.

    Returns:
        The CSV payload.

    Raises:
        DownloadError: If the export is unpublished or all attempts fail.
    """
    url = URL_TEMPLATE.format(slug=slug)
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body: bytes = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in _PERMANENT_HTTP:
                raise DownloadError(
                    f"{slug}: fixture export is not published (HTTP {exc.code})"
                ) from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        else:
            if b"Match Number" not in body[:64]:
                raise DownloadError(f"{slug}: response is not a fixture CSV")
            return body
        if attempt < retries:
            time.sleep(backoff * attempt)

    raise DownloadError(f"{slug}: failed after {retries} attempts") from last_error


def cache_path(root: Path, slug: str, fetched_at: datetime) -> Path:
    """Return the cache path for one export.

    Args:
        root: Data root, normally ``data``.
        slug: The source's season slug.
        fetched_at: When the export was retrieved.

    Returns:
        ``<root>/fixtures/raw/<slug>/<timestamp>.csv``.
    """
    stamp = fetched_at.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%S.%fZ")
    return root / "fixtures" / "raw" / slug / f"{stamp}.csv"


def write_cache(root: Path, slug: str, body: bytes, fetched_at: datetime) -> Path:
    """Write a payload to the cache atomically.

    Args:
        root: Data root, normally ``data``.
        slug: The source's season slug.
        body: Raw CSV bytes.
        fetched_at: When the export was retrieved.

    Returns:
        The path written.
    """
    path = cache_path(root, slug, fetched_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(body)
    temporary.replace(path)
    return path
