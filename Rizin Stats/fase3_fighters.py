import json
import os
import time

import pandas as pd
from bs4 import BeautifulSoup

from utils import CRAWL_DELAY, data_path, fetch_html, make_session

# Fase agnostica de organizacao: le raw_fights.csv (gerado pela fase 2) e
# visita o perfil de cada lutador. Os seletores abaixo foram verificados
# contra o HTML de um lutador do RIZIN (lutadores_pag_principal.html) e batem:
#   - bloco itemtype="http://schema.org/Person"
#   - itemprop: name / nationality / birthDate / height / weight / memberOf
#   - class="nickname" e class="birthplace" > itemprop="address"
# Por isso nao foi necessaria nenhuma alteracao de parsing para o RIZIN.

OUTPUT_FILE = data_path("raw_fighters_profiles.jsonl")


def _person_block(soup: BeautifulSoup):
    return soup.find(attrs={"itemtype": "http://schema.org/Person"})


def _itemprop_value(scope, prop: str) -> str:
    if scope is None:
        return ""
    tag = scope.find(attrs={"itemprop": prop})
    if tag is None:
        return ""
    val = tag.get("content")
    if val:
        return val.strip()
    return tag.get_text(" ", strip=True)


def _nickname(person) -> str:
    if person is None:
        return ""
    nick = person.find(class_="nickname")
    if nick is None:
        return ""
    return nick.get_text(" ", strip=True).strip(' "\'')


def _birthplace(person) -> str:
    if person is None:
        return ""
    bp = person.find(class_="birthplace")
    if bp is None:
        return ""
    addr = bp.find(attrs={"itemprop": "address"})
    if addr is not None:
        return addr.get_text(" ", strip=True)
    return ""


def parse_profile(html: str, fighter_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    person = _person_block(soup)

    return {
        "fighter_url": fighter_url,
        "fighter_name": _itemprop_value(person, "name"),
        "nickname": _nickname(person),
        "nationality": _itemprop_value(person, "nationality"),
        "birthplace": _birthplace(person),
        "birthDate": _itemprop_value(person, "birthDate"),
        "height": _itemprop_value(person, "height"),
        "weight": _itemprop_value(person, "weight"),
        "gym": _itemprop_value(person, "memberOf"),
    }


def get_unique_urls():
    try:
        df = pd.read_csv(data_path("raw_fights.csv"))
        urls = set(df["fighter_1_url"].dropna().tolist() + df["fighter_2_url"].dropna().tolist())
        return [u for u in urls if u and u.startswith("http")]
    except Exception as exc:
        print(f"[ERRO] falha ao ler raw_fights.csv: {exc}")
        return []


def get_processed_urls():
    if not os.path.exists(OUTPUT_FILE):
        return set()
    processed = set()
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                processed.add(data.get("fighter_url"))
            except json.JSONDecodeError:
                pass
    return processed


def main() -> None:
    all_urls = get_unique_urls()
    processed_urls = get_processed_urls()
    to_fetch = [u for u in all_urls if u not in processed_urls]

    print(f"Total de perfis unicos: {len(all_urls)}")
    print(f"Perfis ja baixados: {len(processed_urls)}")
    print(f"Restantes para baixar: {len(to_fetch)}")

    session = make_session()
    falhas = []  # registra o que nao entrou, em vez de sumir silenciosamente

    with open(OUTPUT_FILE, "a", encoding="utf-8") as fout:
        for i, url in enumerate(to_fetch, 1):
            print(f"Processando [{i}/{len(to_fetch)}]: {url}")
            html = fetch_html(url, session=session)

            if html is None:
                falhas.append(url)
            else:
                try:
                    rec = parse_profile(html, fighter_url=url)
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fout.flush()
                except Exception as exc:
                    print(f"[ERRO] parse falhou em {url}: {exc}")
                    falhas.append(url)

            time.sleep(CRAWL_DELAY)

    print(f"\nExtracao concluida. Dados guardados em {OUTPUT_FILE}")
    if falhas:
        print(f"[WARN] {len(falhas)} perfil(is) nao baixado(s). Rode a fase de novo "
              f"para tentar de novo (o JSONL e resumivel). Exemplos:")
        for u in falhas[:5]:
            print(f"  - {u}")


if __name__ == "__main__":
    main()
