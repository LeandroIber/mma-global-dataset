"""
UFC Stats Scraper - Fase 1
Extrai a lista de eventos concluidos do UFC Stats e salva em raw_events.csv.
"""

from __future__ import annotations

import sys
import time
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

URL = "http://ufcstats.com/statistics/events/completed?page=all"
OUTPUT_FILE = "raw_events.csv"

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def fetch_html(url: str) -> Optional[str]:
    """Baixa o HTML da pagina com retry e backoff exponencial.

    Tenta ate MAX_RETRIES vezes, dobrando o tempo de espera a cada falha
    (2s, 4s, 8s, ...). Retorna o HTML como string, ou None se falhar em
    todas as tentativas.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as exc:
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                print(
                    f"[AVISO] Tentativa {attempt}/{MAX_RETRIES} falhou ({exc}). "
                    f"Aguardando {wait}s antes da proxima..."
                )
                time.sleep(wait)
            else:
                print(f"[ERRO] Falha apos {MAX_RETRIES} tentativas em {url}: {exc}")
    return None


def _extract_event(row: Tag) -> Optional[dict]:
    """Extrai os 4 campos de UMA linha <tr> da tabela de eventos.

    Retorna None se a linha for espacador (sem <td>) ou se for o evento
    "NEXT" no topo da pagina (sem o anchor <a class='b-link b-link_style_black'>).
    """
    cells = row.find_all("td")
    if not cells:
        return None

    # Eventos concluidos tem este anchor. O evento "NEXT" (futuro) nao,
    # entao usamos isso como filtro natural.
    name_tag = row.find("a", class_="b-link b-link_style_black")
    if name_tag is None:
        return None

    date_tag = row.find("span", class_="b-statistics__date")

    return {
        "event_name": name_tag.get_text(strip=True),
        "event_url": name_tag.get("href", "").strip(),
        "event_date": date_tag.get_text(strip=True) if date_tag else "",
        "event_location": cells[1].get_text(strip=True) if len(cells) > 1 else "",
    }


def parse_events(html: str) -> list[dict]:
    """Faz o parse da tabela b-statistics__table-events e devolve a lista de eventos."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="b-statistics__table-events")

    if table is None:
        print("[ERRO] Tabela de eventos nao encontrada.")
        return []

    tbody = table.find("tbody")
    if tbody is None:
        return []

    events: list[dict] = []
    for row in tbody.find_all("tr"):
        event = _extract_event(row)
        if event is not None:
            events.append(event)
    return events


def save_to_csv(events: list[dict], filename: str) -> None:
    """Persiste os eventos extraidos em CSV via Pandas."""
    if not events:
        print("[AVISO] Nenhum evento para salvar.")
        return
    pd.DataFrame(events).to_csv(filename, index=False, encoding="utf-8")
    print(f"[OK] {len(events)} eventos salvos em {filename}")


def main() -> None:
    """Pipeline da Fase 1: download -> parse -> dump CSV."""
    html = fetch_html(URL)
    if html is None:
        print("[ERRO FATAL] Não foi possível baixar a lista de eventos. Abortando a pipeline.")
        sys.exit(1)
        
    events = parse_events(html)
    save_to_csv(events, OUTPUT_FILE)


if __name__ == "__main__":
    main()