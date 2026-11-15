"""Is there a newer release on GitHub? Asked once at start-up, in the background.

One unauthenticated GET to the releases API with a short timeout. Any failure (offline, rate
limit, odd JSON) just means "no notice"; nothing is downloaded or installed.
"""
from __future__ import annotations

import json
import re
import threading
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from . import __version__

LATEST_URL = "https://api.github.com/repos/tranhoangtu-it/forgeseer/releases/latest"
RELEASES_PAGE = "https://github.com/tranhoangtu-it/forgeseer/releases/latest"
TIMEOUT_S = 3.0
USER_AGENT = "ForgeSeer-update-check"

Fetch = Callable[[], Any]  # returns the decoded JSON of the "latest release" endpoint


@dataclass(frozen=True)
class UpdateInfo:
    version: str   # "1.2.0"
    url: str       # release page


def parse_version(text: Any) -> tuple[int, ...] | None:
    """'v1.2.0' / '1.2' -> (1, 2, 0) / (1, 2); anything else -> None."""
    if not isinstance(text, str):
        return None
    match = re.fullmatch(r"\s*v?(\d+(?:\.\d+)*)\s*", text)
    return tuple(int(p) for p in match.group(1).split(".")) if match else None


def is_newer(candidate: str, current: str) -> bool:
    new, cur = parse_version(candidate), parse_version(current)
    if new is None or cur is None:
        return False
    width = max(len(new), len(cur))
    return new + (0,) * (width - len(new)) > cur + (0,) * (width - len(cur))


def fetch_latest() -> Any:
    request = urllib.request.Request(LATEST_URL, headers={
        "Accept": "application/vnd.github+json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 - fixed https URL
        return json.loads(response.read().decode("utf-8"))


def check_for_update(fetch: Fetch = fetch_latest, current: str = __version__) -> UpdateInfo | None:
    """The newer release, or None (up to date, draft/prerelease, or any error)."""
    try:
        data = fetch()
    except Exception:  # noqa: BLE001 - offline / timeout / bad JSON: stay quiet
        return None
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not is_newer(tag, current):
        return None
    url = data.get("html_url")
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        url = RELEASES_PAGE
    return UpdateInfo(version=".".join(map(str, parse_version(tag))), url=url)


class UpdateChecker:
    """Runs ``check_for_update`` on a daemon thread; the UI polls ``done`` / ``result``."""

    def __init__(self, fetch: Fetch = fetch_latest, current: str = __version__) -> None:
        self._fetch = fetch
        self._current = current
        self._done = threading.Event()
        self.result: UpdateInfo | None = None

    @property
    def done(self) -> bool:
        return self._done.is_set()

    def start(self) -> "UpdateChecker":
        threading.Thread(target=self._run, name="forgeseer-update", daemon=True).start()
        return self

    def _run(self) -> None:
        try:
            self.result = check_for_update(self._fetch, self._current)
        finally:
            self._done.set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._done.wait(timeout)
