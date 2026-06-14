"""
Executa o pipeline analítico de sinistros de seguros usando DuckDB.

DuckDB lê os CSVs diretamente e executa SQL analítico com
CTEs e window functions, sem necessidade de servidor de banco de dados.
"""

import duckdb
import pandas as pd

# Conecta ao DuckDB (em memória)
con = duckdb.connect()

# Carrega os CSVs como tabelas
con.execute("CREATE TABLE clientes  AS SELECT * FROM read_csv_auto('clientes.csv')")
con.execute("CREATE TABLE apolices  AS SELECT * FROM read_csv_auto('apolices.csv')")
con.execute("CREATE TABLE sinistros AS SELECT * FROM read_csv_auto('sinistros.csv')")
con.execute("CREATE TABLE pagamentos AS SELECT * FROM read_csv_auto('pagamentos.csv')")

print("Tabelas carregadas com sucesso!\n")

# ============================================================
# 1. SINISTRALIDADE POR RAMO
# ============================================================
print("=" * 60)
print("1. SINISTRALIDADE POR RAMO (%)")
print("=" * 60)

query1 = """
WITH premios_por_ramo AS (
    SELECT
        a.ramo,
        COUNT(DISTINCT a.apolice_id)      AS total_apolices,
        SUM(a.premio_anual)               AS total_premios
    FROM apolices a
    WHERE a.status = 'Ativa'
    GROUP BY a.ramo
),
sinistros_pagos_por_ramo AS (
    SELECT
        a.ramo,
        COUNT(s.sinistro_id)              AS total_sinistros,
        SUM(s.valor_pago)                 AS total_pago
    FROM sinistros s
    JOIN apolices a ON s.apolice_id = a.apolice_id
    WHERE s.status = 'Pago'
    GROUP BY a.ramo
)
SELECT
    p.ramo,
    p.total_apolices,
    ROUND(p.total_premios, 2)             AS total_premios,
    COALESCE(s.total_sinistros, 0)        AS total_sinistros,
    ROUND(COALESCE(s.total_pago, 0), 2)   AS total_pago,
    ROUND(
        COALESCE(s.total_pago, 0) / NULLIF(p.total_premios, 0) * 100, 2
    )                                     AS sinistralidade_pct
FROM premios_por_ramo p
LEFT JOIN sinistros_pagos_por_ramo s ON p.ramo = s.ramo
ORDER BY sinistralidade_pct DESC
"""
df1 = con.execute(query1).df()
print(df1.to_string(index=False))

# ============================================================
# 2. TOP 10 CLIENTES POR RISCO
# ============================================================
print("\n" + "=" * 60)
print("2. TOP 10 CLIENTES POR RISCO (window functions)")
print("=" * 60)

query2 = """
WITH sinistros_por_cliente AS (
    SELECT
        a.cliente_id,
        COUNT(s.sinistro_id)              AS qtd_sinistros,
        SUM(s.valor_pago)                 AS total_sinistros_pagos
    FROM sinistros s
    JOIN apolices a ON s.apolice_id = a.apolice_id
    GROUP BY a.cliente_id
),
inadimplencia_por_cliente AS (
    SELECT
        a.cliente_id,
        COUNT(*) FILTER (WHERE p.status = 'Inadimplente') AS pgtos_inadimplentes,
        COUNT(*)                                           AS total_pagamentos
    FROM pagamentos p
    JOIN apolices a ON p.apolice_id = a.apolice_id
    GROUP BY a.cliente_id
),
base_risco AS (
    SELECT
        c.cliente_id,
        c.nome,
        c.estado,
        c.segmento,
        c.score_risco,
        COALESCE(s.qtd_sinistros, 0)           AS qtd_sinistros,
        COALESCE(s.total_sinistros_pagos, 0)   AS total_sinistros_pagos,
        COALESCE(i.pgtos_inadimplentes, 0)     AS pgtos_inadimplentes
    FROM clientes c
    LEFT JOIN sinistros_por_cliente s ON c.cliente_id = s.cliente_id
    LEFT JOIN inadimplencia_por_cliente i ON c.cliente_id = i.cliente_id
)
SELECT
    cliente_id, nome, estado, segmento, score_risco,
    qtd_sinistros,
    ROUND(total_sinistros_pagos, 2)        AS total_sinistros_pagos,
    pgtos_inadimplentes,
    RANK() OVER (ORDER BY score_risco DESC, qtd_sinistros DESC) AS rank_risco,
    NTILE(4) OVER (ORDER BY score_risco DESC)                   AS quartil_risco
FROM base_risco
ORDER BY rank_risco
LIMIT 10
"""
df2 = con.execute(query2).df()
print(df2.to_string(index=False))

# ============================================================
# 3. EVOLUÇÃO MENSAL COM MÉDIA MÓVEL E LAG
# ============================================================
print("\n" + "=" * 60)
print("3. EVOLUÇÃO MENSAL DE SINISTROS (últimos 12 meses)")
print("=" * 60)

query3 = """
WITH sinistros_mensais AS (
    SELECT
        DATE_TRUNC('month', data_ocorrencia)  AS mes,
        COUNT(*)                              AS qtd_sinistros,
        ROUND(SUM(valor_pago), 2)             AS valor_total_pago
    FROM sinistros
    WHERE status = 'Pago'
    GROUP BY DATE_TRUNC('month', data_ocorrencia)
)
SELECT
    STRFTIME(mes, '%Y-%m')                     AS mes,
    qtd_sinistros,
    valor_total_pago,
    ROUND(AVG(qtd_sinistros) OVER (
        ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2)                                      AS media_movel_3m,
    LAG(qtd_sinistros) OVER (ORDER BY mes)     AS sinistros_mes_anterior,
    qtd_sinistros - LAG(qtd_sinistros) OVER (ORDER BY mes) AS variacao_qtd
FROM sinistros_mensais
ORDER BY mes DESC
LIMIT 12
"""
df3 = con.execute(query3).df()
print(df3.to_string(index=False))

# ============================================================
# 4. APÓLICES EM RISCO DE LAPSO
# ============================================================
print("\n" + "=" * 60)
print("4. APÓLICES EM RISCO DE LAPSO (sem pagamento recente)")
print("=" * 60)

query4 = """
WITH ultimo_pagamento AS (
    SELECT
        apolice_id,
        MAX(data_vencimento)   AS ultimo_pgto,
        COUNT(*)               AS total_pgtos,
        SUM(CASE WHEN status = 'Inadimplente' THEN 1 ELSE 0 END) AS pgtos_inadimplentes
    FROM pagamentos
    GROUP BY apolice_id
),
apolices_em_risco AS (
    SELECT
        a.apolice_id, a.cliente_id, a.ramo,
        ROUND(a.premio_anual, 2)  AS premio_anual,
        u.ultimo_pgto,
        CAST(DATE_DIFF('day', u.ultimo_pgto, CURRENT_DATE) AS INTEGER) AS dias_sem_pagamento,
        u.pgtos_inadimplentes
    FROM apolices a
    LEFT JOIN ultimo_pagamento u ON a.apolice_id = u.apolice_id
    WHERE a.status = 'Ativa'
)
SELECT
    apolice_id, cliente_id, ramo, premio_anual,
    dias_sem_pagamento, pgtos_inadimplentes,
    CASE
        WHEN dias_sem_pagamento > 180 THEN 'Crítico'
        WHEN dias_sem_pagamento > 90  THEN 'Alto'
        ELSE 'Moderado'
    END AS risco_lapso
FROM apolices_em_risco
WHERE dias_sem_pagamento > 60
ORDER BY dias_sem_pagamento DESC
LIMIT 10
"""
df4 = con.execute(query4).df()
print(df4.to_string(index=False))

# ============================================================
# 5. LTV POR SEGMENTO
# ============================================================
print("\n" + "=" * 60)
print("5. TOP 10 CLIENTES POR LTV vs MÉDIA DO SEGMENTO")
print("=" * 60)

query5 = """
WITH premios_cliente AS (
    SELECT
        a.cliente_id,
        COUNT(DISTINCT a.apolice_id)  AS total_apolices,
        SUM(a.premio_anual)           AS receita_total
    FROM apolices a
    WHERE a.status IN ('Ativa', 'Vencida')
    GROUP BY a.cliente_id
)
SELECT
    c.cliente_id, c.segmento, c.estado,
    p.total_apolices,
    ROUND(p.receita_total, 2)           AS ltv_estimado,
    ROUND(p.receita_total / NULLIF(p.total_apolices, 0), 2) AS ticket_medio,
    ROUND(AVG(p.receita_total) OVER (PARTITION BY c.segmento), 2) AS media_ltv_segmento,
    ROUND(p.receita_total - AVG(p.receita_total) OVER (PARTITION BY c.segmento), 2) AS desvio_da_media,
    ROUND(PERCENT_RANK() OVER (
        PARTITION BY c.segmento ORDER BY p.receita_total
    ) * 100, 1) AS percentil_ltv_segmento
FROM clientes c
JOIN premios_cliente p ON c.cliente_id = p.cliente_id
ORDER BY ltv_estimado DESC
LIMIT 10
"""
df5 = con.execute(query5).df()
print(df5.to_string(index=False))

print("\n✅ Pipeline completo executado com sucesso!")
print("Rode 'python -m jupyter notebook' para visualizações interativas.")
