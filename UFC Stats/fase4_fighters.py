"""
UFC Stats Scraper - Fase 4
Le raw_fights_links.csv, coleta URLs unicas de lutadores a partir das colunas
já existentes, e raspa a biometria de cada um.
Saida: raw_fighters_profiles.jsonl.

Aplicando as Melhores Práticas (Regras A, B, C e D):
  A) Persistência Incremental via Checkpoint.
  B) Uso de requests.Session() para manter a conexão TCP viva.
  C) Paralelismo (ThreadPoolExecutor) para acelerar a extração.
  D) Dados brutos salvos em JSONL para maior integridade.
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

INPUT_FILE = "raw_fights_links.csv"
OUTPUT_FILE = "raw_fighters_profiles.jsonl"

# Limites e configuracoes
MAX_PROFILES: Optional[int] = None
MAX_WORKERS = 5  # Regra C: Threads simultaneas
REQUEST_TIMEOUT = 30
REQUEST_DELAY_SECONDS = 0.5  # Delay moderado para acompanhar o paralelismo

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

PROFILE_LABELS: dict[str, str] = {
    "Height": "Height:",
    "Weight": "Weight:",
    "Reach": "Reach:",
    "Stance": "STANCE:",
    "DOB": "DOB:",
}

# ============================================================================
# Helpers de Extracao
# ============================================================================

def fetch_html(url: str, session: requests.Session) -> Optional[str]:
    """Baixa o HTML de uma URL usando Session (Regra B)."""
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as exc:
        print(f"[ERRO] Falha ao acessar {url}: {exc}")
        return None

def _extract_profile_field(soup: BeautifulSoup, label: str) -> str:
    """Encontra o <i> cujo texto e exatamente `label` e retorna o texto pai."""
    for i_tag in soup.find_all("i"):
        if i_tag.get_text(strip=True) == label:
            if i_tag.parent is not None:
                parent_text = i_tag.parent.get_text(" ", strip=True)
                return parent_text.replace(label, "", 1).strip()
    return ""

def parse_profile(html: str, fighter_url: str) -> dict[str, str]:
    """Extrai nome + biometria de uma pagina de perfil."""
    soup = BeautifulSoup(html, "html.parser")

    name_tag = soup.find(class_="b-content__title-highlight")
    fighter_name = name_tag.get_text(strip=True) if name_tag else ""

    record: dict[str, str] = {
        "fighter_url": fighter_url,
        "fighter_name": fighter_name,
    }
    for column_name, label in PROFILE_LABELS.items():
        record[column_name] = _extract_profile_field(soup, label)
    return record

def process_fighter(url: str, session: requests.Session) -> Optional[dict]:
    """Worker function: baixa o HTML e faz o parse."""
    html = fetch_html(url, session)
    if html:
        return parse_profile(html, url)
    return None

# ============================================================================
# Orquestracao
# ============================================================================

def main() -> None:
    """Pipeline da Fase 4: Leitura -> Checkpoint -> Scraping Paralelo -> JSONL."""
    print("=== UFC Stats Pipeline - Fase 4 ===")
    
    # 1. Obter lista unica de lutadores usando as URLs mapeadas na Fase 2
    print(f"[INFO] Carregando urls de lutadores do {INPUT_FILE}...")
    df_fights = pd.read_csv(INPUT_FILE)
    
    if "fighter_1_url" not in df_fights.columns or "fighter_2_url" not in df_fights.columns:
        raise ValueError(f"As colunas fighter_1_url e fighter_2_url nao estao no {INPUT_FILE}.")
        
    all_urls = pd.concat([
        df_fights["fighter_1_url"], 
        df_fights["fighter_2_url"]
    ]).dropna().unique().tolist()
    
    print(f"[INFO] Total de lutadores unicos nos eventos: {len(all_urls)}")

    # 2. Persistencia Incremental (Regra A e D)
    processed_urls: set[str] = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        processed_urls.add(record["fighter_url"])
                    except json.JSONDecodeError:
                        continue
    
    # ALTERAÇÃO APLICADA AQUI:
    urls_to_scrape = [u.replace("https://", "http://") for u in all_urls if u not in processed_urls]
    
    if MAX_PROFILES:
        urls_to_scrape = urls_to_scrape[:MAX_PROFILES]
        
    print(f"[INFO] Ja processados: {len(processed_urls)}")
    print(f"[INFO] Restantes para raspagem: {len(urls_to_scrape)}")

    if not urls_to_scrape:
        print("[OK] Todos os perfis ja foram processados!")
        return

    # 3. Execucao Paralela com Sessions (Regra B e C)
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"\n[INFO] Iniciando raspagem paralela com {MAX_WORKERS} workers...")
    
    # Modo 'a' (append) garante que nao perderemos nada (Regra D)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submete todas as tarefas ao executor
            future_to_url = {
                executor.submit(process_fighter, url, session): url 
                for url in urls_to_scrape
            }
            
            # as_completed processa os resultados assim que cada thread termina
            for i, future in enumerate(as_completed(future_to_url), start=1):
                url = future_to_url[future]
                try:
                    record = future.result()
                    if record:
                        # Salva a linha no exato momento que fica pronta
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        f.flush()  # Forca escrita segura no disco
                        
                except Exception as exc:
                    print(f"[ERRO] Excecao na thread processando {url}: {exc}")
                    
                if i % 50 == 0 or i == len(urls_to_scrape):
                    print(f"[Progresso] {i}/{len(urls_to_scrape)} lutadores processados nesta sessao.")
                
                # Rate limiting suave 
                time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\n[OK] Fase 4 finalizada. Dados preservados em {OUTPUT_FILE}")

if __name__ == "__main__":
    main()