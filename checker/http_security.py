from __future__ import annotations

import ipaddress
import time
from collections import OrderedDict, deque
from typing import Iterable


class RateLimiter:
    def __init__(self, window: float = 60.0, max_keys: int = 10_000):
        self.window = window
        self.max_keys = max_keys
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()

    def allow(self, key: str, limit: int, now: float | None = None) -> bool:
        stamp = time.monotonic() if now is None else now
        bucket = self._hits.get(key)
        if bucket is None:
            if len(self._hits) >= self.max_keys:
                self._evict(stamp)
            bucket = deque()
            self._hits[key] = bucket
        else:
            self._hits.move_to_end(key)
        # Drop timestamps older than the window from the front of the bucket.
        while bucket and stamp - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(stamp)
        return True

    def _evict(self, now: float) -> None:
        # Remove buckets whose newest surviving hit is older than the window,
        # or which are empty. Inspect every key (this runs only when the map
        # is full, so the cost is bounded by max_keys).
        stale = []
        for key, bucket in self._hits.items():
            # Trim old entries first so the verdict reflects live state.
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if not bucket:
                stale.append(key)
        for key in stale:
            self._hits.pop(key, None)
        # If still over capacity after trimming, drop the oldest keys outright.
        while len(self._hits) >= self.max_keys:
            self._hits.popitem(last=False)


def parse_content_length(value: str | None) -> int | None:
    """Return the decoded Content-Length, or None if the header is missing or invalid.

    A missing header and an explicit ``0`` are both treated as an empty body
    (caller gets length 0). A non-numeric value is rejected as None.
    """
    if value is None:
        return 0
    raw = value.strip()
    if not raw.isdigit():
        return None
    return int(raw)


def client_ip(
    peer: str,
    forwarded: str | None,
    trusted_cidrs: Iterable[str],
) -> str:
    if not trusted_cidrs or not _ip_in(peer, trusted_cidrs):
        return peer
    chain = [part.strip() for part in (forwarded or "").split(",") if part.strip()]
    if not chain:
        return peer
    for addr in reversed(chain):
        if not _ip_in(addr, trusted_cidrs):
            return addr
    return chain[0]


def origin_allowed(
    origin: str,
    referer: str,
    host: str,
    public_origin: str,
    *,
    loopback: bool,
    method: str,
) -> bool:
    allowed = set()
    if public_origin:
        allowed.add(public_origin.rstrip("/"))
    if host:
        allowed.add(f"http://{host}".rstrip("/"))
        allowed.add(f"https://{host}".rstrip("/"))
    if origin:
        return origin.rstrip("/") in allowed
    if referer:
        return any(referer.startswith(item + "/") or referer.rstrip("/") == item for item in allowed)
    if method in {"GET", "HEAD"}:
        return True
    return loopback


def _ip_in(value: str, cidrs: Iterable[str]) -> bool:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    for item in cidrs:
        try:
            if addr in ipaddress.ip_network(item, strict=False):
                return True
        except ValueError:
            continue
    return False
