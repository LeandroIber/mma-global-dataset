"""
UFC Stats Scraper - Fase 2
Le raw_events.csv, visita cada pagina de evento e extrai os links das lutas,
NOMES E URLs dos lutadores, e categoria de peso. Salva em raw_fights_links.csv.

Mudancas vs versao anterior:
  - Adicionadas colunas fighter_1_url e fighter_2_url (extraidas dos mesmos
    anchors que ja tinham o nome). Isso permite, mais a frente:
      * Fase 4: pular o passo de re-baixar paginas de luta so pra coletar
        URLs de lutadores (elas ja vem prontas neste CSV).
      * Fase 5: fazer o join da biometria por URL em vez de por nome
        (robusto a homonimia).
  - fetch_html agora faz retry com backoff exponencial.
  - Correção de protocolo: substitui https por http no loop principal.
"""

from __future__ import annotations

import time
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

INPUT_FILE = "raw_events.csv"
OUTPUT_FILE = "raw_fights_links.csv"

# Limite de eventos a processar nesta execucao de teste.
# Para processar TODOS os eventos: defina MAX_EVENTS = None.
MAX_EVENTS: Optional[int] = None

REQUEST_DELAY_SECONDS = 2
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
    """Baixa o HTML de uma URL com retry e backoff exponencial.

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


def _extract_fight_url(row: Tag) -> str:
    """Retorna a URL da pagina de detalhes da luta a partir de uma linha <tr>.

    Tenta primeiro o atributo data-link no <tr>; cai para a tag <a class="b-flag">.
    """
    data_link = row.get("data-link")
    if data_link:
        return data_link.strip()

    flag = row.find("a", class_="b-flag")
    if flag and flag.get("href"):
        return flag["href"].strip()

    return ""


def _extract_fighters(row: Tag) -> dict[str, str]:
    """Retorna nome E URL dos dois lutadores.

    Os anchors <a> dentro da segunda <td> ja carregam tanto o nome (texto)
    quanto a URL do perfil (href), entao extraimos as duas coisas de uma
    so vez. Capturar fighter_*_url e o que permite, na Fase 5, fazer o
    join pela URL do lutador em vez de pelo nome (mais robusto a homonimia).

    Lutador ausente -> string vazia em ambos os campos.
    """
    result = {
        "fighter_1": "",
        "fighter_1_url": "",
        "fighter_2": "",
        "fighter_2_url": "",
    }

    cells = row.find_all("td", recursive=False)
    if len(cells) < 2:
        return result

    fighter_links = cells[1].find_all("a")
    for idx, anchor in enumerate(fighter_links[:2], start=1):
        result[f"fighter_{idx}"] = anchor.get_text(strip=True)
        result[f"fighter_{idx}_url"] = anchor.get("href", "").strip()
    return result


def _extract_weight_class(row: Tag) -> str:
    """Retorna a categoria de peso (coluna 'Weight class').

    No UFC Stats a coluna 'Weight class' costuma ser o 7o <td> (indice 6).
    Pega o <p> com o texto da categoria.
    """
    cells = row.find_all("td", recursive=False)
    if len(cells) < 7:
        return ""

    weight_cell = cells[6]
    p_tag = weight_cell.find("p")
    return p_tag.get_text(strip=True) if p_tag else weight_cell.get_text(strip=True)


def parse_fights(html: str, event_url: str) -> list[dict]:
    """Faz o parse da pagina de um evento e retorna a lista de lutas extraidas."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="b-fight-details__table")

    if table is None:
        print(f"[AVISO] Tabela de lutas nao encontrada em {event_url}")
        return []

    tbody = table.find("tbody")
    if tbody is None:
        return []

    fights: list[dict] = []
    for row in tbody.find_all("tr"):
        # Ignora linhas que nao sao de luta (sem celulas)
        if not row.find_all("td", recursive=False):
            continue

        fight: dict[str, str] = {
            "event_url": event_url,
            "fight_url": _extract_fight_url(row),
        }
        fight.update(_extract_fighters(row))
        fight["weight_class"] = _extract_weight_class(row)
        fights.append(fight)

    return fights


def load_event_urls(csv_path: str) -> list[str]:
    """Carrega a coluna event_url do CSV de entrada como lista de strings."""
    df = pd.read_csv(csv_path)
    if "event_url" not in df.columns:
        raise ValueError(f"Coluna 'event_url' nao encontrada em {csv_path}")
    return df["event_url"].dropna().astype(str).tolist()


def save_fights(fights: list[dict], output_path: str) -> None:
    """Salva os registros de lutas em CSV via Pandas."""
    if not fights:
        print("[AVISO] Nenhuma luta extraida; CSV nao sera gerado.")
        return
    pd.DataFrame(fights).to_csv(output_path, index=False, encoding="utf-8")
    print(f"[OK] {len(fights)} lutas salvas em {output_path}")


def main() -> None:
    """Pipeline da Fase 2: le eventos, raspa cada um e consolida as lutas."""
    event_urls = load_event_urls(INPUT_FILE)

    # Para processar todos os eventos, troque a linha abaixo por:
    # urls_to_process = event_urls
    urls_to_process = event_urls[:MAX_EVENTS] if MAX_EVENTS else event_urls

    print(f"[INFO] Processando {len(urls_to_process)} de {len(event_urls)} eventos.")

    all_fights: list[dict] = []
    for idx, url in enumerate(urls_to_process, start=1):
        url = url.replace("https://", "http://")
        print(f"[{idx}/{len(urls_to_process)}] {url}")
        html = fetch_html(url)
        if html is None:
            continue

        fights = parse_fights(html, url)
        all_fights.extend(fights)
        print(f"    -> {len(fights)} lutas extraidas")

        # Rate limit: nao bate de volta no servidor imediatamente
        if idx < len(urls_to_process):
            time.sleep(REQUEST_DELAY_SECONDS)

    save_fights(all_fights, OUTPUT_FILE)


if __name__ == "__main__":
    main()