import sys
import time

import pandas as pd
from bs4 import BeautifulSoup

from utils import CRAWL_DELAY, data_path, fetch_html, make_session

BASE_URL = "https://www.sherdog.com"
ORG_URL = f"{BASE_URL}/organizations/Professional-Fighters-League-12241"


def parse_events(html):
    """Extrai eventos de uma pagina ja baixada. Lista vazia = pagina sem eventos."""
    soup = BeautifulSoup(html, "html.parser")
    data = []

    for tr in soup.find_all("tr", attrs={"itemtype": "http://schema.org/Event"}):
        name_node = tr.find("span", itemprop="name")
        link_node = tr.find("a", itemprop="url")

        if not name_node or not link_node:
            continue

        url_val = link_node.get("href", "").strip()
        if url_val.startswith("/"):
            url_val = f"{BASE_URL}{url_val}"

        date_node = tr.find("meta", itemprop="startDate")
        loc_node = tr.find("td", itemprop="location")

        data.append({
            "event_name": name_node.get_text(strip=True),
            "event_url": url_val,
            "event_date": date_node.get("content", "").strip() if date_node else "",
            "event_location": loc_node.get_text(strip=True) if loc_node else "",
        })

    return data


def get_events_from_page(url, session):
    """Devolve lista de eventos, ou None se o download falhou (erro de rede/HTTP).

    Distinguir None de [] e importante: [] significa 'pagina valida, sem eventos'
    (fim do historico); None significa 'nao consegui baixar' (nao da pra concluir
    que o historico acabou).
    """
    html = fetch_html(url, session=session)
    if html is None:
        return None
    return parse_events(html)


def main():
    session = make_session()
    all_events = []

    # 1. Pagina principal (Upcoming Events + primeira leva de Recent Events)
    print("Buscando pagina principal (Upcoming/Recent)...")
    main_events = get_events_from_page(ORG_URL, session)
    if main_events is None:
        sys.exit("[FATAL] falha ao baixar a pagina principal da organizacao.")
    all_events.extend(main_events)

    # 2. Paginacao do historico (Recent Events)
    page = 1
    while True:
        url = f"{ORG_URL}/recent-events/{page}"
        print(f"Buscando eventos do historico, pagina {page}...")
        events = get_events_from_page(url, session)

        if events is None:
            # Erro de rede: nao da pra saber se o historico acabou. Avisa e para,
            # mas deixa claro que o resultado pode estar incompleto.
            print(f"[WARN] pagina {page} falhou no download; "
                  f"encerrando paginacao - historico pode estar incompleto.")
            break

        if not events:
            # Pagina valida e vazia: fim legitimo do historico.
            break

        # Trava de seguranca: se o primeiro evento ja esta na lista, o Sherdog
        # comecou a repetir paginas e chegamos ao fim.
        if any(e["event_url"] == events[0]["event_url"] for e in all_events):
            break

        all_events.extend(events)
        page += 1
        time.sleep(CRAWL_DELAY)

    if not all_events:
        sys.exit("Nenhum evento encontrado.")

    # Remove duplicados (pagina 1 de recent-events repete a pagina principal)
    df = pd.DataFrame(all_events).drop_duplicates(subset=["event_url"])
    out = data_path("raw_events.csv")
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"\nSucesso! {len(df)} eventos unicos salvos em {out}")


if __name__ == "__main__":
    main()
