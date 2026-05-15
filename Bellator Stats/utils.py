"""Helpers compartilhados de HTTP para o pipeline."""
from __future__ import annotations

import time
from typing import Optional

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = 2


def fetch_html(url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """GET com retry exponencial. Devolve None depois de MAX_RETRIES."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if session is not None:
                r = session.get(url, timeout=REQUEST_TIMEOUT)
            else:
                r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.text
        except requests.exceptions.RequestException as exc:
            if attempt == MAX_RETRIES:
                print(f"[ERRO] {url}: {exc}")
                return None
            wait = RETRY_BACKOFF ** attempt
            print(f"[WARN] tentativa {attempt} falhou ({exc}); aguardando {wait}s")
            time.sleep(wait)
    return None
