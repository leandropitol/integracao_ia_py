#!/usr/bin/env python3
"""
01_carregar_eleitorado.py — lê "Eleitorado por local de votação 2026" (um
ou mais arquivos por UF em data/raw/tse_eleitorado/) e filtra os locais que
são estabelecimentos penais, pelo padrão de nome (ver config.PADROES_NOME_PRESIDIO).

Saída: data/interim/secoes_presidio.csv — uma linha por seção eleitoral em
presídio (pode haver várias seções por estabelecimento).
"""
from __future__ import annotations

import pandas as pd

from _common import INTERIM, RAW, assert_columns, log, parar, listar_arquivos
from config import COLUNAS_TSE_ELEITORADO, REGEX_PRESIDIO, normalizar_nome

DIR_ELEITORADO = RAW / "tse_eleitorado"


def carregar_um_arquivo(caminho) -> pd.DataFrame:
    # TSE costuma publicar em ';' com encoding latin-1; se vier diferente,
    # assert_columns abaixo vai acusar e paramos em vez de adivinhar.
    try:
        df = pd.read_csv(caminho, sep=";", encoding="latin-1", dtype=str)
    except UnicodeDecodeError:
        df = pd.read_csv(caminho, sep=";", encoding="utf-8", dtype=str)
    if df.shape[1] == 1:
        # sep errado quase certamente — tenta vírgula antes de desistir
        df = pd.read_csv(caminho, sep=",", encoding="latin-1", dtype=str)
    assert_columns(df, list(COLUNAS_TSE_ELEITORADO.values()), f"tse_eleitorado:{caminho.name}")
    df = df.rename(columns={v: k for k, v in COLUNAS_TSE_ELEITORADO.items()})
    df["arquivo_origem"] = caminho.name
    return df


def main() -> None:
    log("=== 01_carregar_eleitorado.py: início ===")
    arquivos = listar_arquivos(DIR_ELEITORADO, "*")
    arquivos = [a for a in arquivos if a.is_file() and not a.name.startswith(".")]
    if not arquivos:
        parar(
            f"Nenhum arquivo em {DIR_ELEITORADO}. Baixe 'Eleitorado por local de "
            f"votação 2026' do TSE (dadosabertos.tse.jus.br) e salve lá, um "
            f"arquivo por UF (ou o nacional, se existir como arquivo único)."
        )

    partes = [carregar_um_arquivo(a) for a in arquivos]
    eleitorado = pd.concat(partes, ignore_index=True)
    log(f"Total de locais de votação carregados: {len(eleitorado)} ({len(arquivos)} arquivo(s))")

    eleitorado["nome_local_norm"] = eleitorado["nome_local"].map(normalizar_nome)
    eh_presidio = eleitorado["nome_local_norm"].str.contains(REGEX_PRESIDIO, na=False)
    secoes_presidio = eleitorado[eh_presidio].copy()

    log(f"Seções identificadas como presídio: {len(secoes_presidio)} (esperado: ordem de 240)")
    if len(secoes_presidio) == 0:
        parar(
            "Nenhuma seção casou com os padrões de nome de presídio. Confira "
            "manualmente uma amostra de nome_local no arquivo bruto — o campo "
            "pode estar vindo diferente do esperado (ex.: só o nome do bairro, "
            "sem o nome do estabelecimento)."
        )

    secoes_presidio.to_csv(INTERIM / "secoes_presidio.csv", index=False, encoding="utf-8")
    log(f"OK: data/interim/secoes_presidio.csv ({len(secoes_presidio)} linhas)")

    # Amostra para conferência manual rápida (os 30 nomes mais comuns)
    amostra = secoes_presidio["nome_local"].value_counts().head(30)
    log("Amostra dos nomes mais frequentes encontrados (conferir manualmente):")
    for nome, n in amostra.items():
        log(f"  [{n:>3}] {nome}")

    log("=== 01_carregar_eleitorado.py: fim ===")


if __name__ == "__main__":
    main()
