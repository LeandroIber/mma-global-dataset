import subprocess
import sys
import os

def main():
    # Caminho fixo informado por você (o 'r' antes das aspas é importante no Windows)
    pasta_projeto = r"C:\Users\Leandro\Desktop\UFC Stats\2.0"

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
        
        caminho_fase = os.path.join(pasta_projeto, fase)
        
        # Executa usando o caminho absoluto que você definiu
        resultado = subprocess.run([sys.executable, caminho_fase])
        
        if resultado.returncode != 0:
            print(f"\n[ERRO FATAL] A pipeline falhou durante a execução de {fase}.")
            sys.exit(resultado.returncode)

    print("\n[SUCESSO] Todas as fases da pipeline foram concluídas!")

if __name__ == "__main__":
    main()