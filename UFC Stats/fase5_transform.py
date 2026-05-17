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
PREVIOUS_FILE = "previous_clean_ufc_dataset.csv"
OUTPUT_FILE = "clean_ufc_dataset.csv"

LBS_TO_KG = 0.453592
INCH_TO_CM = 2.54
FOOT_TO_CM = 30.48

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

    df = fights_links.merge(fight_stats, on=["event_url", "fight_url"], how="left")
    df = df.merge(events, on="event_url", how="left")
    df = _merge_fighter_profile(df, fighters, side="f1", key_col="fighter_1_url")
    df = _merge_fighter_profile(df, fighters, side="f2", key_col="fighter_2_url")

    return df


def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
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


def merge_with_history(df_fresh: pd.DataFrame, previous_path: str) -> pd.DataFrame:
    if not os.path.exists(previous_path):
        sys.exit(f"[ERRO FATAL] {previous_path} nao encontrado. A Fase 1.5 deve rodar antes.")

    df_previous = pd.read_csv(previous_path, low_memory=False)
    print(f"[INFO] Historico carregado: {len(df_previous)} lutas.")

    df_previous["event_url"] = (
        df_previous["event_url"].astype(str).str.replace("https://", "http://", regex=False)
    )
    fresh_event_urls = set(
        df_fresh["event_url"].dropna().astype(str).str.replace("https://", "http://", regex=False).unique()
    )
    print(f"[INFO] Event_urls frescos a substituir: {len(fresh_event_urls)}")

    df_previous_filtered = df_previous[~df_previous["event_url"].isin(fresh_event_urls)]
    print(f"[INFO] Lutas historicas preservadas: {len(df_previous_filtered)}")
    print(f"[INFO] Lutas frescas a adicionar: {len(df_fresh)}")

    combined = pd.concat([df_previous_filtered, df_fresh], ignore_index=True)
    combined = reorder_columns(combined)
    combined["event_date"] = pd.to_datetime(combined["event_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return combined


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"[INFO] Lendo arquivos da pasta: {base_dir}")

    try:
        events = pd.read_csv(os.path.join(base_dir, EVENTS_FILE))
        fights = pd.read_csv(os.path.join(base_dir, FIGHTS_LINKS_FILE))
        stats = pd.read_csv(os.path.join(base_dir, FIGHT_STATS_FILE))
        fighters = pd.read_json(os.path.join(base_dir, FIGHTERS_FILE), lines=True)
        fighters = fighters.drop_duplicates(subset=["fighter_url"])

        df_fresh = merge_all(events, fights, stats, fighters)
        df_fresh = transform(df_fresh)
        df_fresh = reorder_columns(df_fresh)
        print(f"[INFO] Lutas frescas processadas: {len(df_fresh)}")

        previous_path = os.path.join(base_dir, PREVIOUS_FILE)
        df_final = merge_with_history(df_fresh, previous_path)

        output_path = os.path.join(base_dir, OUTPUT_FILE)
        df_final.to_csv(output_path, index=False)
        print(f"[OK] Dataset consolidado salvo em: {output_path}")
        print(f"[OK] Total de lutas: {len(df_final)}")

    except Exception as e:
        print(f"[ERRO] Falha na Fase 5: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
