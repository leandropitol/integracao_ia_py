#!/usr/bin/env python3
"""
02_carregar_votacao.py — lê "Votação por seção eleitoral" 1º turno 2026 (um
ou mais arquivos por UF em data/raw/tse_votacao/), filtra só as seções que
estão em presídio (join com data/interim/secoes_presidio.csv por UF +
código de município TSE + zona + seção), e agrega por ESTABELECIMENTO
(pode haver mais de uma seção por unidade, por isso soma).

Saída:
  - data/interim/votacao_secao_presidio.csv  (nível seção, granular)
  - data/interim/votacao_estabelecimento.csv (nível estabelecimento, agregado)
"""
from __future__ import annotations

import pandas as pd

from _common import INTERIM, RAW, assert_columns, log, parar, listar_arquivos
from config import COLUNAS_TSE_VOTACAO, CARGOS_DE_INTERESSE, ROTULOS_BRANCO, ROTULOS_NULO

DIR_VOTACAO = RAW / "tse_votacao"
SECOES_PRESIDIO_PATH = INTERIM / "secoes_presidio.csv"


def carregar_um_arquivo(caminho) -> pd.DataFrame:
    try:
        df = pd.read_csv(caminho, sep=";", encoding="latin-1", dtype=str)
    except UnicodeDecodeError:
        df = pd.read_csv(caminho, sep=";", encoding="utf-8", dtype=str)
    if df.shape[1] == 1:
        df = pd.read_csv(caminho, sep=",", encoding="latin-1", dtype=str)
    assert_columns(df, list(COLUNAS_TSE_VOTACAO.values()), f"tse_votacao:{caminho.name}")
    df = df.rename(columns={v: k for k, v in COLUNAS_TSE_VOTACAO.items()})
    return df


def main() -> None:
    log("=== 02_carregar_votacao.py: início ===")
    if not SECOES_PRESIDIO_PATH.exists():
        parar(f"{SECOES_PRESIDIO_PATH} não existe. Rode 01_carregar_eleitorado.py primeiro.")
    secoes_presidio = pd.read_csv(SECOES_PRESIDIO_PATH, dtype=str)

    arquivos = listar_arquivos(DIR_VOTACAO, "*")
    arquivos = [a for a in arquivos if a.is_file() and not a.name.startswith(".")]
    if not arquivos:
        parar(
            f"Nenhum arquivo em {DIR_VOTACAO}. Baixe 'Votação por seção "
            f"eleitoral — 1º turno 2026' do TSE e salve lá. Pode mandar "
            f"UF por UF — este script processa o que encontrar e avisa "
            f"quais UFs de secoes_presidio.csv ainda não têm arquivo de votação."
        )

    ufs_disponiveis = set()
    partes = []
    for a in arquivos:
        df = carregar_um_arquivo(a)
        ufs_disponiveis.update(df["uf"].unique())
        partes.append(df)
    votacao = pd.concat(partes, ignore_index=True)

    ufs_presidio = set(secoes_presidio["uf"].unique())
    ufs_faltando = ufs_presidio - ufs_disponiveis
    if ufs_faltando:
        log(
            f"AVISO: {len(ufs_faltando)} UF(s) com seção em presídio mas SEM "
            f"arquivo de votação carregado ainda: {sorted(ufs_faltando)}. "
            f"Essas unidades ficarão sem dado de votação (cobertura parcial, "
            f"documentado explicitamente — não é erro, é o esperado ao processar "
            f"aos poucos)."
        )

    votacao["votos"] = pd.to_numeric(votacao["votos"], errors="coerce")
    votacao["cargo_norm"] = votacao["cargo"].str.upper().str.strip()
    votacao = votacao[votacao["cargo_norm"].isin(CARGOS_DE_INTERESSE)]

    # Benchmark municipal: resultado do MUNICÍPIO INTEIRO (todas as seções,
    # não só a(s) do presídio) para presidente — usado depois para medir o
    # descolamento entre a seção do presídio e o entorno. Precisa ser
    # calculado ANTES do filtro para só seções de presídio, senão perdemos
    # as demais seções do município.
    nome_cand_norm_mun = votacao["nome_candidato"].str.upper().str.strip()
    votacao_mun = votacao.assign(
        eh_branco=nome_cand_norm_mun.isin(ROTULOS_BRANCO),
        eh_nulo=nome_cand_norm_mun.isin(ROTULOS_NULO),
    )
    bench_rows = []
    for (uf, mun_tse, cargo), g in votacao_mun[votacao_mun["cargo_norm"] == "PRESIDENTE"].groupby(
        ["uf", "codigo_municipio_tse", "cargo_norm"]
    ):
        validos = g[~g["eh_branco"] & ~g["eh_nulo"]]
        total_validos = validos["votos"].sum()
        top = validos.groupby("nome_candidato")["votos"].sum().sort_values(ascending=False)
        bench_rows.append(
            {
                "uf": uf,
                "codigo_municipio_tse": mun_tse,
                "votos_validos_municipio": total_validos,
                "vencedor_municipio": top.index[0] if len(top) else pd.NA,
                "pct_vencedor_municipio": (top.iloc[0] / total_validos) if total_validos else pd.NA,
            }
        )
    pd.DataFrame(bench_rows).to_csv(INTERIM / "benchmark_municipio.csv", index=False, encoding="utf-8")
    log(f"OK: data/interim/benchmark_municipio.csv ({len(bench_rows)} municípios, presidente)")

    chave = ["uf", "codigo_municipio_tse", "zona", "secao"]
    votacao_secao_presidio = votacao.merge(
        secoes_presidio[chave + ["nome_local", "nome_municipio"]].drop_duplicates(),
        on=chave,
        how="inner",
    )
    log(f"Linhas de votação (candidato x seção) em presídio: {len(votacao_secao_presidio)}")

    nome_candidato_norm = votacao_secao_presidio["nome_candidato"].str.upper().str.strip()
    votacao_secao_presidio = votacao_secao_presidio.assign(
        eh_branco=nome_candidato_norm.isin(ROTULOS_BRANCO),
        eh_nulo=nome_candidato_norm.isin(ROTULOS_NULO),
    )
    votacao_secao_presidio.to_csv(INTERIM / "votacao_secao_presidio.csv", index=False, encoding="utf-8")


    agregados = []
    for (uf, mun_tse, nome_local, cargo), g in votacao_secao_presidio.groupby(
        ["uf", "codigo_municipio_tse", "nome_local", "cargo_norm"]
    ):
        validos = g[~g["eh_branco"] & ~g["eh_nulo"]]
        total_validos = validos["votos"].sum()
        vencedor = validos.sort_values("votos", ascending=False).iloc[0] if len(validos) else None
        linha = {
            "uf": uf,
            "codigo_municipio_tse": mun_tse,
            "nome_local": nome_local,
            "cargo": cargo,
            "votos_validos": total_validos,
            "votos_brancos": g[g["eh_branco"]]["votos"].sum(),
            "votos_nulos": g[g["eh_nulo"]]["votos"].sum(),
            "vencedor_nome": vencedor["nome_candidato"] if vencedor is not None else pd.NA,
            "vencedor_votos": vencedor["votos"] if vencedor is not None else pd.NA,
            "n_secoes_agregadas": g[["zona", "secao"]].drop_duplicates().shape[0],
        }
        agregados.append(linha)

    votacao_estabelecimento = pd.DataFrame(agregados)
    votacao_estabelecimento.to_csv(INTERIM / "votacao_estabelecimento.csv", index=False, encoding="utf-8")
    log(f"OK: data/interim/votacao_estabelecimento.csv ({len(votacao_estabelecimento)} linhas, {votacao_estabelecimento['nome_local'].nunique()} estabelecimentos)")
    log("=== 02_carregar_votacao.py: fim ===")


if __name__ == "__main__":
    main()
