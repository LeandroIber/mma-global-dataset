# Web scraping MMA Global Dataset, Analysis of datasets and observed results

Pipeline ETL automatizado que raspa, padroniza e publica datasets das principais organizações de MMA do mundo no kaggle. Cada organização tem seu próprio módulo, seu script adaptado e uma análise detalhada.

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

Cada pasta de organização contém um pipeline próprio dividido em 5 ou 6 fases, cada uma persistindo seu resultado num CSV/JSONL intermediário:

* `fase1_events.py`: lista de eventos (cards).
* `fase2_fights.py`: visita cada evento e coleta URLs das lutas e dos lutadores.
* `fase3_stats.py`: estatísticas Fight Totals (KD, Sig.str, Td, Ctrl) por luta.
* `fase4_fighters.py`: biometria dos lutadores.
* `fase5_transform.py`: joins relacionais entre os 4 datasets brutos e conversão de unidades imperiais para métricas (UFC por exemplo, usa sistema imperial, Organizações brasileiras como Jungle Fight usam sistema métrico).
* `fase6_load.py`: upload do CSV consolidado pro Kaggle (Exporta o dataset diretamente para o Kaggle).

O módulo `utils.py` de cada pasta concentra o cliente HTTP (com retry exponencial) e a normalização de URL, evitando duplicação entre fases. O `run_pipeline.py` é um wrapper que roda as fases em sequência.

O schema das colunas pode variar entre organizações porque cada fonte expõe os dados de forma diferente. A padronização para sistema métrico e o pipeline de 6 fases é o que se mantém igual em todas.

## Como rodar

Dependências:

```
pip install -r requirements.txt
```

Antes de rodar a Fase 5, configure as credenciais do Kaggle. Baixe o `kaggle.json` em https://www.kaggle.com/settings e coloque em:

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

## Resultado final > gráficos

Cada organização possui uma análise visual padronizada cobrindo evolução
temporal, composição de desfechos e atributos físicos por categoria.

| Organização   | Análise                                              | Notebook Kaggle                                                                              |
| ------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| UFC           | A Historical Analysis of the UFC Using Data          | https://www.kaggle.com/code/leandroiber/a-historical-analysis-of-the-ufc-using-data          |
| Bellator      | Historical Analysis of the Bellator MMA              | https://www.kaggle.com/code/leandroiber/historical-analysis-of-the-bellator-mma              |
| PFL           | Historical Analysis of the PFL Using Official Data   | https://www.kaggle.com/code/leandroiber/historical-analysis-of-the-pfl-using-official-data   |
| Rizin         | Historical Analysis of the Rizin MMA                 | https://www.kaggle.com/code/leandroiber/historical-analysis-of-the-rizin-mma                 |
| ACA           | Historical Analysis of the ACA Using Official Data   | https://www.kaggle.com/code/leandroiber/historical-analysis-of-the-aca-using-official-data   |
| KSW           | Historical Analysis of the KSW Using Official Data   | https://www.kaggle.com/code/leandroiber/historical-analysis-of-the-ksw-using-official-data   |
| Oktagon       | Historical Analysis of the Oktagon                   | https://www.kaggle.com/code/leandroiber/historical-analysis-of-the-oktagon                   |
| Cage Warriors | Historical Analysis of the CW Using Official Data    | https://www.kaggle.com/code/leandroiber/historical-analysis-of-the-cw-using-official-data    |
| LFA           | Historical Analysis of the LFA Using Official Data   | https://www.kaggle.com/code/leandroiber/historical-analysis-of-the-lfa-using-official-data   |
| Jungle Fight  | Historical Analysis of the Jungle Fight MMA          | https://www.kaggle.com/code/leandroiber/historical-analysis-of-the-jungle-fight-mma          |

Dentro da pasta de cada organização tem um PDF com a análise final.

### Duração das lutas ao longo do tempo

<img width="676" height="379" alt="image" src="https://github.com/user-attachments/assets/ab6347fb-f552-42e2-bcab-4b843b846033" />


Série temporal da mediana e média de duração das lutas por ano. Separa
lutas regulares (non-title) de lutas de cinturão (title fights) para
identificar regimes distintos e efeitos de limites regulatórios.

### Distribuição de desfechos por ano

<img width="666" height="351" alt="image" src="https://github.com/user-attachments/assets/8c30072f-72b4-489a-8cff-a62d80ad5a21" />


Barras empilhadas com a proporção anual de cada tipo de desfecho (KO/TKO,
finalização, decisão). Permite identificar mudanças na composição de
resultados ao longo das eras da organização.

### Altura média por categoria de peso

<img width="670" height="461" alt="image" src="https://github.com/user-attachments/assets/e4e76657-0e3a-478d-8431-b0ce2e0440eb" />


Média de altura agregada por categoria, em centímetros. Serve como baseline
descritiva e suporta os testes de vantagem física subsequentes.

### Taxa de vitórias por vantagem de altura

<img width="669" height="469" alt="image" src="https://github.com/user-attachments/assets/1c23b749-d5c3-42a8-9e3b-5414977c41f6" />


Teste de proporção da taxa de vitórias do lutador mais alto por categoria.


## Licença

MIT, veja `LICENSE`.
