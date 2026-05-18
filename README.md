# MMA Global Dataset

Pipeline ETL automatizado que raspa, padroniza e publica datasets das principais organizações de MMA do mundo. Cada organização tem seu próprio módulo, mas todos seguem a mesma arquitetura de 6 fases e exportam o dataset final para o Kaggle.

## Organizações cobertas

| Organização   | Pasta                  | Dataset Kaggle                                                                |
| ------------- | ---------------------- | ----------------------------------------------------------------------------- |
| UFC           | `UFC Stats/`           | https://www.kaggle.com/datasets/leandroiber/ufc-stats-complete-dataset        |
| Bellator      | `Bellator Stats/`      | https://www.kaggle.com/datasets/leandroiber/bellator-mma-complete-dataset     |
| PFL           | `PFL Stats/`           | https://www.kaggle.com/datasets/leandroiber/pfl-complete-dataset              |
| Rizin         | `Rizin Stats/`         | https://www.kaggle.com/datasets/leandroiber/rizin-mma-dataset                 |
| ACA           | `Aca Stats/`           | https://www.kaggle.com/datasets/leandroiber/aca-mma-dataset                   |
| KSW           | `Ksw Stats/`           | https://www.kaggle.com/datasets/leandroiber/ksw-mma-dataset                   |
| Oktagon       | `Oktagon Stats/`       | https://www.kaggle.com/datasets/leandroiber/oktagon-mma-dataset               |
| Cage Warriors | `Cage Warrios Stats/`  | https://www.kaggle.com/datasets/leandroiber/cage-warriors-mma-dataset         |
| LFA           | `LFA Stats/`           | https://www.kaggle.com/datasets/leandroiber/lfa-mma-dataset                   |
| Jungle Fight  | `Jungle Fight Stats/`  | https://www.kaggle.com/datasets/leandroiber/jungle-fight-complete-dataset     |

Todos os datasets usam sistema métrico (kg, cm), independente da unidade original da fonte.

## Arquitetura

Cada pasta de organização contém um pipeline próprio dividido em 6 fases, cada uma persistindo seu resultado num CSV/JSONL intermediário:

* `fase1_events.py`: lista de eventos concluídos.
* `fase2_fights.py`: visita cada evento e coleta URLs das lutas e dos lutadores.
* `fase3_stats.py`: estatísticas Fight Totals (KD, Sig.str, Td, Ctrl) por luta.
* `fase4_fighters.py`: biometria dos lutadores. Roda em paralelo (5 workers) e mantém checkpoint em JSONL, então pode ser interrompido e retomado.
* `fase5_transform.py`: joins relacionais entre os 4 datasets brutos e conversão de unidades imperiais para métricas.
* `fase6_load.py`: upload do CSV consolidado pro Kaggle (cria na primeira execução, versiona daí em diante).

O módulo `utils.py` de cada pasta concentra o cliente HTTP (com retry exponencial) e a normalização de URL, evitando duplicação entre fases. O `run_pipeline.py` é um wrapper que roda as fases em sequência.

O schema das colunas pode variar entre organizações porque cada fonte expõe os dados de forma diferente. A padronização para sistema métrico e o pipeline de 6 fases é o que se mantém igual em todas.

## Como rodar

Dependências:

```
pip install -r requirements.txt
```

Antes de rodar a Fase 6, configure as credenciais do Kaggle. Baixe o `kaggle.json` em https://www.kaggle.com/settings e coloque em:

* Linux/Mac: `~/.kaggle/kaggle.json`
* Windows: `%USERPROFILE%\.kaggle\kaggle.json`

E exporte seu usuário:

```
export KAGGLE_USERNAME=seu_usuario
```

Pipeline completo de uma organização (entre na pasta correspondente):

```
cd "UFC Stats"
python run_pipeline.py
```

Ou rode fases individualmente, respeitando a ordem. Cada fase consome o output da anterior.

## Atualização

Os datasets são atualizados semanalmente.

## Licença

MIT, veja `LICENSE`.
