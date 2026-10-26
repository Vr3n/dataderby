"""WhoScored feed requests, structure checks, and retry policy."""

from __future__ import annotations

import codecs
import json
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode

from curl_cffi.requests import Session

from dataderby.config import StageSpec
from dataderby.contract import EXPECTED_STAT_COLUMNS, SECTIONS, VIEWS, Section, View

FEED_URL = "https://www.whoscored.com/statisticsfeed/1/getteamstatistics"

_SUBCATEGORY: dict[Section, str] = {
    "summary": "all",
    "defensive": "defensive",
    "offensive": "offensive",
}
_FIELD: dict[View, str] = {
    "overall": "Overall",
    "home": "Home",
    "away": "Away",
}


class FetchError(RuntimeError):
    """Base class for a feed that could not be accepted."""


class FetchBlocked(FetchError):
    """The source returned HTTP 403. A policy answer, not a transient error."""


class FetchBudgetExceeded(FetchError):
    """A run tried to make more requests than its budget allows."""


@dataclass(slots=True)
class RequestBudget:
    """A hard ceiling on requests for one run."""

    limit: int
    used: int = 0

    def consume(self) -> None:
        """Count one request, or fail when the ceiling is reached.

        Raises:
            FetchBudgetExceeded: If the budget is already exhausted.
        """
        if self.used >= self.limit:
            raise FetchBudgetExceeded(f"request budget exhausted: {self.used}/{self.limit}")
        self.used += 1


def retry_after_seconds(value: str | None, *, now: datetime | None = None) -> float | None:
    """Parse an HTTP ``Retry-After`` value into seconds.

    Supports both forms allowed by HTTP: a number of seconds and an HTTP-date.
    The caller caps the result, so a hostile header cannot stall a run.

    Args:
        value: The header value, or ``None``.
        now: Injectable clock for the HTTP-date form.

    Returns:
        Seconds to wait, or ``None`` when the header is absent or unparseable.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - (now or datetime.now(UTC))).total_seconds())


class GatePage(FetchError):
    """The body is HTML, empty, or not the expected JSON envelope."""


class SchemaDrift(FetchError):
    """The envelope is valid but its statColumns do not match the contract."""


@dataclass(frozen=True, slots=True)
class Capture:
    """One accepted feed payload and its request metadata."""

    section: Section
    view: View
    body: bytes
    captured_at: datetime
    content_type: str | None
    url: str
    status: int = 200
    attempt: int = 1


def feed_url(
    spec: StageSpec,
    section: Section,
    view: View,
    *,
    base_url: str = FEED_URL,
) -> str:
    """Build one feed URL for a configured stage.

    The live endpoint takes the section in ``subcategory`` and the split in
    ``field``. ``category`` is always ``summaryteam``; sending ``defensive``
    there, or a split in ``subcategory``, returns a body with an empty
    ``statColumns`` list, which the contract check correctly rejects.
    """
    query = urlencode(
        {
            "stageId": spec.whoscored_stage_id,
            "category": "summaryteam",
            "subcategory": _SUBCATEGORY[section],
            "field": _FIELD[view],
            "statsAccumulationType": 0,
            "tournamentOptions": spec.whoscored_tournament_id,
            "numberOfTeamsToPick": spec.expected_teams,
            "isCurrent": "true",
            "sortBy": "Rating",
        }
    )
    return f"{base_url}?{query}"


def parse_envelope(body: bytes, section: Section, view: View) -> dict[str, Any]:
    """Decode and structurally validate a feed body.

    Args:
        body: Raw response bytes, optionally with a UTF-8 BOM.
        section: Expected section.
        view: Expected split.

    Returns:
        The decoded top-level JSON object.

    Raises:
        GatePage: If the body is not the expected JSON envelope.
        SchemaDrift: If ``statColumns`` is not the contract's list for this
            section and split.
    """
    payload_bytes = body.removeprefix(codecs.BOM_UTF8)
    try:
        payload: Any = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GatePage(f"{section}/{view}: response is not JSON") from exc

    if not isinstance(payload, dict):
        raise GatePage(f"{section}/{view}: response is not a JSON object")
    if not {"teamTableStats", "paging", "statColumns"} <= set(payload):
        raise GatePage(f"{section}/{view}: response is not the feed envelope")
    if not isinstance(payload["teamTableStats"], list):
        raise GatePage(f"{section}/{view}: teamTableStats is not a list")
    if not isinstance(payload["paging"], dict):
        raise GatePage(f"{section}/{view}: paging is not an object")
    if not isinstance(payload["statColumns"], list):
        raise GatePage(f"{section}/{view}: statColumns is not a list")

    actual = tuple(str(column) for column in payload["statColumns"])
    expected = EXPECTED_STAT_COLUMNS[(section, view)]
    if actual != expected:
        raise SchemaDrift(f"{section}/{view}: statColumns changed: {actual!r}")

    return payload


class FeedFetcher:
    """Fetch the nine feed payloads with pacing, retries, and structure checks."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        base_url: str = FEED_URL,
        spacing: float = 1.2,
        timeout: float = 30.0,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        jitter: Callable[[], float] = random.random,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._session = session if session is not None else Session(impersonate="chrome")
        self._base_url = base_url
        self._spacing = spacing
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._clock = clock
        self._jitter = jitter
        self._now = now
        self._last_request_at: float | None = None

    def _pace(self) -> None:
        if self._last_request_at is not None:
            remaining = self._spacing - (self._clock() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._clock()

    def fetch_one(self, spec: StageSpec, section: Section, view: View, token: str) -> Capture:
        """Fetch and validate one feed payload.

        Args:
            spec: Stage configuration.
            section: Feed section.
            view: Feed split.
            token: ``Model-last-Mode`` token from the page.

        Returns:
            An accepted capture.

        Raises:
            FetchBlocked: Immediately on HTTP 403. A denied request is a policy
                answer, not a transient failure.
            FetchError: Immediately on any other 4xx, or after the attempts on a
                5xx, timeout, or gate page.
            GatePage: If every attempt is a gate page or malformed body.
            SchemaDrift: Immediately, because a changed column list is not a
                transient failure.
        """
        url = feed_url(spec, section, view, base_url=self._base_url)
        last_error: FetchError | None = None

        for attempt in range(1, self._max_attempts + 1):
            self._pace()
            try:
                response = self._session.get(
                    url,
                    headers={"Model-last-Mode": token},
                    timeout=self._timeout,
                )
            except Exception as exc:
                last_error = FetchError(f"{section}/{view}: request failed: {exc}")
            else:
                status = int(response.status_code)
                headers: Mapping[str, str] = getattr(response, "headers", {})
                if status == 403:
                    raise FetchBlocked(f"{section}/{view}: HTTP 403")
                if status == 429:
                    wait = retry_after_seconds(headers.get("retry-after"))
                    if attempt < self._max_attempts:
                        self._sleep(
                            min(60.0, wait) if wait is not None else 2**attempt + self._jitter()
                        )
                        continue
                    raise FetchError(f"{section}/{view}: HTTP 429 after every attempt")
                if 400 <= status < 500:
                    raise FetchError(f"{section}/{view}: HTTP {status}")
                if status != 200:
                    last_error = FetchError(f"{section}/{view}: HTTP {status}")
                else:
                    try:
                        parse_envelope(response.content, section, view)
                    except SchemaDrift:
                        raise
                    except GatePage as exc:
                        last_error = exc
                    else:
                        return Capture(
                            section=section,
                            view=view,
                            body=response.content,
                            captured_at=self._now(),
                            content_type=headers.get("content-type"),
                            url=url,
                            status=status,
                            attempt=attempt,
                        )

            if attempt < self._max_attempts:
                self._sleep(2**attempt + self._jitter())

        if last_error is None:
            raise FetchError(f"{section}/{view}: no attempt was made")
        raise last_error

    def fetch_all(self, spec: StageSpec, token: str) -> tuple[Capture, ...]:
        """Fetch all nine feeds in Summary then Defensive then Offensive order."""
        return tuple(
            self.fetch_one(spec, section, view, token) for section in SECTIONS for view in VIEWS
        )
