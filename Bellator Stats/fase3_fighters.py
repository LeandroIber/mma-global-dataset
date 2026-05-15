"""
Extração de perfis biométricos de lutadores do Sherdog.
Utiliza processamento paralelo e mantém estado de execução em arquivo JSONL.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from utils import HEADERS, fetch_html

INPUT_FILE = "raw_fights.csv"
OUTPUT_FILE = "raw_fighters_profiles.jsonl"

MAX_PROFILES: Optional[int] = None
MAX_WORKERS = 5
REQUEST_DELAY = 0.5


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


def fetch_one(url: str, session: requests.Session) -> Optional[dict]:
    html = fetch_html(url, session=session)
    if html is None:
        return {
            "fighter_url": url, "fighter_name": "", "nickname": "",
            "nationality": "", "birthplace": "", "birthDate": "",
            "height": "", "weight": "", "gym": "",
        }
    return parse_profile(html, url)


def _load_done() -> set[str]:
    if not os.path.exists(OUTPUT_FILE):
        return set()
    done = set()
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                done.add(json.loads(line)["fighter_url"])
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def main() -> None:
    df = pd.read_csv(INPUT_FILE)
    for col in ("fighter_1_url", "fighter_2_url"):
        if col not in df.columns:
            raise ValueError(f"Coluna ausente: {col}")

    all_urls = (
        pd.concat([df["fighter_1_url"], df["fighter_2_url"]])
        .dropna()
        .astype(str)
        .str.strip()
    )
    all_urls = all_urls[all_urls != ""].unique().tolist()
    print(f"{len(all_urls)} lutadores únicos encontrados.")

    done = _load_done()
    todo = [u for u in all_urls if u not in done]
    if MAX_PROFILES:
        todo = todo[:MAX_PROFILES]

    print(f"Processados: {len(done)} | Restantes: {len(todo)}")
    if not todo:
        print("Nenhum novo perfil para processar.")
        return

    session = requests.Session()
    session.headers.update(HEADERS)

    with open(OUTPUT_FILE, "a", encoding="utf-8") as fout:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fetch_one, url, session): url for url in todo}
            for i, fut in enumerate(as_completed(futures), start=1):
                url = futures[fut]
                try:
                    rec = fut.result()
                    if rec:
                        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fout.flush()
                except Exception as exc:
                    print(f"[ERRO] {url}: {exc}")

                if i % 50 == 0 or i == len(todo):
                    print(f"Progresso: {i}/{len(todo)}")
                time.sleep(REQUEST_DELAY)

    print(f"Finalizado. Dados salvos em {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
