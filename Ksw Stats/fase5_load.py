import datetime
import json
import os
import shutil
import sys
import pandas as pd
from kaggle.api.kaggle_api_extended import KaggleApi

KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME", "leandroiber")
DATASET_SLUG = "ksw-mma-dataset"
DATASET_TITLE = "KSW MMA Dataset Complete"
CSV_FILE = "clean_sherdog_ksw.csv"
UPLOAD_DIR = "kaggle_upload"
METADATA_FILE = "dataset-metadata.json"
DATASET_DESCRIPTION = (
    "Dataset completo do Konfrontacja Sztuk Walki (KSW), a maior promocao "
    "de MMA da Polonia, raspado do Sherdog.com. Eventos, lutas, resultados, "
    "metodos, arbitros e biometria dos lutadores em sistema metrico. A coluna "
    "event_status indica o estado do evento: REALIZADO, AGENDADO (evento "
    "futuro / luta ainda nao ocorrida), CANCELADO ou ERRO_FETCH (falha na coleta)."
)


def version_notes(csv_path):
    try:
        n = len(pd.read_csv(csv_path))
        today = datetime.datetime.now().strftime("%d/%m/%Y")
        return f"Atualizacao {today}: {n} lutas registradas."
    except Exception:
        return "Atualizacao automatica."


def prepare_upload_dir(base):
    csv_path = os.path.join(base, CSV_FILE)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"arquivo nao encontrado: {csv_path}")

    upload_path = os.path.join(base, UPLOAD_DIR)
    if os.path.exists(upload_path):
        shutil.rmtree(upload_path)
    os.makedirs(upload_path)
    shutil.copy(csv_path, os.path.join(upload_path, CSV_FILE))

    metadata = {
        "title": DATASET_TITLE,
        "id": f"{KAGGLE_USERNAME}/{DATASET_SLUG}",
        "licenses": [{"name": "CC0-1.0"}],
        "description": DATASET_DESCRIPTION,
    }
    with open(os.path.join(upload_path, METADATA_FILE), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return upload_path, version_notes(csv_path)


def authenticate():
    try:
        api = KaggleApi()
        api.authenticate()
        return api
    except Exception as exc:
        sys.exit(f"Erro no Kaggle: {exc}")


def upload(api, folder, notes):
    dataset_url = f"https://www.kaggle.com/datasets/{KAGGLE_USERNAME}/{DATASET_SLUG}"
    result = api.dataset_create_version(
        folder=folder, version_notes=notes, quiet=False,
        convert_to_csv=False, delete_old_versions=False, dir_mode="skip",
    )

    status = getattr(result, "status", None)
    error = getattr(result, "error", None) or getattr(result, "errorMessage", None)
    if (status and str(status).lower() != "ok") or error:
        raise RuntimeError(f"Falha ao versionar dataset: {error or result}")

    print(f"Nova versao publicada: {dataset_url}")


def main():
    if not KAGGLE_USERNAME:
        sys.exit("Defina a variavel KAGGLE_USERNAME")

    base = os.path.dirname(os.path.abspath(__file__))
    upload_path = None
    try:
        upload_path, notes = prepare_upload_dir(base)
        api = authenticate()
        upload(api, upload_path, notes)
    except Exception as exc:
        sys.exit(str(exc))
    finally:
        if upload_path and os.path.exists(upload_path):
            shutil.rmtree(upload_path)


if __name__ == "__main__":
    main()
