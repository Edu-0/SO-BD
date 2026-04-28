# SO-BD

Projeto de banco de dados simplificado com cliente e servidor em Python, usando arquivos CSV como persistência. O sistema interpreta comandos SQL básicos no cliente, envia a requisição por socket para o servidor e executa as operações sobre as tabelas na pasta `Tables`.

## Funcionalidades

- `SELECT` com colunas específicas ou `*`
- `INSERT` com uma ou mais linhas
- `UPDATE` com `SET` e `WHERE`
- `DELETE` com `WHERE`
- Filtros com `AND` e `OR`
- Leitura e escrita de dados em arquivos `.csv`
- Registro das requisições em `log.txt`

## Estrutura do projeto

- `Client/client.py`: interface de linha de comando do cliente, envio das requisições e gravação de logs
- `Client/sql.py`: interpretador SQL e conversão para o formato usado pelo cliente
- `Server/server.py`: servidor socket responsável por receber e distribuir as operações
- `Server/methods.py`: implementação das operações de leitura, inserção, atualização e remoção nos CSVs
- `Tables/`: pasta com as tabelas usadas pelo sistema

## Requisitos

- Python 3.x
- Bibliotecas:
	- `pandas`
	- `numpy`

Se necessário, instale com:

```bash
pip install pandas numpy
```

## Como executar

1. Inicie o servidor:

```bash
python Server/server.py
```

2. Em outro terminal, execute o cliente:

```bash
python Client/client.py
```

3. Digite comandos SQL no cliente.

## Teste de concorrência

Para executar uma carga intensa com múltiplas threads, backup automático da tabela e geração de relatório, rode:

```bash
python stress_concurrency_test.py
```

Ou para um relatório com diferentes números de threads de Client:
```bash
python stress_concurrency_test.py --matrix 1 2 4 8 --workload-cycles 16
```

O script gera o relatório em `relatorio_teste_concorrencia.md` e adiciona um resumo da execução em `log.txt`. Também restaura `Tables/test.csv` ao estado original ao final do teste.

## Exemplos de uso

```sql
SELECT * FROM test WHERE id = 1
SELECT id, nome FROM test WHERE num > 50
INSERT INTO test (id, nome, num) VALUES (25, 'Maria', 88)
UPDATE test SET nome = 'Joao' WHERE id = 25
DELETE FROM test WHERE id = 25
```

## Observações

- O servidor escuta em `localhost:5000`.
- As tabelas devem estar em `Tables/` com extensão `.csv`.
- O arquivo `Tables/test.csv` serve como base de exemplo.
- O sistema suporta condições simples no `WHERE`, combinadas com `AND` e `OR`.

## Contribuição

Projeto desenvolvido em dupla.

## Créditos

- Eduardo José de Souza: desenvolvimento da parte de programação do cliente, servidor e banco
- Lucas Lopes Baroni: desenvolvimento do `sql.py` e da documentação escrita

## Referências

- Repositório original: https://github.com/Luc4sL0/SO-BD

