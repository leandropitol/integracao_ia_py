#!/usr/bin/env python3
"""
04_indicador3_empregador.py — Indicador 3 (central do projeto): estado
como principal empregador formal do município.

Duas definições de "maior empregador", calculadas em paralelo porque
divergem e ambas são defensáveis:
  (a) por setor: vínculos da administração municipal vs. maior seção CNAE privada
  (b) por empregador individual: prefeitura (CNPJ raiz) vs. maior CNPJ raiz privado

A leitura/agregação da RAIS está em lib_rais.py (compartilhada com o
indicador 2). Este script cuida de: achar os arquivos por UF, rodar a
agregação, juntar com o de/para de município, agregar por UF, e anexar a
taxa de informalidade da PNAD Contínua como coluna de CONTEXTO (fonte
diferente, não usada para corrigir nada).

*** LIMITAÇÃO METODOLÓGICA OBRIGATÓRIA (ver também README.md) ***
A RAIS só enxerga o emprego FORMAL. Onde a informalidade é alta — Norte,
Nordeste, municípios rurais pequenos — o peso relativo do setor público
aparece superestimado frente à ocupação real total. Isso não é corrigido
por estimativa; é documentado, e a taxa de informalidade da PNAD Contínua
é trazida como contraponto, claramente marcada como fonte diferente.

Entregáveis: out/indicador3_empregador_municipio.csv, out/indicador3_empregador_uf.csv
"""
from __future__ import annotations

import pandas as pd

from _common import INTERIM, OUT, RAW, log, parar
from lib_rais import agregar_rais_por_municipio

DE_PARA_PATH = INTERIM / "de_para_municipio.csv"
RAIS_DIR = RAW / "rais"
PNADC_INFORMALIDADE_PATH = RAW / "pnadc" / "pnadc_informalidade_uf.csv"

# TODO-VERIFICAR nomes de coluna reais do export da PNAD Contínua escolhido.
COLUNAS_PNADC = {"uf_sigla": "UF", "taxa_informalidade": "taxa_informalidade_pct"}


def carregar_de_para() -> pd.DataFrame:
    if not DE_PARA_PATH.exists():
        parar(f"{DE_PARA_PATH} não existe. Rode 01_de_para_municipio.py primeiro.")
    return pd.read_csv(DE_PARA_PATH, dtype={"codigo_ibge_7": "Int64", "codigo_ibge_6": "Int64"})


def encontrar_arquivos_rais() -> list:
    arquivos = sorted(RAIS_DIR.glob("RAIS_VINC_PUB_*.txt"))
    if not arquivos:
        parar(
            f"Nenhum arquivo RAIS encontrado em {RAIS_DIR} (padrão esperado: "
            f"RAIS_VINC_PUB_<UF>.txt). Rode 00_download.py / confirme o "
            f"nome exato dos arquivos no FTP do MTE e ajuste o padrão de "
            f"busca aqui se necessário."
        )
    return arquivos


def carregar_informalidade_pnadc() -> pd.DataFrame | None:
    if not PNADC_INFORMALIDADE_PATH.exists():
        log(f"AVISO: {PNADC_INFORMALIDADE_PATH} não encontrado — coluna de contexto de informalidade ficará ausente.")
        return None
    df = pd.read_csv(PNADC_INFORMALIDADE_PATH)
    faltando = [c for c in COLUNAS_PNADC.values() if c not in df.columns]
    if faltando:
        log(f"AVISO: colunas PNADC ausentes {faltando} — pulando coluna de contexto (não é um dado do indicador, então não paramos o pipeline por isso).")
        return None
    return df.rename(columns={v: k for k, v in COLUNAS_PNADC.items()})[list(COLUNAS_PNADC.keys())]


def agregar_por_uf(agregado_rais: pd.DataFrame, de_para: pd.DataFrame, informalidade: pd.DataFrame | None) -> pd.DataFrame:
    # Base é sempre o universo TOTAL de municípios do de/para (todos os
    # 5.570), não só os que aparecem na RAIS agregada — senão a cobertura
    # nunca apareceria abaixo de 100%.
    df = de_para[["codigo_ibge_6", "uf_sigla"]].merge(agregado_rais, on="codigo_ibge_6", how="left")
    linhas = []
    for uf, g in df.groupby("uf_sigla"):
        n_total = len(g)
        n_com_dado = int(g["total_vinculos_ativos"].notna().sum())
        n_setor = int(g["adm_municipal_maior_que_maior_setor_privado"].fillna(False).sum())
        n_individual = int(g["adm_municipal_maior_que_maior_empregador_individual"].fillna(False).sum())
        linha = {
            "uf_sigla": uf,
            "n_municipios_total": n_total,
            "n_municipios_com_dado_rais": n_com_dado,
            "cobertura_rais_pct": n_com_dado / n_total if n_total else pd.NA,
            "pct_adm_maior_empregador_por_setor_sobre_com_dado": n_setor / n_com_dado if n_com_dado else pd.NA,
            "pct_adm_maior_empregador_por_setor_sobre_total_uf": n_setor / n_total if n_total else pd.NA,
            "pct_adm_maior_empregador_individual_sobre_com_dado": n_individual / n_com_dado if n_com_dado else pd.NA,
            "pct_adm_maior_empregador_individual_sobre_total_uf": n_individual / n_total if n_total else pd.NA,
            "media_pct_vinculos_adm_municipal": g["pct_vinculos_adm_municipal"].mean(skipna=True),
        }
        linhas.append(linha)
    uf_df = pd.DataFrame(linhas).sort_values("uf_sigla").reset_index(drop=True)
    if informalidade is not None:
        uf_df = uf_df.merge(informalidade, on="uf_sigla", how="left")
        uf_df["fonte_taxa_informalidade"] = "PNAD Contínua (contexto, fonte distinta da RAIS)"
    return uf_df


def main() -> None:
    log("=== 04_indicador3_empregador.py: início ===")
    de_para = carregar_de_para()
    arquivos_rais = encontrar_arquivos_rais()

    agregado_rais = agregar_rais_por_municipio(arquivos_rais)
    # Salva o subproduto que 03_indicador2_bolsafamilia.py também consulta,
    # para não obrigar o usuário a rodar 04 antes de 03 caso não precise
    # da terceira razão do indicador 2 na primeira passada.
    agregado_rais.to_csv(INTERIM / "rais_vinculos_totais_municipio.csv", index=False, encoding="utf-8")

    municipio = de_para.merge(agregado_rais, on="codigo_ibge_6", how="left")
    municipio.to_csv(OUT / "indicador3_empregador_municipio.csv", index=False, encoding="utf-8")

    informalidade = carregar_informalidade_pnadc()
    uf = agregar_por_uf(agregado_rais, de_para, informalidade)
    uf.to_csv(OUT / "indicador3_empregador_uf.csv", index=False, encoding="utf-8")

    log(f"OK: out/indicador3_empregador_municipio.csv ({len(municipio)} linhas), out/indicador3_empregador_uf.csv ({len(uf)} linhas)")
    log("=== 04_indicador3_empregador.py: fim ===")


if __name__ == "__main__":
    main()
