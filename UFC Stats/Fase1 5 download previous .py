"""
UFC Stats Pipeline - Fase 1.5 (Download Previous Dataset)

Baixa a versao publicada anteriormente do dataset UFC Stats no Kaggle.
Esse CSV serve como memoria historica entre execucoes: a Fase 5 vai
usar esses dados como base e atualizar apenas as lutas dos 20 eventos
mais recentes (processados pelas Fases 2-4).

Aborta o pipeline se o download falhar para evitar corromper o dataset.
"""

import os
import shutil
import sys

from kaggle.api.kaggle_api_extended import KaggleApi

DATASET_SLUG = "leandroiber/ufc-stats-complete-dataset"
SOURCE_CSV = "clean_ufc_dataset.csv"
TARGET_CSV = "previous_clean_ufc_dataset.csv"
DOWNLOAD_DIR = "kaggle_download"


def authenticate():
    try:
        api = KaggleApi()
        api.authenticate()
        return api
    except Exception as exc:
        sys.exit(f"[ERRO FATAL] Falha na autenticacao Kaggle: {exc}")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    download_path = os.path.join(base_dir, DOWNLOAD_DIR)

    if os.path.exists(download_path):
        shutil.rmtree(download_path)
    os.makedirs(download_path)

    api = authenticate()

    try:
        print(f"[INFO] Baixando dataset anterior: {DATASET_SLUG}")
        api.dataset_download_files(
            DATASET_SLUG, path=download_path, unzip=True, quiet=False
        )
    except Exception as exc:
        shutil.rmtree(download_path, ignore_errors=True)
        sys.exit(f"[ERRO FATAL] Falha no download do dataset anterior: {exc}")

    source_path = os.path.join(download_path, SOURCE_CSV)
    if not os.path.exists(source_path):
        shutil.rmtree(download_path, ignore_errors=True)
        sys.exit(f"[ERRO FATAL] {SOURCE_CSV} nao encontrado apos download.")

    target_path = os.path.join(base_dir, TARGET_CSV)
    shutil.copy(source_path, target_path)
    shutil.rmtree(download_path, ignore_errors=True)

    print(f"[OK] Versao anterior salva em: {target_path}")


if __name__ == "__main__":
    main()
