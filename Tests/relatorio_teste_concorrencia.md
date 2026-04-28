# Relatório do teste de concorrência

- Data: 2026-04-28 14:33:19
- Servidor iniciado pelo script: sim
- Threads do cliente: 8
- Ciclos por thread: 3
- Requisições totais: 144
- Sucessos: 144
- Erros: 0
- Taxa de sucesso: 100.00%
- Duração total: 0.80s
- Latência média: 0.042s
- Mediana: 0.041s
- p95: 0.073s
- p99: 0.091s

## Distribuição por tipo

- DELETE: 24
- GET: 72
- POST: 24
- PUT: 24

## Observações

- O teste usa backup/restauração do arquivo `Tables/test.csv` para evitar sujeira na massa de dados.
- A fila do servidor e o `time.sleep(1)` por requisição limitam a vazão total, então o foco é medir contenção e estabilidade sob concorrência real.
- Se houve erro, ele aparece no resumo e no log de execução.
