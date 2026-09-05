#!/usr/bin/env python3
"""
02_indicador1_fiscal.py — Indicador 1: autossustentação fiscal.

Duas medidas independentes e propositalmente NÃO reconciliadas entre si
(a discordância entre elas é informação, não erro):

  1a. IFGF Autonomia (Firjan): % de municípios da UF com nota zero em
      Autonomia (receita local insuficiente para custear prefeito e câmara).
  1b. Grau de dependência de transferências (Siconfi/DCA): receita própria
      / receita corrente total, com os cortes <=20% e dependência >=90%.

*** LAYOUTS NÃO VERIFICADOS AO VIVO NESTA SESSÃO ***
Os nomes de coluna em COLUNAS_IFGF e COLUNAS_DCA abaixo são um ponto de
partida plausível, não uma confirmação. Rode este script; se ele parar em
assert_columns, abra o arquivo bruto, confira o nome real da coluna e
ajuste o mapeamento aqui — não adivinhe no meio do processamento.

Entregáveis: out/indicador1_fiscal_municipio.csv, out/indicador1_fiscal_uf.csv
"""
from __future__ import annotations

import pandas as pd

from _common import INTERIM, OUT, RAW, assert_columns, log, parar

DE_PARA_PATH = INTERIM / "de_para_municipio.csv"
IFGF_PATH = RAW / "ifgf" / "ifgf_base_municipios.xlsx"
DCA_GLOB_PATTERN = "siconfi/dca_receitas_*.csv"

# --- 1a. IFGF Autonomia -----------------------------------------------
# TODO-VERIFICAR contra o arquivo real baixado da Firjan. Nomes plausíveis
# com base em edições anteriores conhecidas do IFGF; a planilha costuma
# trazer o código IBGE, o nome do município, a UF e uma nota (0 a 1) por
# eixo (Autonomia, Gastos com Pessoal, Liquidez, Investimentos).
COLUNAS_IFGF = {
    "codigo_ibge": "Cod IBGE",
    "municipio": "Município",
    "uf": "UF",
    "nota_autonomia": "Autonomia",
}
ABA_IFGF = 0  # TODO-VERIFICAR: a planilha pode ter múltiplas abas (uma por eixo/ano)

# --- 1b. Siconfi / DCA ---------------------------------------------------
# TODO-VERIFICAR contra o CSV real exportado do Siconfi. A API/export
# costuma trazer uma linha por conta contábil (formato longo), não uma
# coluna por conta — por isso o parser pivota pelas contas de interesse.
COLUNAS_DCA = {
    "codigo_ibge": "cod_ibge",
    "exercicio": "exercicio",
    "conta_descricao": "conta",  # texto da conta contábil
    "valor": "valor",
}

# Contas que compõem RECEITA PRÓPRIA, por regra explícita do projeto:
# impostos de competência municipal (IPTU, ISS, ITBI, IRRF sobre folha
# própria) + taxas + contribuição de melhoria + COSIP.
# EXCLUI: transferências correntes/capital, cota-parte de ICMS/IPVA, FPM,
# royalties, receita de aplicação financeira.
# TODO-VERIFICAR os textos exatos das contas no anexo de receitas
# orçamentárias da DCA (podem vir como código de conta contábil em vez de
# descrição — nesse caso, trocar este filtro por códigos de conta).
CONTAS_RECEITA_PROPRIA = [
    "Imposto sobre a Propriedade Predial e Territorial Urbana",
    "Imposto sobre Serviços de Qualquer Natureza",
    "Imposto sobre Transmissão \"Inter Vivos\"",
    "IRRF",
    "Taxas",
    "Contribuição de Melhoria",
    "Contribuição para o Custeio do Serviço de Iluminação Pública",
]
CONTA_RECEITA_CORRENTE_TOTAL = "Receitas Correntes"


def carregar_de_para() -> pd.DataFrame:
    if not DE_PARA_PATH.exists():
        parar(f"{DE_PARA_PATH} não existe. Rode 01_de_para_municipio.py primeiro.")
    return pd.read_csv(DE_PARA_PATH, dtype={"codigo_ibge_7": "Int64", "codigo_ibge_6": "Int64"})


def processar_ifgf(de_para: pd.DataFrame) -> pd.DataFrame:
    if not IFGF_PATH.exists():
        log(f"AVISO: {IFGF_PATH} não encontrado — indicador 1a (IFGF) ficará NA para todos os municípios.")
        base = de_para[["codigo_ibge_7"]].copy()
        base["nota_autonomia_ifgf"] = pd.NA
        base["flag_nota_zero_autonomia"] = pd.NA
        base["ifgf_analisado"] = False
        return base

    df = pd.read_excel(IFGF_PATH, sheet_name=ABA_IFGF)
    assert_columns(df, list(COLUNAS_IFGF.values()), "ifgf_firjan")
    df = df.rename(columns={v: k for k, v in COLUNAS_IFGF.items()})

    df["codigo_ibge"] = pd.to_numeric(df["codigo_ibge"], errors="coerce").astype("Int64")
    if df["codigo_ibge"].isna().any():
        parar(
            "IFGF: há linhas sem código IBGE numérico válido após conversão — "
            "confira se a coluna de código não veio como texto com máscara "
            "(ex. pontuação) ou se há linhas de rodapé/nota na planilha que "
            "deveriam ser descartadas antes do parse (skiprows)."
        )

    df["ifgf_analisado"] = True
    df["flag_nota_zero_autonomia"] = df["nota_autonomia"] == 0

    out = de_para[["codigo_ibge_7"]].merge(
        df[["codigo_ibge", "nota_autonomia", "flag_nota_zero_autonomia", "ifgf_analisado"]],
        left_on="codigo_ibge_7",
        right_on="codigo_ibge",
        how="left",
    ).drop(columns="codigo_ibge")
    out["ifgf_analisado"] = out["ifgf_analisado"].fillna(False)
    out = out.rename(columns={"nota_autonomia": "nota_autonomia_ifgf"})
    return out


def processar_dca(de_para: pd.DataFrame) -> pd.DataFrame:
    arquivos = sorted(RAW.glob(DCA_GLOB_PATTERN))
    if not arquivos:
        log(f"AVISO: nenhum arquivo em data/raw/{DCA_GLOB_PATTERN} — indicador 1b (Siconfi) ficará NA.")
        base = de_para[["codigo_ibge_7"]].copy()
        for c in ["receita_propria", "receita_corrente_total", "pct_receita_propria", "pct_dependencia_transferencias"]:
            base[c] = pd.NA
        base["dca_analisado"] = False
        base["flag_receita_propria_baixa"] = pd.NA
        base["flag_dependencia_alta"] = pd.NA
        return base

    # Usa o exercício mais recente disponível entre os arquivos baixados.
    arquivo_mais_recente = arquivos[-1]
    log(f"Usando DCA: {arquivo_mais_recente.name}")
    df = pd.read_csv(arquivo_mais_recente, dtype=str)
    assert_columns(df, list(COLUNAS_DCA.values()), "siconfi_dca")
    df = df.rename(columns={v: k for k, v in COLUNAS_DCA.items()})
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["codigo_ibge"] = pd.to_numeric(df["codigo_ibge"], errors="coerce").astype("Int64")

    receita_propria = (
        df[df["conta_descricao"].isin(CONTAS_RECEITA_PROPRIA)]
        .groupby("codigo_ibge", as_index=False)["valor"].sum()
        .rename(columns={"valor": "receita_propria"})
    )
    receita_corrente = (
        df[df["conta_descricao"] == CONTA_RECEITA_CORRENTE_TOTAL]
        .groupby("codigo_ibge", as_index=False)["valor"].sum()
        .rename(columns={"valor": "receita_corrente_total"})
    )

    fiscal = receita_corrente.merge(receita_propria, on="codigo_ibge", how="left")
    fiscal["receita_propria"] = fiscal["receita_propria"].fillna(0.0)  # ausência de conta = 0 arrecadado nela, não NA
    fiscal["dca_analisado"] = True
    fiscal["pct_receita_propria"] = fiscal["receita_propria"] / fiscal["receita_corrente_total"]
    fiscal["pct_dependencia_transferencias"] = 1 - fiscal["pct_receita_propria"]
    fiscal["flag_receita_propria_baixa"] = fiscal["pct_receita_propria"] <= 0.20
    fiscal["flag_dependencia_alta"] = fiscal["pct_dependencia_transferencias"] >= 0.90

    out = de_para[["codigo_ibge_7"]].merge(
        fiscal, left_on="codigo_ibge_7", right_on="codigo_ibge", how="left"
    ).drop(columns="codigo_ibge")
    out["dca_analisado"] = out["dca_analisado"].fillna(False)
    return out


def agregar_por_uf(municipio: pd.DataFrame) -> pd.DataFrame:
    # `municipio` já vem com uf_sigla (herdado do de_para na junção feita em main()).
    df = municipio
    linhas = []
    for uf, g in df.groupby("uf_sigla"):
        n_total = len(g)
        n_ifgf = int(g["ifgf_analisado"].sum())
        n_dca = int(g["dca_analisado"].sum())
        n_nota_zero = int(g["flag_nota_zero_autonomia"].fillna(False).sum())
        n_receita_baixa = int(g["flag_receita_propria_baixa"].fillna(False).sum())
        n_dependencia_alta = int(g["flag_dependencia_alta"].fillna(False).sum())
        linhas.append(
            {
                "uf_sigla": uf,
                "n_municipios_total": n_total,
                "n_municipios_ifgf_analisados": n_ifgf,
                "n_municipios_dca_analisados": n_dca,
                "cobertura_ifgf_pct": n_ifgf / n_total if n_total else pd.NA,
                "cobertura_dca_pct": n_dca / n_total if n_total else pd.NA,
                "pct_nota_zero_sobre_ifgf_analisados": n_nota_zero / n_ifgf if n_ifgf else pd.NA,
                "pct_nota_zero_sobre_total_uf": n_nota_zero / n_total if n_total else pd.NA,
                "pct_receita_propria_baixa_sobre_dca_analisados": n_receita_baixa / n_dca if n_dca else pd.NA,
                "pct_receita_propria_baixa_sobre_total_uf": n_receita_baixa / n_total if n_total else pd.NA,
                "pct_dependencia_alta_sobre_dca_analisados": n_dependencia_alta / n_dca if n_dca else pd.NA,
                "pct_dependencia_alta_sobre_total_uf": n_dependencia_alta / n_total if n_total else pd.NA,
                "alerta_cobertura_ifgf_abaixo_90pct": (n_ifgf / n_total < 0.90) if n_total else pd.NA,
            }
        )
    return pd.DataFrame(linhas).sort_values("uf_sigla").reset_index(drop=True)


def main() -> None:
    log("=== 02_indicador1_fiscal.py: início ===")
    de_para = carregar_de_para()

    ifgf = processar_ifgf(de_para)
    dca = processar_dca(de_para)

    municipio = de_para.merge(ifgf, on="codigo_ibge_7", how="left").merge(dca, on="codigo_ibge_7", how="left")
    municipio.to_csv(OUT / "indicador1_fiscal_municipio.csv", index=False, encoding="utf-8")

    uf = agregar_por_uf(municipio)
    uf.to_csv(OUT / "indicador1_fiscal_uf.csv", index=False, encoding="utf-8")

    alertas = uf[uf["alerta_cobertura_ifgf_abaixo_90pct"] == True]  # noqa: E712
    if len(alertas):
        log(f"AVISO — UFs com cobertura IFGF < 90%: {list(alertas['uf_sigla'])}")

    log(f"OK: out/indicador1_fiscal_municipio.csv ({len(municipio)} linhas), out/indicador1_fiscal_uf.csv ({len(uf)} linhas)")
    log("=== 02_indicador1_fiscal.py: fim ===")


if __name__ == "__main__":
    main()
