"""
UFC Stats Pipeline - Fase 6 (Load)

Faz o upload do clean_ufc_dataset.csv como dataset publico no Kaggle.
Sobe uma nova versao com notas dinamicas a cada execucao.
"""

import datetime
import json
import os
import shutil
import sys

import pandas as pd
from kaggle.api.kaggle_api_extended import KaggleApi

KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME", "leandroiber")
DATASET_SLUG = "ufc-stats-complete-dataset"
DATASET_TITLE = "UFC Stats Complete Dataset (Metric System)"

CSV_FILE = "clean_ufc_dataset.csv"
UPLOAD_DIR = "kaggle_upload"
METADATA_FILE = "dataset-metadata.json"


def check_username() -> None:
    if KAGGLE_USERNAME in ("SEU_USUARIO_KAGGLE", "", None):
        print("=" * 72)
        print("[ERRO] Voce precisa definir a variavel KAGGLE_USERNAME.")
        print("=" * 72)
        sys.exit(1)


def generate_version_notes(csv_path: str) -> str:
    try:
        df = pd.read_csv(csv_path)
        rows = len(df)
        today = datetime.datetime.now().strftime("%d/%m/%Y")
        return f"Atualização automática de {today}: Dataset consolidado com {rows} lutas registradas."
    except Exception:
        return "Atualizacao automatica da pipeline ETL"


def prepare_upload_dir() -> tuple[str, str]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho_csv_real = os.path.join(base_dir, CSV_FILE)

    if not os.path.exists(caminho_csv_real):
        raise FileNotFoundError(
            f"\n[ERRO] Arquivo nao encontrado: {caminho_csv_real}\n"
            "Certifique-se de que a Fase 5 salvou o arquivo nesta pasta."
        )

    upload_path = os.path.join(base_dir, UPLOAD_DIR)
    if os.path.exists(upload_path):
        shutil.rmtree(upload_path)
    os.makedirs(upload_path)

    dest_csv = os.path.join(upload_path, CSV_FILE)
    shutil.copy(caminho_csv_real, dest_csv)
    print(f"[OK] CSV movido para area de stage: {dest_csv}")

    metadata = {
        "title": DATASET_TITLE,
        "id": f"{KAGGLE_USERNAME}/{DATASET_SLUG}",
        "licenses": [{"name": "CC0-1.0"}],
        "description": "Dataset completo do UFC Stats. Contém eventos, resultados, estatísticas e biometria padronizada para o sistema métrico."
    }
    metadata_path = os.path.join(upload_path, METADATA_FILE)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    notes = generate_version_notes(caminho_csv_real)
    print(f"[OK] Metadados gerados com a nota: '{notes}'")

    return upload_path, notes


def authenticate_kaggle() -> KaggleApi:
    try:
        api = KaggleApi()
        api.authenticate()
        print("[OK] Autenticacao no Kaggle bem-sucedida.")
        return api
    except Exception as exc:
        print("\n[ERRO FATAL] Falha ao autenticar na API do Kaggle.")
        print("Verifique as variaveis de ambiente KAGGLE_USERNAME e KAGGLE_KEY,")
        print("ou o arquivo ~/.kaggle/kaggle.json.")
        print(f"Detalhe: {exc}")
        sys.exit(1)


def upload_dataset(api: KaggleApi, folder: str, version_notes: str) -> None:
    dataset_url = f"https://www.kaggle.com/datasets/{KAGGLE_USERNAME}/{DATASET_SLUG}"

    print("\n[INFO] Publicando nova versao do dataset...")
    result = api.dataset_create_version(
        folder=folder,
        version_notes=version_notes,
        quiet=False,
        convert_to_csv=False,
        delete_old_versions=False,
        dir_mode="skip",
    )

    status = getattr(result, "status", None)
    error = getattr(result, "error", None) or getattr(result, "errorMessage", None)
    if (status and str(status).lower() != "ok") or error:
        raise RuntimeError(f"Falha ao versionar dataset: {error or result}")

    print(f"\n[OK] Nova versao publicada com sucesso!")
    print(f"     Acesse: {dataset_url}")


def main() -> None:
    print("=== UFC Stats Pipeline - Fase 6 (Load) ===\n")
    check_username()

    try:
        upload_dir, notes = prepare_upload_dir()
        api = authenticate_kaggle()
        upload_dataset(api, upload_dir, notes)
    except Exception as e:
        print(f"[ERRO] Falha na Fase 6: {e}")
        sys.exit(1)
    finally:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        upload_path = os.path.join(base_dir, UPLOAD_DIR)
        if os.path.exists(upload_path):
            shutil.rmtree(upload_path)
            print(f"\n[INFO] Pasta temporaria de upload removida.")


if __name__ == "__main__":
    main()
