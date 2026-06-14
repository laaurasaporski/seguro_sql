"""
Gera dados sintéticos para o pipeline analítico de sinistros de seguros.

Simula o contexto de uma consultoria de TI para o setor de seguros (como a Provider IT),
com tabelas de clientes, apólices, sinistros e pagamentos de prêmio.
"""

import numpy as np
import pandas as pd

np.random.seed(42)
N_CLIENTES = 500
N_APOLICES = 800
N_SINISTROS = 400
N_PAGAMENTOS = 2000

# ==========================
# CLIENTES
# ==========================
estados = ["SP", "RJ", "MG", "RS", "PR", "BA", "PE", "CE"]
segmentos = ["PF", "PJ"]

clientes = pd.DataFrame({
    "cliente_id": range(1, N_CLIENTES + 1),
    "nome": [f"Cliente_{i}" for i in range(1, N_CLIENTES + 1)],
    "estado": np.random.choice(estados, N_CLIENTES, p=[0.35, 0.20, 0.15, 0.10, 0.08, 0.05, 0.04, 0.03]),
    "segmento": np.random.choice(segmentos, N_CLIENTES, p=[0.65, 0.35]),
    "data_cadastro": pd.to_datetime(
        np.random.choice(pd.date_range("2018-01-01", "2023-12-31"), N_CLIENTES)
    ),
    "score_risco": np.random.randint(1, 11, N_CLIENTES),  # 1=baixo, 10=alto
})

# ==========================
# APÓLICES
# ==========================
ramos = ["Auto", "Vida", "Residencial", "Saúde", "Empresarial"]
status_apolice = ["Ativa", "Cancelada", "Vencida"]

apolices = pd.DataFrame({
    "apolice_id": range(1, N_APOLICES + 1),
    "cliente_id": np.random.choice(clientes["cliente_id"], N_APOLICES),
    "ramo": np.random.choice(ramos, N_APOLICES, p=[0.30, 0.25, 0.20, 0.15, 0.10]),
    "premio_anual": np.random.normal(3500, 1500, N_APOLICES).clip(500, 15000).round(2),
    "importancia_segurada": np.random.normal(150000, 80000, N_APOLICES).clip(10000, 800000).round(2),
    "data_inicio": pd.to_datetime(
        np.random.choice(pd.date_range("2019-01-01", "2023-06-30"), N_APOLICES)
    ),
    "status": np.random.choice(status_apolice, N_APOLICES, p=[0.70, 0.15, 0.15]),
})

apolices["data_fim"] = apolices["data_inicio"] + pd.DateOffset(years=1)

# ==========================
# SINISTROS
# ==========================
status_sinistro = ["Pago", "Em análise", "Negado", "Em recurso"]
causas = ["Colisão", "Furto/Roubo", "Incêndio", "Danos naturais", "Invalidez", "Falecimento", "Danos elétricos"]

sinistros_apolice_ids = np.random.choice(apolices["apolice_id"], N_SINISTROS)

sinistros = pd.DataFrame({
    "sinistro_id": range(1, N_SINISTROS + 1),
    "apolice_id": sinistros_apolice_ids,
    "causa": np.random.choice(causas, N_SINISTROS),
    "valor_reclamado": np.random.normal(25000, 15000, N_SINISTROS).clip(500, 200000).round(2),
    "data_ocorrencia": pd.to_datetime(
        np.random.choice(pd.date_range("2019-06-01", "2024-01-31"), N_SINISTROS)
    ),
    "status": np.random.choice(status_sinistro, N_SINISTROS, p=[0.55, 0.25, 0.15, 0.05]),
    "dias_resolucao": np.random.exponential(scale=30, size=N_SINISTROS).clip(1, 365).astype(int),
})

# Valor pago é menor ou igual ao reclamado (só para sinistros pagos)
sinistros["valor_pago"] = np.where(
    sinistros["status"] == "Pago",
    (sinistros["valor_reclamado"] * np.random.uniform(0.6, 1.0, N_SINISTROS)).round(2),
    0.0
)

# ==========================
# PAGAMENTOS DE PRÊMIO
# ==========================
status_pgto = ["Pago", "Atrasado", "Inadimplente"]

pagamentos = pd.DataFrame({
    "pagamento_id": range(1, N_PAGAMENTOS + 1),
    "apolice_id": np.random.choice(apolices["apolice_id"], N_PAGAMENTOS),
    "valor": np.random.normal(300, 120, N_PAGAMENTOS).clip(50, 1500).round(2),
    "data_vencimento": pd.to_datetime(
        np.random.choice(pd.date_range("2019-01-01", "2024-01-31"), N_PAGAMENTOS)
    ),
    "status": np.random.choice(status_pgto, N_PAGAMENTOS, p=[0.75, 0.15, 0.10]),
})

# ==========================
# SALVA CSV
# ==========================
clientes.to_csv("clientes.csv", index=False)
apolices.to_csv("apolices.csv", index=False)
sinistros.to_csv("sinistros.csv", index=False)
pagamentos.to_csv("pagamentos.csv", index=False)

print("Dados gerados com sucesso!")
print(f"  Clientes:   {len(clientes)}")
print(f"  Apólices:   {len(apolices)}")
print(f"  Sinistros:  {len(sinistros)}")
print(f"  Pagamentos: {len(pagamentos)}")
