"""
winandtitlescraping.py
======================

Quando foi feito o webscraping do UFCSTATS para baixar o dataset completo do UFC, o Dev em questão não raspou a coluna de "vitórias" nem a coluna de "Title Fights" portanto esse script salvou o dev de refazer todo o WS.

Web scraper do UFCStats.com que extrai o histórico completo de lutas
e produz um dicionário JSON indexado por `fight_url` (identificador
único por luta no domínio do ufcstats), com os campos:

    {
        "winner":          str,   # 'Draw/NC' quando não houver vencedor
        "is_title_fight":  bool,  # True quando há disputa de cinturão
        "event_date":      str,   # ISO 'YYYY-MM-DD'
        "fighter_1":       str,
        "fighter_2":       str
    }

"""

import os
import time
import json
from datetime import datetime
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

# ==========================================
# 1. Configurações
# ==========================================
BASE_DIR = r"C:\Users\Leandro\Desktop\MMA GLOBAL"
OUTPUT_JSON = os.path.join(BASE_DIR, "win_and_title_data.json")

EVENTS_URL = "http://ufcstats.com/statistics/events/completed?page=all"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 20         # segundos
SLEEP_BETWEEN_PAGES = 2      # segundos (anti-ban)
CHECKPOINT_EVERY = 50        # salva parcial a cada N eventos


# ==========================================
# 2. Funções auxiliares
# ==========================================
def get_all_event_links() -> List[str]:
    """
    Acessa a página principal do UFCStats e retorna a lista de URLs
    de todos os eventos já realizados (deduplicados).
    """
    print(f"[*] Acessando lista de eventos em: {EVENTS_URL}")
    response = requests.get(EVENTS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        print(f"[ERRO] Falha ao acessar a página principal. "
              f"Status Code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    event_links = {
        link_tag["href"]
        for link_tag in soup.find_all("a", href=True)
        if "/event-details/" in link_tag["href"]
    }

    event_links = sorted(event_links)  # determinismo na ordem de scraping
    print(f"[*] {len(event_links)} eventos encontrados no histórico do UFC.")
    return event_links


def parse_event_date(soup: BeautifulSoup) -> Optional[str]:
    """
    Extrai a data do evento do header da página e converte para ISO.

    O ufcstats serializa a data em <li class="b-list__box-list-item">
    no formato 'Month DD, YYYY' (ex: 'May 16, 2026'). A conversão para
    'YYYY-MM-DD' padroniza o tipo e garante ordenação cronológica
    lexicográfica.
    """
    for li in soup.find_all("li", class_="b-list__box-list-item"):
        txt = li.get_text(separator=" ", strip=True)
        if txt.startswith("Date"):
            raw = txt.replace("Date:", "").strip()
            try:
                return datetime.strptime(raw, "%B %d, %Y").strftime("%Y-%m-%d")
            except ValueError:
                return None
    return None


def scrape_ufc_event_page(html_content: str) -> List[Dict]:
    """
    Parse da página de evento. Retorna uma lista de lutas, cada uma
    contendo o `fight_url` (identificador único), data do evento,
    nomes dos lutadores, vencedor e flag de disputa de cinturão.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    event_date = parse_event_date(soup)
    fights_data: List[Dict] = []

    rows = soup.find_all("tr", class_="b-fight-details__table-row")

    for row in rows[1:]:  # skip header
        cols = row.find_all("td")
        if not cols or len(cols) < 10:
            continue

        # Identificador único da luta: atributo data-link da <tr>
        fight_url = row.get("data-link")
        if not fight_url:
            continue

        # Lutadores
        fighters = cols[1].find_all("a")
        if len(fighters) < 2:
            continue
        fighter_1 = fighters[0].text.strip()
        fighter_2 = fighters[1].text.strip()

        # Vencedor: <a class="b-flag_style_green"> dentro do <p> indica vitória
        win_indicators = cols[0].find_all("p")
        winner = "Draw/NC"
        if len(win_indicators) >= 1 and win_indicators[0].find("a", class_="b-flag_style_green"):
            winner = fighter_1
        elif len(win_indicators) >= 2 and win_indicators[1].find("a", class_="b-flag_style_green"):
            winner = fighter_2

        # Disputa de cinturão: ícone belt.png na coluna de weight class
        is_title_fight = any(
            "belt.png" in img.get("src", "")
            for img in cols[6].find_all("img")
        )

        fights_data.append({
            "fight_url": fight_url,
            "event_date": event_date,
            "fighter_1": fighter_1,
            "fighter_2": fighter_2,
            "winner": winner,
            "is_title_fight": is_title_fight,
        })

    return fights_data


def save_json(data: Dict, path: str) -> None:
    """Serialização atômica: escreve em arquivo temporário e renomeia."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, path)


# ==========================================
# 3. Pipeline principal
# ==========================================
def main():
    print("=" * 60)
    print(" INICIANDO WEB SCRAPING - HISTÓRICO COMPLETO UFC")
    print("=" * 60)

    event_links = get_all_event_links()
    if not event_links:
        print("[AVISO] Nenhum link encontrado. Encerrando.")
        return

    master_lookup_dict: Dict[str, Dict] = {}
    total_fights = 0
    n_events = len(event_links)

    for i, link in enumerate(event_links, start=1):
        print(f"[{i}/{n_events}] Raspando: {link}")

        try:
            response = requests.get(link, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                event_data = scrape_ufc_event_page(response.text)

                for luta in event_data:
                    fight_url = luta["fight_url"]
                    master_lookup_dict[fight_url] = {
                        "winner":         luta["winner"],
                        "is_title_fight": luta["is_title_fight"],
                        "event_date":     luta["event_date"],
                        "fighter_1":      luta["fighter_1"],
                        "fighter_2":      luta["fighter_2"],
                    }
                    total_fights += 1
            else:
                print(f"  [!] Erro {response.status_code} ao acessar página.")

        except requests.exceptions.RequestException as e:
            print(f"  [!] Erro de conexão: {e}")
        except Exception as e:
            print(f"  [!] Erro inesperado: {e}")

        # Checkpoint incremental
        if i % CHECKPOINT_EVERY == 0:
            save_json(master_lookup_dict, OUTPUT_JSON)
            print(f"  [checkpoint] {i}/{n_events} eventos processados | "
                  f"{total_fights} lutas | parcial salvo em {OUTPUT_JSON}")

        time.sleep(SLEEP_BETWEEN_PAGES)

    # Persistência final
    print("\n" + "=" * 60)
    print("[FINALIZANDO] Salvando dados no computador...")
    save_json(master_lookup_dict, OUTPUT_JSON)

    print(f"[SUCESSO] Histórico de {total_fights} lutas "
          f"({len(master_lookup_dict)} chaves únicas) salvo em:")
    print(OUTPUT_JSON)
    print("=" * 60)


if __name__ == "__main__":
    main()
