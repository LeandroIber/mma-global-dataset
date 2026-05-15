import os
import re
import sys
import numpy as np
import pandas as pd

EVENTS_FILE = "raw_events.csv"
FIGHTS_FILE = "raw_fights.csv"
FIGHTERS_FILE = "raw_fighters_profiles.jsonl"
OUTPUT_FILE = "clean_sherdog_cagewarriors.csv"

LBS_TO_KG = 0.453592
INCH_TO_CM = 2.54
FOOT_TO_CM = 30.48

PROFILE_DROP_ON_MERGE = {"fighter_name"}

_HEIGHT_RE = re.compile(r"(\d+)'\s*(\d+)\"?")


def height_to_cm(value):
    if not isinstance(value, str) or value.strip() in ("", "--", "N/A"):
        return np.nan
    m = _HEIGHT_RE.match(value.strip())
    if not m:
        return np.nan
    return round(int(m.group(1)) * FOOT_TO_CM + int(m.group(2)) * INCH_TO_CM, 2)


def weight_to_kg(value):
    if not isinstance(value, str) or value.strip() in ("", "--", "N/A"):
        return np.nan
    txt = value.replace("lbs", "").replace(".", "").strip()
    try:
        return round(float(txt) * LBS_TO_KG, 2)
    except ValueError:
        return np.nan


def _merge_fighter(df, fighters, side, key):
    bio_cols = [
        c for c in fighters.columns
        if c != "fighter_url" and c not in PROFILE_DROP_ON_MERGE
    ]
    sub = fighters[["fighter_url"] + bio_cols].rename(
        columns={c: f"{side}_{c}" for c in bio_cols}
    )
    out = df.merge(sub, left_on=key, right_on="fighter_url", how="left")
    if "fighter_url" in out.columns and key != "fighter_url":
        out = out.drop(columns=["fighter_url"])
    return out


def merge_all(events, fights, fighters):
    events["event_url"] = events["event_url"].astype(str)
    fights["event_url"] = fights["event_url"].astype(str)
    fights["fighter_1_url"] = fights["fighter_1_url"].astype(str).replace("nan", "")
    fights["fighter_2_url"] = fights["fighter_2_url"].astype(str).replace("nan", "")
    fighters["fighter_url"] = fighters["fighter_url"].astype(str).replace("nan", "")

    df = fights.merge(events, on="event_url", how="left")
    df = _merge_fighter(df, fighters, "f1", "fighter_1_url")
    df = _merge_fighter(df, fighters, "f2", "fighter_2_url")
    return df


def derive_event_status(df):
    now = pd.Timestamp.now(tz="UTC")
    preliminar = df.get("event_status", pd.Series("", index=df.index)).astype(str)

    is_future = df["event_date"].notna() & (df["event_date"] > now)

    pending = pd.Series(False, index=df.index)
    for col in ("fighter_1_result", "fighter_2_result"):
        if col in df.columns:
            pending |= df[col].astype(str).str.contains("yet to come", case=False, na=False)

    status = pd.Series("REALIZADO", index=df.index)
    status[preliminar == "CANCELADO"] = "CANCELADO"
    status[preliminar == "SEM_LUTAS"] = "CANCELADO"
    status[preliminar == "ERRO_FETCH"] = "ERRO_FETCH"
    status[is_future | pending] = "AGENDADO"

    df["event_status"] = status
    return df


def transform(df):
    df = df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce", utc=True)

    for p in ("f1", "f2"):
        bd_col = f"{p}_birthDate"
        if bd_col in df.columns:
            df[bd_col] = pd.to_datetime(df[bd_col], format="%b %d, %Y", errors="coerce")
        if f"{p}_height" in df.columns:
            df[f"{p}_height_cm"] = df[f"{p}_height"].apply(height_to_cm)
        if f"{p}_weight" in df.columns:
            df[f"{p}_weight_kg"] = df[f"{p}_weight"].apply(weight_to_kg)

    if "round_num" in df.columns:
        df["round_num"] = pd.to_numeric(df["round_num"], errors="coerce").astype("Int64")
    if "fight_order" in df.columns:
        df["fight_order"] = pd.to_numeric(df["fight_order"], errors="coerce").astype("Int64")

    df = derive_event_status(df)

    drop_cols = [f"{p}_{c}" for p in ("f1", "f2") for c in ("height", "weight")]
    return df.drop(columns=[c for c in drop_cols if c in df.columns])


def reorder(df):
    preferred = [
        "event_name", "event_date", "event_location", "event_status",
        "fight_order", "fight_name", "weight_class",
        "method", "referee", "round_num", "time",
        "fighter_1", "fighter_1_result",
        "f1_nickname", "f1_nationality", "f1_birthplace",
        "f1_birthDate", "f1_height_cm", "f1_weight_kg", "f1_gym",
        "fighter_2", "fighter_2_result",
        "f2_nickname", "f2_nationality", "f2_birthplace",
        "f2_birthDate", "f2_height_cm", "f2_weight_kg", "f2_gym",
        "event_url", "fighter_1_url", "fighter_2_url", "referee_url",
    ]
    existing = [c for c in preferred if c in df.columns]
    others = [c for c in df.columns if c not in existing]
    return df[existing + others]


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    try:
        events = pd.read_csv(os.path.join(base, EVENTS_FILE))
        fights = pd.read_csv(os.path.join(base, FIGHTS_FILE))
        fighters = pd.read_json(os.path.join(base, FIGHTERS_FILE), lines=True)
        fighters = fighters.drop_duplicates(subset=["fighter_url"])
    except Exception as exc:
        sys.exit(f"[ERRO] falha ao carregar arquivos: {exc}")

    df = merge_all(events, fights, fighters)
    df = transform(df)
    df = reorder(df)

    out = os.path.join(base, OUTPUT_FILE)
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"{len(df)} linhas -> {out}")

    if "event_status" in df.columns:
        print("\nBreakdown por status:")
        print(df["event_status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
