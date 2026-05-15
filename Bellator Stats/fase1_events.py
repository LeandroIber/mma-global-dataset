import sys
import time
import pandas as pd
from bs4 import BeautifulSoup
from utils import fetch_html

BASE_URL = "https://www.sherdog.com"
ORG_SLUG = "Bellator-MMA-1960"
NUM_PAGES = 4  

URLS = [f"{BASE_URL}/organizations/{ORG_SLUG}/recent-events/{i}" for i in range(1, NUM_PAGES + 1)]

def get_events(html):
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

def main():
    results = []

    for idx, u in enumerate(URLS, 1):
        print(f"Processando [{idx}/{len(URLS)}]: {u}")
        page_html = fetch_html(u)
        
        if not page_html:
            continue

        evts = get_events(page_html)
        results.extend(evts)
        
        if idx < len(URLS):
            time.sleep(2)

    if not results:
        sys.exit("Nenhum evento encontrado.")

    df = pd.DataFrame(results).drop_duplicates(subset=["event_url"])
    df.to_csv("raw_events.csv", index=False, encoding="utf-8")
    print(f"{len(df)} eventos -> raw_events.csv")

if __name__ == "__main__":
    main()
