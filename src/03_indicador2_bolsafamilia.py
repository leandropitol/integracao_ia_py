#!/usr/bin/env python3
"""
03_indicador2_bolsafamilia.py — Indicador 2: penetração do Bolsa Família.

Métricas por município:
  - familias_bf / domicilios_censo2022
  - pessoas_bf   / populacao_censo2022
  - familias_bf / vinculos_formais_ativos   (vem da RAIS, ver lib_rais.py)

Por UF: % de municípios acima de 30%, 50% e 80% dos domicílios.

Flag de anomalia: municípios com razão acima de 100% dos domicílios EXISTEM
e são reais na base (subcontagem do Censo em área rural dispersa, cadastro
desatualizado ou fraude são hipóteses, não certezas). Marcados em
`flag_razao_acima_100`, nunca excluídos e nunca tratados como erro de dado.

*** LAYOUTS NÃO VERIFICADOS AO VIVO NESTA SESSÃO *** — ver TODO-VERIFICAR
nos mapeamentos de coluna abaixo.

Entregáveis: out/indicador2_bolsafamilia_municipio.csv, out/indicador2_bolsafamilia_uf.csv
"""
from __future__ import annotations

import pandas as pd

from _common import INTERIM, OUT, RAW, assert_columns, log, parar
from lib_rais import agregar_rais_por_municipio

DE_PARA_PATH = INTERIM / "de_para_municipio.csv"
RAIS_INTERIM_PATH = INTERIM / "rais_vinculos_totais_municipio.csv"
RAIS_DIR = RAW / "rais"
CENSO_PATH = RAW / "censo2022" / "censo2022_populacao_domicilios_municipio.csv"
BF_DIR = RAW / "bolsafamilia"

MES_REFERENCIA_ESPERADO = None  # TODO: defina explicitamente, ex. "2025_06",
# e ajuste o glob abaixo para exigir esse mês específico — o projeto pede
# mês de referência fixo e explícito no nome do arquivo, não "o mais recente
# disponível no diretório" escolhido implicitamente.
BF_GLOB_PATTERN = "bf_familias_beneficiarias_*.csv"

# TODO-VERIFICAR nomes reais das colunas no export do VIS DATA/MDS.
COLUNAS_BF = {
    "codigo_ibge": "codigo_ibge",
    "familias_bf": "qtd_familias_beneficiarias",
    "pessoas_bf": "qtd_pessoas_beneficiarias",
}

# TODO-VERIFICAR números de tabela SIDRA do Censo 2022 usados para gerar
# este CSV (ver config_fontes.py, fonte "censo2022_sidra").
COLUNAS_CENSO = {
    "codigo_ibge": "codigo_ibge",
    "domicilios_censo2022": "domicilios_particulares_permanentes",
    "populacao_censo2022": "populacao_residente",
}


def carregar_de_para() -> pd.DataFrame:
    if not DE_PARA_PATH.exists():
        parar(f"{DE_PARA_PATH} não existe. Rode 01_de_para_municipio.py primeiro.")
    return pd.read_csv(DE_PARA_PATH, dtype={"codigo_ibge_7": "Int64", "codigo_ibge_6": "Int64"})


def carregar_bolsa_familia() -> pd.DataFrame:
    arquivos = sorted(BF_DIR.glob(BF_GLOB_PATTERN))
    if not arquivos:
        parar(
            f"Nenhum arquivo em data/raw/{BF_GLOB_PATTERN}. Baixe manualmente "
            f"do VIS DATA (ver config_fontes.py, fonte 'bolsafamilia_visdata') "
            f"com o mês de referência no nome do arquivo."
        )
    if len(arquivos) > 1:
        parar(
            f"Mais de um arquivo de Bolsa Família encontrado: {[a.name for a in arquivos]}. "
            f"O projeto exige mês de referência FIXO — deixe só o arquivo do mês "
            f"escolhido em data/raw/bolsafamilia/ (mova os outros para fora) e rode de novo."
        )
    arquivo = arquivos[0]
    log(f"Usando Bolsa Família: {arquivo.name}")
    df = pd.read_csv(arquivo, dtype=str)
    assert_columns(df, list(COLUNAS_BF.values()), "bolsafamilia_visdata")
    df = df.rename(columns={v: k for k, v in COLUNAS_BF.items()})
    df["codigo_ibge"] = pd.to_numeric(df["codigo_ibge"], errors="coerce").astype("Int64")
    df["familias_bf"] = pd.to_numeric(df["familias_bf"], errors="coerce")
    df["pessoas_bf"] = pd.to_numeric(df["pessoas_bf"], errors="coerce")
    df["mes_referencia_arquivo"] = arquivo.stem
    return df


def carregar_censo() -> pd.DataFrame:
    if not CENSO_PATH.exists():
        parar(f"{CENSO_PATH} não encontrado. Rode 00_download.py / confirme a fonte 'censo2022_sidra'.")
    df = pd.read_csv(CENSO_PATH, dtype=str)
    assert_columns(df, list(COLUNAS_CENSO.values()), "censo2022_sidra")
    df = df.rename(columns={v: k for k, v in COLUNAS_CENSO.items()})
    df["codigo_ibge"] = pd.to_numeric(df["codigo_ibge"], errors="coerce").astype("Int64")
    df["domicilios_censo2022"] = pd.to_numeric(df["domicilios_censo2022"], errors="coerce")
    df["populacao_censo2022"] = pd.to_numeric(df["populacao_censo2022"], errors="coerce")
    return df


def carregar_vinculos_formais(de_para: pd.DataFrame) -> pd.DataFrame:
    """Tenta, nesta ordem: (1) subproduto já calculado por
    04_indicador3_empregador.py em data/interim/; (2) calcular na hora se
    os arquivos brutos da RAIS já estiverem em data/raw/rais/; (3) desistir
    e devolver NA — a razão familias_bf/vinculos_formais_ativos fica
    ausente, mas o resto do indicador 2 segue normalmente."""
    if RAIS_INTERIM_PATH.exists():
        log(f"Usando vínculos formais já agregados: {RAIS_INTERIM_PATH}")
        df = pd.read_csv(RAIS_INTERIM_PATH, dtype={"codigo_ibge_6": "Int64"})
        return df[["codigo_ibge_6", "total_vinculos_ativos"]]

    arquivos_rais = sorted(RAIS_DIR.glob("RAIS_VINC_PUB_*.txt"))
    if arquivos_rais:
        log("Subproduto da RAIS não existe ainda; agregando agora a partir dos brutos (isso é lento).")
        agregado = agregar_rais_por_municipio(arquivos_rais)
        agregado.to_csv(RAIS_INTERIM_PATH, index=False, encoding="utf-8")
        return agregado[["codigo_ibge_6", "total_vinculos_ativos"]]

    log(
        "AVISO: vínculos formais ativos (RAIS) indisponíveis — a razão "
        "familias_bf/vinculos_formais_ativos ficará NA. Rode "
        "04_indicador3_empregador.py (ou baixe a RAIS) para preenchê-la."
    )
    base = de_para[["codigo_ibge_6"]].copy()
    base["total_vinculos_ativos"] = pd.NA
    return base


def agregar_por_uf(municipio: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for uf, g in municipio.groupby("uf_sigla"):
        n_total = len(g)
        n_com_dado = int(g["razao_familias_domicilios"].notna().sum())
        linha = {"uf_sigla": uf, "n_municipios_total": n_total, "n_municipios_com_dado": n_com_dado}
        for corte in (0.30, 0.50, 0.80):
            n_acima = int((g["razao_familias_domicilios"] > corte).sum())
            linha[f"pct_acima_{int(corte*100)}pct_domicilios_sobre_com_dado"] = n_acima / n_com_dado if n_com_dado else pd.NA
            linha[f"pct_acima_{int(corte*100)}pct_domicilios_sobre_total_uf"] = n_acima / n_total if n_total else pd.NA
        n_anomalia = int(g["flag_razao_acima_100"].fillna(False).sum())
        linha["n_municipios_flag_razao_acima_100"] = n_anomalia
        linha["pct_flag_razao_acima_100_sobre_total_uf"] = n_anomalia / n_total if n_total else pd.NA
        linhas.append(linha)
    return pd.DataFrame(linhas).sort_values("uf_sigla").reset_index(drop=True)


def main() -> None:
    log("=== 03_indicador2_bolsafamilia.py: início ===")
    de_para = carregar_de_para()
    bf = carregar_bolsa_familia()
    censo = carregar_censo()
    vinculos = carregar_vinculos_formais(de_para)

    municipio = de_para.merge(bf.drop(columns=[]), left_on="codigo_ibge_7", right_on="codigo_ibge", how="left").drop(columns="codigo_ibge")
    municipio = municipio.merge(censo, left_on="codigo_ibge_7", right_on="codigo_ibge", how="left", suffixes=("", "_censo")).drop(columns="codigo_ibge")
    municipio = municipio.merge(vinculos, on="codigo_ibge_6", how="left")

    municipio["razao_familias_domicilios"] = municipio["familias_bf"] / municipio["domicilios_censo2022"]
    municipio["razao_pessoas_populacao"] = municipio["pessoas_bf"] / municipio["populacao_censo2022"]
    municipio["razao_familias_vinculos_formais"] = municipio["familias_bf"] / municipio["total_vinculos_ativos"]
    municipio["flag_razao_acima_100"] = municipio["razao_familias_domicilios"] > 1.0

    municipio.to_csv(OUT / "indicador2_bolsafamilia_municipio.csv", index=False, encoding="utf-8")

    uf = agregar_por_uf(municipio)
    uf.to_csv(OUT / "indicador2_bolsafamilia_uf.csv", index=False, encoding="utf-8")

    n_anomalia_brasil = int(municipio["flag_razao_acima_100"].fillna(False).sum())
    log(f"Municípios com razão familias/domicílios > 100%: {n_anomalia_brasil} (mantidos, não excluídos).")
    log(f"OK: out/indicador2_bolsafamilia_municipio.csv ({len(municipio)} linhas), out/indicador2_bolsafamilia_uf.csv ({len(uf)} linhas)")
    log("=== 03_indicador2_bolsafamilia.py: fim ===")


if __name__ == "__main__":
    main()
