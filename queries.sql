-- ============================================================
-- PIPELINE ANALÍTICO DE SINISTROS DE SEGUROS
-- Contexto: consultoria de TI para o setor financeiro/seguros
-- Ferramentas: DuckDB (SQL analítico)
--
-- Demonstra:
--   - CTEs encadeadas
--   - Window functions (ROW_NUMBER, RANK, SUM OVER, AVG OVER,
--                       LAG, LEAD, NTILE)
--   - Pipelines analíticos para KPIs de negócio
-- ============================================================


-- ============================================================
-- 1. SINISTRALIDADE POR RAMO
--    Razão entre valor total pago em sinistros e prêmios arrecadados
--    KPI central para seguradoras (< 60% = saudável)
-- ============================================================
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
ORDER BY sinistralidade_pct DESC;


-- ============================================================
-- 2. RANKING DE CLIENTES POR RISCO
--    Combina score de risco, frequência de sinistros e
--    inadimplência de pagamentos — usando window functions
-- ============================================================
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
        COALESCE(i.pgtos_inadimplentes, 0)     AS pgtos_inadimplentes,
        COALESCE(i.total_pagamentos, 0)        AS total_pagamentos,
        ROUND(
            COALESCE(i.pgtos_inadimplentes, 0) * 1.0 /
            NULLIF(COALESCE(i.total_pagamentos, 0), 0) * 100, 2
        )                                      AS taxa_inadimplencia_pct
    FROM clientes c
    LEFT JOIN sinistros_por_cliente s ON c.cliente_id = s.cliente_id
    LEFT JOIN inadimplencia_por_cliente i ON c.cliente_id = i.cliente_id
)

SELECT
    cliente_id,
    nome,
    estado,
    segmento,
    score_risco,
    qtd_sinistros,
    ROUND(total_sinistros_pagos, 2)        AS total_sinistros_pagos,
    taxa_inadimplencia_pct,
    -- Window functions: ranking e quartil de risco
    RANK() OVER (ORDER BY score_risco DESC, qtd_sinistros DESC)   AS rank_risco_geral,
    RANK() OVER (PARTITION BY estado ORDER BY score_risco DESC)   AS rank_risco_por_estado,
    NTILE(4) OVER (ORDER BY score_risco DESC)                     AS quartil_risco  -- 1=maior risco
FROM base_risco
ORDER BY rank_risco_geral
LIMIT 20;


-- ============================================================
-- 3. EVOLUÇÃO MENSAL DE SINISTROS (SÉRIE TEMPORAL)
--    Com média móvel de 3 meses e variação mês a mês (LAG)
-- ============================================================
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
    mes,
    qtd_sinistros,
    valor_total_pago,
    -- Média móvel de 3 meses
    ROUND(AVG(qtd_sinistros) OVER (
        ORDER BY mes
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2)                                     AS media_movel_3m,
    -- Variação em relação ao mês anterior (LAG)
    LAG(qtd_sinistros) OVER (ORDER BY mes)    AS sinistros_mes_anterior,
    qtd_sinistros - LAG(qtd_sinistros) OVER (ORDER BY mes) AS variacao_qtd,
    -- Acumulado no ano (running total)
    SUM(valor_total_pago) OVER (
        PARTITION BY DATE_TRUNC('year', mes)
        ORDER BY mes
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                         AS acumulado_ano
FROM sinistros_mensais
ORDER BY mes;


-- ============================================================
-- 4. PIPELINE DE QUALIDADE: APÓLICES SEM PAGAMENTO RECENTE
--    Identifica apólices ativas com risco de lapso (sem
--    pagamento nos últimos 90 dias) — típico pipeline de
--    monitoramento operacional
-- ============================================================
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
        a.apolice_id,
        a.cliente_id,
        a.ramo,
        a.premio_anual,
        a.status,
        u.ultimo_pgto,
        u.total_pgtos,
        u.pgtos_inadimplentes,
        DATE_DIFF('day', u.ultimo_pgto, CURRENT_DATE) AS dias_sem_pagamento
    FROM apolices a
    LEFT JOIN ultimo_pagamento u ON a.apolice_id = u.apolice_id
    WHERE a.status = 'Ativa'
)

SELECT
    apolice_id,
    cliente_id,
    ramo,
    ROUND(premio_anual, 2)      AS premio_anual,
    ultimo_pgto,
    dias_sem_pagamento,
    pgtos_inadimplentes,
    -- Classificação de risco de lapso
    CASE
        WHEN dias_sem_pagamento > 180 THEN 'Crítico'
        WHEN dias_sem_pagamento > 90  THEN 'Alto'
        WHEN dias_sem_pagamento > 60  THEN 'Moderado'
        ELSE 'Normal'
    END                         AS risco_lapso,
    -- Receita em risco acumulada (window function)
    SUM(premio_anual) OVER (
        PARTITION BY ramo
        ORDER BY dias_sem_pagamento DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                           AS receita_em_risco_acumulada
FROM apolices_em_risco
WHERE dias_sem_pagamento > 60
ORDER BY dias_sem_pagamento DESC;


-- ============================================================
-- 5. LTV E TICKET MÉDIO POR SEGMENTO
--    Lifetime Value estimado por cliente + comparação com
--    média do segmento via window function
-- ============================================================
WITH premios_cliente AS (
    SELECT
        a.cliente_id,
        COUNT(DISTINCT a.apolice_id)  AS total_apolices,
        SUM(a.premio_anual)           AS receita_total,
        MIN(a.data_inicio)            AS primeira_apolice,
        MAX(a.data_inicio)            AS ultima_apolice
    FROM apolices a
    WHERE a.status IN ('Ativa', 'Vencida')
    GROUP BY a.cliente_id
)

SELECT
    c.cliente_id,
    c.segmento,
    c.estado,
    p.total_apolices,
    ROUND(p.receita_total, 2)           AS ltv_estimado,
    ROUND(p.receita_total / NULLIF(p.total_apolices, 0), 2) AS ticket_medio,
    -- Comparação com média do segmento (window function)
    ROUND(AVG(p.receita_total) OVER (PARTITION BY c.segmento), 2)        AS media_ltv_segmento,
    ROUND(p.receita_total - AVG(p.receita_total) OVER (PARTITION BY c.segmento), 2) AS desvio_da_media,
    -- Percentil dentro do segmento
    ROUND(PERCENT_RANK() OVER (
        PARTITION BY c.segmento ORDER BY p.receita_total
    ) * 100, 1)                         AS percentil_ltv_no_segmento
FROM clientes c
JOIN premios_cliente p ON c.cliente_id = p.cliente_id
ORDER BY ltv_estimado DESC
LIMIT 30;
