# 📊 Pipeline Analítico SQL — Setor de Seguros

Projeto de SQL analítico simulando o contexto de uma consultoria de TI
para o **setor financeiro e de seguros**, demonstrando CTEs encadeadas,
window functions e construção de pipelines analíticos para KPIs de negócio.

## 🎯 Contexto de negócio

Seguradoras precisam monitorar continuamente:
- **Sinistralidade**: quanto pagam em sinistros vs quanto arrecadam em prêmios
- **Risco de carteira**: quais clientes concentram maior risco
- **Saúde financeira**: apólices em risco de lapso por inadimplência
- **LTV de clientes**: quais clientes geram mais receita ao longo do tempo

Este pipeline responde a essas perguntas com SQL puro, rodando via **DuckDB**
diretamente sobre arquivos CSV — sem necessidade de servidor de banco de dados.

## 🧠 O que este projeto demonstra

- **CTEs encadeadas**: decomposição de queries complexas em etapas legíveis e reutilizáveis
- **Window functions**:
  - `RANK()` e `NTILE()` para ranking e quartil de risco de clientes
  - `AVG() OVER (ROWS BETWEEN ...)` para média móvel de 3 meses
  - `LAG()` para variação mês a mês de sinistros
  - `SUM() OVER (PARTITION BY ...)` para acumulado por ano e receita em risco
  - `PERCENT_RANK()` para percentil de LTV dentro do segmento
- **Pipeline analítico**: 5 queries encadeadas cobrindo sinistralidade, risco, série temporal, qualidade de dados e LTV

## 🛠️ Stack

`Python` · `DuckDB` · `SQL` · `Pandas`

## 📋 Queries do pipeline

| # | Query | KPI calculado | Técnicas SQL |
|---|-------|--------------|-------------|
| 1 | Sinistralidade por ramo | % sinistros pagos / prêmios arrecadados | CTE, LEFT JOIN, NULLIF |
| 2 | Ranking de risco de clientes | Score composto de risco, sinistros e inadimplência | 3 CTEs encadeadas, RANK(), NTILE() |
| 3 | Evolução mensal de sinistros | Série temporal com média móvel e variação | AVG OVER ROWS, LAG() |
| 4 | Apólices em risco de lapso | Dias sem pagamento + classificação de risco | CTE, DATE_DIFF, CASE, SUM OVER |
| 5 | LTV vs média do segmento | Lifetime value + desvio da média + percentil | PERCENT_RANK(), AVG OVER PARTITION |

## Passo a passo (do zero)

```
python -m pip install -r requirements.txt
python generate_data.py
python analysis.py
```

Isso gera 4 CSVs sintéticos (500 clientes, 800 apólices, 400 sinistros,
2000 pagamentos) e executa o pipeline completo, imprimindo os resultados
de cada query no terminal.

## Estrutura dos arquivos

| Arquivo | Descrição |
|---|---|
| `generate_data.py` | Gera os CSVs sintéticos de clientes, apólices, sinistros e pagamentos |
| `queries.sql` | Pipeline SQL completo com comentários explicativos |
| `analysis.py` | Executa as queries via DuckDB e imprime os resultados |
| `requirements.txt` | Dependências do projeto |

## Problemas comuns

**DuckDB não instalado** → `python -m pip install duckdb pandas`
