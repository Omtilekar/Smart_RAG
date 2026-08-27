"""Shared HTTP plumbing for rate-limited downloads (SEC EDGAR and friends).

SEC requires a descriptive User-Agent with contact info and enforces a
10 requests/second cap. Violating either gets you a 403 or an IP block,
so the rate limiter here is deliberately conservative (8/sec default).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- config

# SEC requires this. Set it or the scripts refuse to run.
#   export SEC_USER_AGENT="Your Name your.email@example.com"
USER_AGENT = os.getenv("SEC_USER_AGENT", "")

STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", "./data"))

# SEC's published cap is 10/sec. Stay under it.
REQUESTS_PER_SECOND = float(os.getenv("SEC_RPS", "8"))

ARCHIVES = "https://www.sec.gov/Archives"


def check_user_agent() -> None:
    if not USER_AGENT or "@" not in USER_AGENT:
        raise SystemExit(
            "SEC_USER_AGENT must be set to something like:\n"
            '  export SEC_USER_AGENT="Jane Doe jane@example.com"\n'
            "SEC blocks requests without a contact address."
        )


# ---------------------------------------------------------- rate limiter


class RateLimiter:
    """Thread-safe minimum-interval limiter.

    Simpler than a token bucket and, for a hard cap like SEC's, safer:
    it never allows a burst above the rate.
    """

    def __init__(self, per_second: float) -> None:
        self._interval = 1.0 / per_second
        self._lock = threading.Lock()
        self._next_at = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            sleep_for = self._next_at - now
            if sleep_for > 0:
                time.sleep(sleep_for)
                now = time.monotonic()
            self._next_at = now + self._interval


_limiter = RateLimiter(REQUESTS_PER_SECOND)


# ----------------------------------------------------------- http session


def make_session() -> requests.Session:
    """Session with retry/backoff on the status codes SEC actually returns."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        }
    )
    retry = Retry(
        total=5,
        backoff_factor=2.0,          # 2s, 4s, 8s, 16s, 32s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
    session.mount("https://", adapter)
    return session


def get(session: requests.Session, url: str, *, timeout: int = 60) -> requests.Response:
    """Rate-limited GET. Raises on non-2xx after retries are exhausted."""
    _limiter.wait()
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp


def download_to(session: requests.Session, url: str, dest: Path, *, timeout: int = 300) -> int:
    """Stream a URL to disk atomically. Returns bytes written.

    Writes to a .part file first so an interrupted run never leaves a
    truncated file that a resume would mistake for complete. On failure
    the .part is removed - leaving it around would waste disk on huge
    filings and, since resume only checks for the final filename, is
    otherwise harmless but pointless clutter.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    _limiter.wait()
    try:
        written = 0
        with session.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    if chunk:
                        fh.write(chunk)
                        written += len(chunk)
        tmp.replace(dest)
        return written
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
