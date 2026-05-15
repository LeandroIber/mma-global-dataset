"""
UFC Stats Pipeline - Fase 6 (Load)

Faz o upload do clean_ufc_dataset.csv como dataset publico no Kaggle.
Cria o dataset na primeira execucao; nas seguintes, sobe uma nova versao com
notas dinamicas.
"""

import datetime
import json
import os
import shutil
import sys

import pandas as pd
from kaggle.api.kaggle_api_extended import KaggleApi

# ============================================================================
# Configuracao
# ============================================================================
KAGGLE_USERNAME = "leandroiber"
DATASET_SLUG = "ufc-stats-complete-dataset"
DATASET_TITLE = "UFC Stats Complete Dataset (Metric System)"

# Arquivos e diretorios
CSV_FILE = "clean_ufc_dataset.csv"
UPLOAD_DIR = "kaggle_upload"
METADATA_FILE = "dataset-metadata.json"


# ============================================================================
# Validacao previa
# ============================================================================

def check_username() -> None:
    """Aborta se o placeholder do username ainda estiver no codigo."""
    if KAGGLE_USERNAME in ("SEU_USUARIO_KAGGLE", "", None):
        print("=" * 72)
        print("[ERRO] Voce precisa editar este script antes de rodar:")
        print("       Defina a variavel KAGGLE_USERNAME (proximo ao topo)")
        print("=" * 72)
        sys.exit(1)


# ============================================================================
# Preparacao da pasta de upload e Metadados
# ============================================================================

def generate_version_notes(csv_path: str) -> str:
    """Gera uma nota de versao com a data atual e a contagem de linhas."""
    try:
        df = pd.read_csv(csv_path)
        rows = len(df)
        today = datetime.datetime.now().strftime("%d/%m/%Y")
        return f"Atualização automática de {today}: Dataset consolidado com {rows} lutas registradas."
    except Exception:
        return "Atualizacao automatica da pipeline ETL"


def prepare_upload_dir() -> tuple[str, str]:
    """Cria a pasta de upload garantindo o caminho absoluto do projeto."""
    
    # 1. Localiza a pasta onde este script está (Desktop/UFC Stats/2.0)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho_csv_real = os.path.join(base_dir, CSV_FILE)

    # 2. Verifica se o CSV realmente existe na pasta do Desktop
    if not os.path.exists(caminho_csv_real):
        raise FileNotFoundError(
            f"\n[ERRO] Arquivo nao encontrado: {caminho_csv_real}\n"
            "Certifique-se de que a Fase 5 salvou o arquivo nesta pasta."
        )

    # 3. Define o caminho da pasta temporaria de upload dentro do projeto
    upload_path = os.path.join(base_dir, UPLOAD_DIR)

    # Limpa a pasta se tiver sobrado de uma execucao anterior
    if os.path.exists(upload_path):
        shutil.rmtree(upload_path)
    os.makedirs(upload_path)

    # 4. Copia o CSV para dentro da pasta de upload
    dest_csv = os.path.join(upload_path, CSV_FILE)
    shutil.copy(caminho_csv_real, dest_csv)
    print(f"[OK] CSV movido para area de stage: {dest_csv}")

    # 5. Gera o dataset-metadata.json para o Kaggle
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


# ============================================================================
# Autenticacao e Upload
# ============================================================================

def authenticate_kaggle() -> KaggleApi:
    """Inicializa e autentica a Kaggle API."""
    try:
        api = KaggleApi()
        api.authenticate()
        print("[OK] Autenticacao no Kaggle bem-sucedida.")
        return api
    except Exception as exc:
        print("\n[ERRO FATAL] Falha ao autenticar na API do Kaggle.")
        print("Verifique se o arquivo kaggle.json esta na pasta: C:\\Users\\Leandro\\.kaggle\\kaggle.json")
        print(f"Detalhe: {exc}")
        sys.exit(1)


def upload_dataset(api: KaggleApi, folder: str, version_notes: str) -> None:
    """Tenta criar dataset novo; se ja existir, sobe uma versao incremental."""
    dataset_url = f"https://www.kaggle.com/datasets/{KAGGLE_USERNAME}/{DATASET_SLUG}"

    try:
        print("\n[INFO] Tentando criar dataset novo...")
        api.dataset_create_new(
            folder=folder,
            public=True,
            quiet=False,
            convert_to_csv=False,
            dir_mode="skip",
        )
        print(f"\n[OK] Dataset inedito criado com sucesso!")
        print(f"     Acesse: {dataset_url}")

    except Exception:
        print(f"[INFO] O dataset '{DATASET_SLUG}' ja existe. Subindo nova versao...")

        api.dataset_create_version(
            folder=folder,
            version_notes=version_notes,
            quiet=False,
            convert_to_csv=False,
            delete_old_versions=False,
            dir_mode="skip",
        )
        print(f"\n[OK] Nova versao publicada com sucesso!")
        print(f"     Acesse: {dataset_url}")


# ============================================================================
# Orquestracao
# ============================================================================

def main() -> None:
    """Pipeline da Fase 6."""
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
        # Limpeza: Deleta a pasta temporaria apos o processo
        base_dir = os.path.dirname(os.path.abspath(__file__))
        upload_path = os.path.join(base_dir, UPLOAD_DIR)
        if os.path.exists(upload_path):
            shutil.rmtree(upload_path)
            print(f"\n[INFO] Pasta temporaria de upload removida.")

if __name__ == "__main__":
    main()