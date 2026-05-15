"""
UFC Stats Pipeline - Fase 5 (Transformacao)
Le os dados brutos das Fases 1-4, faz os joins relacionais, limpa tipos
e padroniza unidades. Saida: clean_ufc_dataset.csv.
"""

from __future__ import annotations

import re
import os
import sys
from typing import Tuple

import numpy as np
import pandas as pd

EVENTS_FILE = "raw_events.csv"
FIGHTS_LINKS_FILE = "raw_fights_links.csv"
FIGHT_STATS_FILE = "raw_fight_stats.csv"
FIGHTERS_FILE = "raw_fighters_profiles.jsonl"
OUTPUT_FILE = "clean_ufc_dataset.csv"

# Fatores de conversao para o sistema metrico
LBS_TO_KG = 0.453592
INCH_TO_CM = 2.54
FOOT_TO_CM = 30.48

# ============================================================================
# Helpers de conversao de unidades
# ============================================================================

_HEIGHT_RE = re.compile(r"(\d+)'\s*(\d+)\"?")

def height_to_cm(value: object) -> float:
    if not isinstance(value, str) or value.strip() in ("", "--"):
        return np.nan
    match = _HEIGHT_RE.match(value.strip())
    if not match:
        return np.nan
    feet, inches = int(match.group(1)), int(match.group(2))
    return feet * FOOT_TO_CM + inches * INCH_TO_CM

def weight_to_kg(value: object) -> float:
    if not isinstance(value, str) or value.strip() in ("", "--"):
        return np.nan
    cleaned = value.replace("lbs.", "").strip()
    try:
        return round(float(cleaned) * LBS_TO_KG, 2)
    except ValueError:
        return np.nan

def reach_to_cm(value: object) -> float:
    if not isinstance(value, str) or value.strip() in ("", "--"):
        return np.nan
    cleaned = value.replace('"', "").strip()
    try:
        return round(float(cleaned) * INCH_TO_CM, 2)
    except ValueError:
        return np.nan

def split_x_of_y(series: pd.Series) -> Tuple[pd.Series, pd.Series]:
    extracted = series.astype(str).str.extract(r"(\d+)\s*of\s*(\d+)")
    landed = pd.to_numeric(extracted[0], errors="coerce")
    attempted = pd.to_numeric(extracted[1], errors="coerce")
    return landed, attempted

def to_datetime_safe(series: pd.Series, fmt: str = "%b %d, %Y") -> pd.Series:
    return pd.to_datetime(series, format=fmt, errors="coerce")

# ============================================================================
# Joins e Merge (Versão Corrigida)
# ============================================================================

def _merge_fighter_profile(df, fighters, side, key_col):
    bio_cols = [c for c in fighters.columns if c not in ("fighter_url", "fighter_name")]
    subset = fighters[["fighter_url"] + bio_cols].copy()
    prefixed = subset.rename(columns={c: f"{side}_{c}" for c in bio_cols})
    merged = df.merge(prefixed, left_on=key_col, right_on="fighter_url", how="left")
    if "fighter_url" in merged.columns and "fighter_url" != key_col:
        merged = merged.drop(columns=["fighter_url"])
    return merged

def merge_all(
    events: pd.DataFrame,
    fights_links: pd.DataFrame,
    fight_stats: pd.DataFrame,
    fighters: pd.DataFrame,
) -> pd.DataFrame:
    """Encadeia os quatro DataFrames numa unica tabela analitica."""
    
    # Prevenção contra mistura de protocolos HTTP/HTTPS
    for df in (events, fights_links, fight_stats):
        if "event_url" in df.columns:
            df["event_url"] = df["event_url"].str.replace("https://", "http://", regex=False)
            
    for df in (fights_links, fight_stats):
        if "fight_url" in df.columns:
            df["fight_url"] = df["fight_url"].str.replace("https://", "http://", regex=False)
            
    if "fighter_1_url" in fights_links.columns:
        fights_links["fighter_1_url"] = fights_links["fighter_1_url"].str.replace("https://", "http://", regex=False)
    if "fighter_2_url" in fights_links.columns:
        fights_links["fighter_2_url"] = fights_links["fighter_2_url"].str.replace("https://", "http://", regex=False)
    if "fighter_url" in fighters.columns:
        fighters["fighter_url"] = fighters["fighter_url"].str.replace("https://", "http://", regex=False)

    # 1. Lutas + stats
    df = fights_links.merge(fight_stats, on=["event_url", "fight_url"], how="left")

    # 2. + metadados do evento
    df = df.merge(events, on="event_url", how="left")

    # 3. + biometria f1 e f2
    df = _merge_fighter_profile(df, fighters, side="f1", key_col="fighter_1_url")
    df = _merge_fighter_profile(df, fighters, side="f2", key_col="fighter_2_url")

    return df

# ============================================================================
# Transformacoes e Ordem
# ============================================================================

def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Datas (ajustado para aceitar formatos variados do UFC Stats)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["f1_DOB"] = pd.to_datetime(df["f1_DOB"], format="%b %d, %Y", errors="coerce")
    df["f2_DOB"] = pd.to_datetime(df["f2_DOB"], format="%b %d, %Y", errors="coerce")

    for prefix in ("f1", "f2"):
        df[f"{prefix}_Height_cm"] = df[f"{prefix}_Height"].apply(height_to_cm)
        df[f"{prefix}_Weight_kg"] = df[f"{prefix}_Weight"].apply(weight_to_kg)
        df[f"{prefix}_Reach_cm"] = df[f"{prefix}_Reach"].apply(reach_to_cm)
        df[f"{prefix}_Stance"] = df[f"{prefix}_Stance"].replace({"": np.nan, "--": np.nan})
        
        for stat in ("Sig_str", "Td"):
            col = f"{prefix}_{stat}"
            landed, attempted = split_x_of_y(df[col])
            df[f"{col}_landed"] = landed
            df[f"{col}_attempted"] = attempted

    # Limpeza de colunas antigas
    cols_to_drop = ["f1_Height", "f1_Weight", "f1_Reach", "f2_Height", "f2_Weight", "f2_Reach",
                    "f1_Sig_str", "f2_Sig_str", "f1_Td", "f2_Td"]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

    return df

def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "event_name", "event_date", "fighter_1", "fighter_2", "method", "round_num", "time",
        "f1_Height_cm", "f1_Weight_kg", "f1_Reach_cm", "f2_Height_cm", "f2_Weight_kg", "f2_Reach_cm"
    ]
    existing = [c for c in preferred if c in df.columns]
    others = [c for c in df.columns if c not in existing]
    return df[existing + others]

# ============================================================================
# Main
# ============================================================================

def main() -> None:
    # Garante que os caminhos sejam relativos à pasta onde este script está
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"[INFO] Lendo arquivos da pasta: {base_dir}")
    
    try:
        events = pd.read_csv(os.path.join(base_dir, EVENTS_FILE))
        fights = pd.read_csv(os.path.join(base_dir, FIGHTS_LINKS_FILE))
        stats = pd.read_csv(os.path.join(base_dir, FIGHT_STATS_FILE))
        fighters = pd.read_json(os.path.join(base_dir, FIGHTERS_FILE), lines=True)
        fighters = fighters.drop_duplicates(subset=["fighter_url"])
        
        df = merge_all(events, fights, stats, fighters)
        df = transform(df)
        df = reorder_columns(df)
        
        output_path = os.path.join(base_dir, OUTPUT_FILE)
        df.to_csv(output_path, index=False)
        print(f"[OK] Dataset consolidado salvo em: {output_path}")
        
    except Exception as e:
        print(f"[ERRO] Falha ao carregar arquivos: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()