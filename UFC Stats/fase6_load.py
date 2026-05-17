import datetime
import json
import os
import shutil
import sys

import pandas as pd
from kaggle.api.kaggle_api_extended import KaggleApi

KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME", "leandroiber")
DATASET_SLUG = "ufc-stats-complete-dataset"

CSV_FILE = "clean_ufc_dataset.csv"
UPLOAD_DIR = "kaggle_upload"

DEFAULT_KEYWORDS = [
    "sports",
    "mma",
    "combat sports",
    "data analytics",
    "data visualization",
]


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
        return (
            f"Atualização automática de {today}: "
            f"Dataset consolidado com {rows} lutas registradas."
        )
    except Exception:
        return "Atualizacao automatica da pipeline ETL"


def extract_error(result):
    if result is None:
        return None
    return getattr(result, "error", None) or getattr(result, "errorMessage", None)


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

    notes = generate_version_notes(caminho_csv_real)
    print(f"[OK] Nota de versao gerada: '{notes}'")

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


def prepare_metadata(api: KaggleApi, folder: str) -> dict:
    dataset_handle = f"{KAGGLE_USERNAME}/{DATASET_SLUG}"
    print(f"\n[INFO] Baixando metadados existentes de {dataset_handle}...")
    api.dataset_metadata(dataset_handle, path=folder)

    metadata_path = os.path.join(folder, "dataset-metadata.json")
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    metadata["id"] = dataset_handle

    existing_keywords = metadata.get("keywords") or []
    if not existing_keywords:
        metadata["keywords"] = DEFAULT_KEYWORDS
        print(f"[INFO] Keywords vazias no Kaggle. Aplicando defaults: {DEFAULT_KEYWORDS}")
    else:
        print(f"[INFO] Keywords existentes preservadas: {existing_keywords}")

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("[OK] Metadata preparada para upload.")
    return metadata


def create_new_version(api: KaggleApi, folder: str, version_notes: str) -> None:
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
    error = extract_error(result)
    if (status and str(status).lower() not in ("ok", "none")) or error:
        raise RuntimeError(f"Falha ao versionar dataset: {error or result}")

    print("[OK] Nova versao publicada com sucesso.")


def update_metadata(api: KaggleApi, folder: str) -> None:
    dataset_handle = f"{KAGGLE_USERNAME}/{DATASET_SLUG}"
    print("\n[INFO] Atualizando metadata do dataset (tags, descricao, ...)")

    update_fn = getattr(api, "dataset_metadata_update", None)
    if update_fn is None:
        print(
            "[AVISO] A versao instalada do `kaggle` nao expoe "
            "`dataset_metadata_update`. Atualize: pip install -U kaggle"
        )
        return

    try:
        result = update_fn(dataset_handle, folder)
    except Exception as exc:
        print(f"[AVISO] dataset_metadata_update lancou excecao: {exc}")
        return

    error = extract_error(result)
    if error:
        print(f"[AVISO] Falha ao atualizar metadata: {error}")
    else:
        print("[OK] Metadata (tags incluidas) atualizada com sucesso.")


def main() -> None:
    print("=== UFC Stats Pipeline - Fase 6 (Load) ===\n")
    check_username()

    dataset_url = f"https://www.kaggle.com/datasets/{KAGGLE_USERNAME}/{DATASET_SLUG}"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    upload_path = os.path.join(base_dir, UPLOAD_DIR)

    try:
        upload_dir, notes = prepare_upload_dir()
        api = authenticate_kaggle()
        prepare_metadata(api, upload_dir)
        create_new_version(api, upload_dir, notes)
        update_metadata(api, upload_dir)
        print(f"\n[OK] Pipeline concluida. Acesse: {dataset_url}")
    except Exception as e:
        print(f"[ERRO] Falha na Fase 6: {e}")
        sys.exit(1)
    finally:
        if os.path.exists(upload_path):
            shutil.rmtree(upload_path)
            print("\n[INFO] Pasta temporaria de upload removida.")


if __name__ == "__main__":
    main()
