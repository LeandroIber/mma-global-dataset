"""Helpers compartilhados de HTTP para o pipeline Sherdog/PFL."""
from __future__ import annotations

import os
import time
from typing import Optional

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
CRAWL_DELAY = 2  # segundos entre requisições, para ser educado com o Sherdog


def make_session() -> requests.Session:
    """Sessao com headers padrao; reaproveita conexao TCP entre requisicoes."""
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_html(url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """GET com retry exponencial. Devolve None depois de MAX_RETRIES."""
    getter = session.get if session is not None else requests.get
    kwargs = {"timeout": REQUEST_TIMEOUT}
    if session is None:
        kwargs["headers"] = HEADERS

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = getter(url, **kwargs)
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


def data_path(filename: str) -> str:
    """Caminho absoluto de um arquivo de dados, ancorado no diretorio do pipeline."""
    return os.path.join(BASE_DIR, filename)
