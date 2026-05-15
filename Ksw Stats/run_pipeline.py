"""Orquestrador do pipeline Sherdog/LFA."""
import os
import subprocess
import sys

FASES = [
    "fase1_events.py",
    "fase2_fights.py",
    "fase3_fighters.py",
    "fase4_transform.py",
    "fase5_load.py",
]


def main() -> None:
    base = os.path.dirname(os.path.abspath(__file__))

    for fase in FASES:
        print(f"\n>>> {fase}")
        rc = subprocess.run([sys.executable, os.path.join(base, fase)]).returncode
        if rc != 0:
            sys.exit(f"[FATAL] {fase} falhou (rc={rc})")

    print("\nPipeline concluido.")


if __name__ == "__main__":
    main()
