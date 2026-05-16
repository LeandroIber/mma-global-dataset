import subprocess
import sys
from pathlib import Path


def main():
    pasta_projeto = Path(__file__).resolve().parent

    fases = [
        "fase1_events.py",
        "fase2_fights.py",
        "fase3_stats.py",
        "fase4_fighters.py",
        "fase5_transform.py",
        "fase6_load.py"
    ]

    print("=== INICIANDO PIPELINE UFC STATS ===")

    for fase in fases:
        print(f"\n{'='*50}\n▶ Executando: {fase}\n{'='*50}")

        caminho_fase = pasta_projeto / fase

        resultado = subprocess.run([sys.executable, str(caminho_fase)])

        if resultado.returncode != 0:
            print(f"\n[ERRO FATAL] A pipeline falhou durante a execução de {fase}.")
            sys.exit(resultado.returncode)

    print("\n[SUCESSO] Todas as fases da pipeline foram concluídas!")


if __name__ == "__main__":
    main()
