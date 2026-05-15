"""
UFC Stats Scraper - Fase 3
Le raw_fights_links.csv, visita cada pagina de luta e extrai metadados
(method, round, time) e estatisticas Fight Totals (KD, Sig_str, Td, Ctrl) por lutador.
Saida: raw_fight_stats.csv.

Sobre a tabela "Fight Totals" (fix de 2026-05-11):
  A pagina de luta do UFC Stats tem 4 tabelas:
    Table 0 (sem classe)              -> Fight Totals      <- O QUE QUEREMOS
    Table 1 (js-fight-table)          -> Totals per round
    Table 2 (sem classe)              -> Sig Strikes Totals
    Table 3 (js-fight-table)          -> Sig Strikes per round
  Pegamos a primeira <table> que NAO tem a classe 'js-fight-table'.

Mudancas vs versao anterior:
  - fetch_html agora faz retry com backoff exponencial (era single-shot).
  - STAT_FIELDS deduzido automaticamente de TOTALS_COLUMNS (DRY).
"""

from __future__ import annotations

import time
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

INPUT_FILE = "raw_fights_links.csv"
OUTPUT_FILE = "raw_fight_stats.csv"

# Limite de teste. Para processar TODAS as lutas: defina MAX_FIGHTS = None.
MAX_FIGHTS: Optional[int] = None

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

# Indices das colunas na tabela Fight Totals do UFC Stats.
# Layout: 0=Fighter, 1=KD, 2=Sig.str, 3=Sig.str%, 4=Total str,
#         5=Td, 6=Td%, 7=Sub.att, 8=Rev, 9=Ctrl
TOTALS_COLUMNS: dict[str, int] = {
    "KD": 1,
    "Sig_str": 2,
    "Td": 5,
    "Ctrl": 9,
}

# Lista achatada de colunas finais: ['f1_KD', 'f2_KD', 'f1_Sig_str', 'f2_Sig_str', ...]
# Deduzida de TOTALS_COLUMNS pra nao ter que manter duas listas em sincronia.
STAT_FIELDS: list[str] = [
    f"f{side}_{stat}"
    for stat in TOTALS_COLUMNS
    for side in (1, 2)
]


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


def _extract_label_value(soup: BeautifulSoup, label: str) -> str:
    """Procura um <i class='b-fight-details__label'> com texto `label` e retorna
    o conteudo textual do elemento pai (sem o proprio label).
    """
    label_tag = soup.find(
        "i",
        class_="b-fight-details__label",
        string=lambda s: s is not None and label in s,
    )
    if label_tag is None or label_tag.parent is None:
        return ""

    parent_text = label_tag.parent.get_text(" ", strip=True)
    label_text = label_tag.get_text(strip=True)
    return parent_text.replace(label_text, "", 1).strip()


def parse_fight_metadata(soup: BeautifulSoup) -> dict[str, str]:
    """Extrai method / round / time da secao b-fight-details__fight."""
    return {
        "method": _extract_label_value(soup, "Method:"),
        "round_num": _extract_label_value(soup, "Round:"),
        "time": _extract_label_value(soup, "Time:"),
    }


def _empty_stats() -> dict[str, str]:
    """Retorna o dicionario de estatisticas vazio (para lutas sem tabela)."""
    return {field: "" for field in STAT_FIELDS}


def _find_totals_table(soup: BeautifulSoup) -> Optional[Tag]:
    """Localiza a tabela 'Fight Totals' (resumo agregado da luta).

    Estrategia: pegar a primeira <table> da pagina que NAO tem a classe
    'js-fight-table'. As js-fight-table sao os breakdowns por round.
    """
    for table in soup.find_all("table"):
        classes = table.get("class") or []
        if "js-fight-table" not in classes:
            return table
    return None


def parse_totals_stats(soup: BeautifulSoup, fight_url: str) -> dict[str, str]:
    """Extrai estatisticas da tabela Fight Totals.

    Estrutura: 1 linha de header (<th>) + 1 linha de dados (<td>),
    cada <td> com dois <p> (lutador 1 e lutador 2).
    Lutas antigas/canceladas podem nao ter a tabela; nesse caso retorna vazios.
    """
    table = _find_totals_table(soup)
    if table is None:
        print(f"[AVISO] Tabela Fight Totals ausente em {fight_url}")
        return _empty_stats()

    rows = table.find_all("tr")
    if len(rows) < 2:
        print(f"[AVISO] Tabela Fight Totals sem linha de dados em {fight_url}")
        return _empty_stats()

    # rows[0] = header (<th>), rows[1] = dados (<td>)
    data_row = rows[1]
    cells: list[Tag] = data_row.find_all("td", recursive=False)

    stats: dict[str, str] = {}
    for field_name, col_index in TOTALS_COLUMNS.items():
        if col_index >= len(cells):
            stats[f"f1_{field_name}"] = ""
            stats[f"f2_{field_name}"] = ""
            continue

        paragraphs = cells[col_index].find_all("p")
        stats[f"f1_{field_name}"] = paragraphs[0].get_text(strip=True) if len(paragraphs) > 0 else ""
        stats[f"f2_{field_name}"] = paragraphs[1].get_text(strip=True) if len(paragraphs) > 1 else ""

    return stats


def parse_fight_page(html: str, event_url: str, fight_url: str) -> dict[str, str]:
    """Pipeline de parse de uma pagina de luta: metadados + estatisticas Totals."""
    soup = BeautifulSoup(html, "html.parser")

    record: dict[str, str] = {
        "event_url": event_url,
        "fight_url": fight_url,
    }
    record.update(parse_fight_metadata(soup))
    record.update(parse_totals_stats(soup, fight_url))
    return record


def load_fight_index(csv_path: str) -> pd.DataFrame:
    """Carrega o CSV da Fase 2 e devolve apenas event_url + fight_url validos."""
    df = pd.read_csv(csv_path)
    required = {"event_url", "fight_url"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colunas ausentes em {csv_path}: {missing}")

    df = df.dropna(subset=["fight_url"])
    df = df[df["fight_url"].astype(str).str.strip() != ""]
    return df[["event_url", "fight_url"]].reset_index(drop=True)


def save_stats(records: list[dict], output_path: str) -> None:
    """Persiste os registros de estatisticas em CSV."""
    if not records:
        print("[AVISO] Nenhuma luta extraida; CSV nao sera gerado.")
        return
    pd.DataFrame(records).to_csv(output_path, index=False, encoding="utf-8")
    print(f"[OK] {len(records)} lutas salvas em {output_path}")


def main() -> None:
    """Pipeline da Fase 3: le indice de lutas, raspa cada uma e consolida."""
    fight_index = load_fight_index(INPUT_FILE)

    # Para processar todas as lutas, troque a linha por:
    # rows_to_process = fight_index
    rows_to_process = fight_index.head(MAX_FIGHTS) if MAX_FIGHTS else fight_index

    total = len(rows_to_process)
    print(f"[INFO] Processando {total} de {len(fight_index)} lutas.")

    records: list[dict] = []
    for idx, (_, row) in enumerate(rows_to_process.iterrows(), start=1):
        # ALTERAÇÃO APLICADA AQUI:
        event_url = str(row["event_url"]).replace("https://", "http://")
        fight_url = str(row["fight_url"]).replace("https://", "http://")
        
        print(f"[{idx}/{total}] {fight_url}")

        html = fetch_html(fight_url)
        if html is None:
            continue

        record = parse_fight_page(html, event_url, fight_url)
        records.append(record)

        if idx < total:
            time.sleep(REQUEST_DELAY_SECONDS)

    save_stats(records, OUTPUT_FILE)


if __name__ == "__main__":
    main()