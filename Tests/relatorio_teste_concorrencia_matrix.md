# Relatório comparativo de concorrência

- Data: 2026-04-28 14:34:02
- Baseline de 1 thread: 1.44s
- Requisições totais por rodada: 96

| Threads | Ciclos por thread | Requisições | Duração | Req/s | Speedup | Eficiência |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 16 | 96 | 1.44s | 66.70 | 1.00x | 1.00 |
| 2 | 8 | 96 | 0.87s | 110.00 | 1.65x | 0.82 |
| 4 | 4 | 96 | 0.59s | 161.49 | 2.42x | 0.61 |
| 8 | 2 | 96 | 0.48s | 200.82 | 3.01x | 0.38 |

## Interpretação

- Speedup acima de 1x indica ganho em relação à execução com 1 thread no mesmo volume total de trabalho.
- Req/s ajuda a ver se o sistema está realmente processando mais requisições por segundo.
- Eficiência é o speedup dividido pelo número de threads e mostra o quanto cada thread contribui.
- O gargalo principal inclui o lock por operação no CSV.
