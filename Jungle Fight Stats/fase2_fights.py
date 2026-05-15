import re
import sys
import time
import pandas as pd
from bs4 import BeautifulSoup
from utils import fetch_html

BASE_URL = "https://www.sherdog.com"

def get_abs_url(href):
    return f"{BASE_URL}{href}" if href and href.startswith("/") else (href or "")

def get_fighter_info(element):
    if not element:
        return "", "", ""
    name = element.find("span", itemprop="name")
    name_txt = name.get_text(" ", strip=True) if name else ""
    
    link = element.find("a", itemprop="url")
    url = get_abs_url(link.get("href", "").strip()) if link else ""
    
    res = element.find("span", class_="final_result")
    res_txt = res.get_text(strip=True).lower() if res else ""
    
    return name_txt, url, res_txt

def get_method_and_ref(td):
    if not td:
        return "", "", ""
    b_tag = td.find("b")
    method = b_tag.get_text(" ", strip=True) if b_tag else ""
    
    ref = td.find("a", href=re.compile(r"^/referee/"))
    if ref:
        return method, ref.get_text(strip=True), get_abs_url(ref.get("href", "").strip())
    return method, "", ""

def parse_fights(html, event_url):
    soup = BeautifulSoup(html, "html.parser")
    fights = []
    seen = set()

    fc = soup.find("div", class_="fight_card")
    if fc:
        f1_name, f1_url, f1_res = get_fighter_info(fc.find("div", class_="fighter left_side"))
        f2_name, f2_url, f2_res = get_fighter_info(fc.find("div", class_="fighter right_side"))
        
        versus = fc.find("div", class_="versus")
        wc = versus.find("span", class_="weight_class") if versus else None
        weight_class = wc.get_text(strip=True) if wc else ""

        method = referee = ref_url = round_num = match_time = ""
        order = None

        resume = soup.find("table", class_="fight_card_resume")
        if resume:
            for td in resume.find_all("td"):
                txt = td.get_text(" ", strip=True)
                if "Match" in txt:
                    try: order = int(txt.replace("Match", "").strip())
                    except: pass
                elif "Method" in txt: method = txt.replace("Method", "").strip()
                elif "Referee" in txt:
                    referee = txt.replace("Referee", "").strip()
                    a_tag = td.find("a")
                    if a_tag: ref_url = get_abs_url(a_tag.get("href", ""))
                elif "Round" in txt: round_num = txt.replace("Round", "").strip()
                elif "Time" in txt: match_time = txt.replace("Time", "").strip()

        fight_name = f"{f1_name} vs {f2_name}" if f1_name and f2_name else ""
        
        fights.append({
            "event_url": event_url, "fight_order": order, "fight_name": fight_name,
            "fighter_1": f1_name, "fighter_1_url": f1_url, "fighter_1_result": f1_res,
            "fighter_2": f2_name, "fighter_2_url": f2_url, "fighter_2_result": f2_res,
            "weight_class": weight_class, "method": method, "referee": referee,
            "referee_url": ref_url, "round_num": round_num, "time": match_time,
        })
        seen.add((f1_url, f2_url))

    for table in soup.find_all("table", class_="new_table"):
        if "result" not in (table.get("class") or []):
            continue
        for row in table.find_all("tr"):
            if row.get("itemtype") != "http://schema.org/Event":
                continue
            cells = row.find_all("td", recursive=False)
            if len(cells) < 7:
                continue
            
            m = re.search(r"\b(\d+)\b", cells[0].get_text(" ", strip=True))
            order = int(m.group(1)) if m else None
            
            f1_name, f1_url, f1_res = get_fighter_info(cells[1])
            f2_name, f2_url, f2_res = get_fighter_info(cells[3])
            
            if (f1_url, f2_url) in seen:
                continue
                
            name_meta = row.find("meta", itemprop="name")
            wc_span = row.find("span", class_="weight_class")
            method, referee, ref_url = get_method_and_ref(cells[4])

            fights.append({
                "event_url": event_url, "fight_order": order,
                "fight_name": name_meta.get("content", "").strip() if name_meta else "",
                "fighter_1": f1_name, "fighter_1_url": f1_url, "fighter_1_result": f1_res,
                "fighter_2": f2_name, "fighter_2_url": f2_url, "fighter_2_result": f2_res,
                "weight_class": wc_span.get_text(strip=True) if wc_span else "",
                "method": method, "referee": referee, "referee_url": ref_url,
                "round_num": cells[5].get_text(strip=True),
                "time": cells[6].get_text(strip=True),
            })
        break

    return fights

def main():
    df = pd.read_csv("raw_events.csv").dropna(subset=["event_url"])
    today = pd.Timestamp.now(tz="UTC").normalize()
    rows = []

    base_empty = {
        "fight_order": None, "fight_name": "", "fighter_1": "", "fighter_1_url": "",
        "fighter_1_result": "", "fighter_2": "", "fighter_2_url": "", "fighter_2_result": "",
        "weight_class": "", "method": "", "referee": "", "referee_url": "",
        "round_num": "", "time": ""
    }

    for i, (_, ev) in enumerate(df.iterrows(), 1):
        url = ev["event_url"]
        date_val = pd.to_datetime(ev.get("event_date"), errors="coerce", utc=True)
        print(f"Processando [{i}/{len(df)}]: {url}")
        
        html = fetch_html(url)
        
        if not html:
            row = base_empty.copy()
            row.update({"event_url": url, "event_status": "ERRO_FETCH"})
            rows.append(row)
            continue

        fights = parse_fights(html, url)
        
        if fights:
            status = "AGENDADO" if pd.notna(date_val) and date_val > today else "REALIZADO"
            for f in fights:
                f["event_status"] = status
            rows.extend(fights)
        else:
            row = base_empty.copy()
            row.update({"event_url": url, "event_status": "CANCELADO"})
            rows.append(row)

        if i < len(df):
            time.sleep(2)

    if not rows:
        sys.exit("Nenhuma luta extraída")

    pd.DataFrame(rows).to_csv("raw_fights.csv", index=False, encoding="utf-8")

if __name__ == "__main__":
    main()