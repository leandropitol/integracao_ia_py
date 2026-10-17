#!/usr/bin/env python3
"""
03_carregar_sisdepen.py — lê os arquivos do SISDEPEN em data/raw/sisdepen/
(item 5.14 "incidências por tipo penal" + população prisional/provisórios)
e monta o perfil penal por unidade: % de cada categoria de tipo penal e %
de presos provisórios.

Saída: data/interim/perfil_penal_unidade.csv — uma linha por estabelecimento.
"""
from __future__ import annotations

import pandas as pd

from _common import INTERIM, RAW, assert_columns, log, parar, listar_arquivos
from config import (
    COLUNAS_SISDEPEN_TIPO_PENAL,
    COLUNAS_SISDEPEN_POPULACAO,
    CATEGORIAS_TIPO_PENAL,
    CATEGORIA_RESIDUAL,
    categorizar_tipo_penal,
)

DIR_SISDEPEN = RAW / "sisdepen"


def _ler_planilha(caminho, aba=None) -> pd.DataFrame:
    if caminho.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(caminho, sheet_name=aba if aba is not None else 0)
    return pd.read_csv(caminho, dtype=str)


def carregar_tipo_penal() -> pd.DataFrame:
    arquivos = listar_arquivos(DIR_SISDEPEN, "*tipo*penal*") or listar_arquivos(DIR_SISDEPEN, "*5.14*") or listar_arquivos(DIR_SISDEPEN, "*5_14*")
    if not arquivos:
        parar(
            f"Nenhum arquivo de tipo penal (item 5.14) encontrado em {DIR_SISDEPEN}. "
            f"Nomeie o arquivo contendo 'tipo_penal' ou '5.14' para o script achar, "
            f"ou ajuste o padrão de busca aqui depois de ver o nome real do arquivo baixado."
        )
    partes = []
    for a in arquivos:
        df = _ler_planilha(a)
        assert_columns(df, list(COLUNAS_SISDEPEN_TIPO_PENAL.values()), f"sisdepen_tipo_penal:{a.name}")
        df = df.rename(columns={v: k for k, v in COLUNAS_SISDEPEN_TIPO_PENAL.items()})
        partes.append(df)
    tipo_penal = pd.concat(partes, ignore_index=True)
    tipo_penal["quantidade"] = pd.to_numeric(tipo_penal["quantidade"], errors="coerce")
    tipo_penal["categoria"] = tipo_penal["tipo_penal"].map(categorizar_tipo_penal)
    return tipo_penal


def carregar_populacao() -> pd.DataFrame:
    arquivos = listar_arquivos(DIR_SISDEPEN, "*populac*") or listar_arquivos(DIR_SISDEPEN, "*provisori*")
    if not arquivos:
        log(
            f"AVISO: nenhum arquivo de população/provisórios encontrado em {DIR_SISDEPEN} "
            f"(buscando *populac* ou *provisori*). % de provisórios ficará NA."
        )
        return pd.DataFrame(columns=list(COLUNAS_SISDEPEN_POPULACAO.keys()))
    partes = []
    for a in arquivos:
        df = _ler_planilha(a)
        assert_columns(df, list(COLUNAS_SISDEPEN_POPULACAO.values()), f"sisdepen_populacao:{a.name}")
        df = df.rename(columns={v: k for k, v in COLUNAS_SISDEPEN_POPULACAO.items()})
        partes.append(df)
    pop = pd.concat(partes, ignore_index=True)
    pop["populacao_total"] = pd.to_numeric(pop["populacao_total"], errors="coerce")
    pop["presos_provisorios"] = pd.to_numeric(pop["presos_provisorios"], errors="coerce")
    return pop


def main() -> None:
    log("=== 03_carregar_sisdepen.py: início ===")
    tipo_penal = carregar_tipo_penal()
    populacao = carregar_populacao()

    pivot = tipo_penal.pivot_table(
        index=["uf", "nome_unidade"], columns="categoria", values="quantidade", aggfunc="sum", fill_value=0
    )
    # Garante todas as categorias conhecidas mesmo que alguma não tenha
    # aparecido nos dados carregados até agora (ex.: só algumas UFs
    # processadas ainda) — senão colunas pct_* somem e quebram scripts
    # downstream que esperam o conjunto fixo de categorias.
    todas_categorias = list(CATEGORIAS_TIPO_PENAL.keys()) + [CATEGORIA_RESIDUAL]
    pivot = pivot.reindex(columns=todas_categorias, fill_value=0)
    pivot["total_incidencias"] = pivot.sum(axis=1)
    pct = pivot.div(pivot["total_incidencias"], axis=0).add_prefix("pct_")
    pct = pct.drop(columns=["pct_total_incidencias"], errors="ignore")
    perfil = pivot.join(pct).reset_index()

    if not populacao.empty:
        pop_agg = populacao.groupby(["uf", "nome_unidade"], as_index=False).agg(
            populacao_total=("populacao_total", "sum"),
            presos_provisorios=("presos_provisorios", "sum"),
        )
        pop_agg["pct_provisorios"] = pop_agg["presos_provisorios"] / pop_agg["populacao_total"]
        # campos adicionais (regime, gênero, município) — pega a primeira
        # ocorrência por unidade; se houver múltiplas linhas conflitantes
        # (ex. unidade mista relatada por regime), isso é achatado aqui e
        # deve ser revisto manualmente se o número de linhas por unidade > 1.
        extras = populacao.groupby(["uf", "nome_unidade"], as_index=False).agg(
            municipio=("municipio", "first"),
            genero_unidade=("genero_unidade", "first"),
            regime=("regime", "first"),
        )
        perfil = perfil.merge(pop_agg, on=["uf", "nome_unidade"], how="left")
        perfil = perfil.merge(extras, on=["uf", "nome_unidade"], how="left")
    else:
        perfil["populacao_total"] = pd.NA
        perfil["presos_provisorios"] = pd.NA
        perfil["pct_provisorios"] = pd.NA
        perfil["municipio"] = pd.NA
        perfil["genero_unidade"] = pd.NA
        perfil["regime"] = pd.NA

    perfil.to_csv(INTERIM / "perfil_penal_unidade.csv", index=False, encoding="utf-8")
    log(f"OK: data/interim/perfil_penal_unidade.csv ({len(perfil)} unidades)")
    log("=== 03_carregar_sisdepen.py: fim ===")


if __name__ == "__main__":
    main()
