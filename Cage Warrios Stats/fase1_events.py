import sys
import time
import pandas as pd
from bs4 import BeautifulSoup
from utils import CRAWL_DELAY, data_path, fetch_html, make_session

BASE_URL = "https://www.sherdog.com"
ORG_URL = "https://www.sherdog.com/organizations/Cage-Warriors-186"

def parse_events(html):
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
    html = fetch_html(url, session)
    if not html:
        return None
    return parse_events(html)

def main():
    session = make_session()
    all_events = []

    print(f"Buscando pagina principal: {ORG_URL}")
    main_events = get_events_from_page(ORG_URL, session)
    
    if main_events is None:
        sys.exit("Falha fatal ao baixar a pagina principal da organizacao.")
        
    all_events.extend(main_events)

    page = 1
    last_page_events = []
    
    while True:
        url = f"{ORG_URL}/recent-events/{page}"
        print(f"Buscando eventos do historico, pagina {page}...")
        events = get_events_from_page(url, session)

        if events is None:
            print(f"[WARN] pagina {page} falhou no download; encerrando paginacao.")
            break

        if not events or events == last_page_events:
            break

        all_events.extend(events)
        last_page_events = events
        page += 1
        time.sleep(CRAWL_DELAY)

    if not all_events:
        sys.exit("Nenhum evento encontrado.")

    df = pd.DataFrame(all_events).drop_duplicates(subset=["event_url"])
    
    out = data_path("raw_events.csv")
    df.to_csv(out, index=False)
    print(f"\nSucesso! {len(df)} eventos únicos da Cage Warriors salvos em: {out}")

if __name__ == "__main__":
    main()
