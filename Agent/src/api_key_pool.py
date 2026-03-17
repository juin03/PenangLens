"""Round-robin API key pool for Gemini calls."""

from __future__ import annotations

import os
import threading
from typing import List


def _mask_key(key: str) -> str:
    if not key:
        return "(empty)"
    if len(key) <= 10:
        return "***"
    return f"{key[:8]}...{key[-4:]}"


def _parse_csv_keys(raw: str) -> List[str]:
    return [k.strip() for k in raw.split(",") if k.strip()]


class GoogleApiKeyPool:
    """Thread-safe round-robin key selector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index = 0

    def _load_keys(self) -> List[str]:
        multi_raw = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY", "").strip()
        list_raw = os.getenv("GOOGLE_API_KEYS", "").strip()
        single_raw = os.getenv("GOOGLE_API_KEY", "").strip()

        keys: List[str] = []

        if multi_raw:
            keys.extend(_parse_csv_keys(multi_raw))
        if list_raw:
            keys.extend(_parse_csv_keys(list_raw))
        if single_raw:
            keys.append(single_raw)

        # De-duplicate while preserving order
        deduped: List[str] = []
        seen = set()
        for key in keys:
            if key not in seen:
                deduped.append(key)
                seen.add(key)

        return deduped

    def get_next_key(self) -> str:
        keys = self._load_keys()
        if not keys:
            return ""

        with self._lock:
            key = keys[self._index % len(keys)]
            self._index += 1
            return key


_POOL = GoogleApiKeyPool()


def get_next_google_api_key() -> str:
    return _POOL.get_next_key()


def mask_google_key(key: str) -> str:
    return _mask_key(key)
