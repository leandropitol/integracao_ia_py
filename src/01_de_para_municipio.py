#!/usr/bin/env python3
"""
01_de_para_municipio.py — constrói data/interim/de_para_municipio.csv a
partir da malha oficial de municípios do IBGE (data/raw/ibge/municipios.json,
baixado por 00_download.py via API pública do IBGE).

Saída: uma linha por município brasileiro, com:
  - codigo_ibge_7        : código IBGE completo (7 dígitos, com dígito verificador)
  - codigo_ibge_6        : código sem o dígito verificador, usado por RAIS/CAGED/DATASUS
  - nome_municipio
  - uf_sigla
  - uf_codigo            : 2 primeiros dígitos do codigo_ibge_7

### Sobre a conversão 7 -> 6 dígitos

Não é um "zfill" nem um truncamento de string arbitrário: é a regra
OFICIAL documentada no layout da RAIS/CAGED e usada pelo DATASUS —
o código de 6 dígitos é o código IBGE completo SEM o último dígito, que é
o dígito verificador. Ou seja: codigo_ibge_6 = codigo_ibge_7 // 10.

Isso só é seguro porque:
1. Partimos da tabela OFICIAL do IBGE (não recalculamos o dígito
   verificador nós mesmos), então codigo_ibge_7 já é o valor correto.
2. Validamos abaixo que a operação produz 5.570 códigos de 6 dígitos
   ÚNICOS (nenhuma colisão) — se algum dia isso não bater (município novo
   com colisão, mudança na malha), o script PARA em vez de gerar um
   de/para furado silenciosamente.

Se algum órgão publicar um de/para 6<->7 divergente do que sai daqui, isso
é motivo para investigar manualmente, não para usar por padrão.
"""
from __future__ import annotations

import json

import pandas as pd

from _common import INTERIM, RAW, assert_columns, log, parar

MUNICIPIOS_JSON = RAW / "ibge" / "municipios.json"
SAIDA = INTERIM / "de_para_municipio.csv"

N_MUNICIPIOS_BRASIL_ESPERADO = 5570  # malha vigente à época de escrita deste script;
# se o IBGE criar/extinguir município, ajuste este número deliberadamente
# (nunca silenciosamente) após confirmar a mudança na malha oficial.


def carregar_municipios_ibge() -> pd.DataFrame:
    if not MUNICIPIOS_JSON.exists():
        parar(
            f"Arquivo não encontrado: {MUNICIPIOS_JSON}. Rode "
            f"'python src/00_download.py --somente malha_municipios_ibge' primeiro."
        )
    with open(MUNICIPIOS_JSON, encoding="utf-8") as f:
        dados = json.load(f)

    if not isinstance(dados, list) or not dados:
        parar(
            f"{MUNICIPIOS_JSON} não tem o formato esperado (lista JSON não-vazia "
            f"de objetos de município). Confira se o download não trouxe uma "
            f"página de erro no lugar do JSON."
        )

    # Formato conhecido da API servicodados.ibge.gov.br/api/v1/localidades/municipios:
    # cada item tem "id" (código de 7 dígitos), "nome", e uma estrutura
    # aninhada microrregiao/mesorregiao/UF (ou regiao-imediata/regiao-intermediaria
    # dependendo da versão da API). Extraímos de forma tolerante a essas duas
    # variações, mas paramos se nenhuma delas bater.
    linhas = []
    for item in dados:
        municipio_id = item.get("id")
        nome = item.get("nome")
        uf = None
        # variação 1: microrregiao -> mesorregiao -> UF
        try:
            uf = item["microrregiao"]["mesorregiao"]["UF"]
        except (KeyError, TypeError):
            pass
        # variação 2: regiao-imediata -> regiao-intermediaria -> UF
        if uf is None:
            try:
                uf = item["regiao-imediata"]["regiao-intermediaria"]["UF"]
            except (KeyError, TypeError):
                pass
        if municipio_id is None or nome is None or uf is None:
            parar(
                f"Item de município com estrutura inesperada, não foi possível "
                f"extrair id/nome/UF: {json.dumps(item, ensure_ascii=False)[:300]}\n"
                f"O layout da API do IBGE pode ter mudado — confira manualmente "
                f"antes de ajustar o parser."
            )
        linhas.append(
            {
                "codigo_ibge_7": int(municipio_id),
                "nome_municipio": nome,
                "uf_sigla": uf.get("sigla"),
                "uf_nome": uf.get("nome"),
            }
        )

    df = pd.DataFrame(linhas)
    assert_columns(df, ["codigo_ibge_7", "nome_municipio", "uf_sigla", "uf_nome"], "malha_municipios_ibge")
    return df


def construir_de_para(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if len(df) != N_MUNICIPIOS_BRASIL_ESPERADO:
        log(
            f"AVISO: malha trouxe {len(df)} municípios, esperado "
            f"{N_MUNICIPIOS_BRASIL_ESPERADO}. Se isso é uma mudança real na "
            f"divisão territorial (município novo/extinto), atualize "
            f"N_MUNICIPIOS_BRASIL_ESPERADO deliberadamente. Seguindo com o "
            f"valor real encontrado."
        )

    if df["codigo_ibge_7"].duplicated().any():
        dup = df[df["codigo_ibge_7"].duplicated(keep=False)]
        parar(f"codigo_ibge_7 duplicado na malha do IBGE — dados corrompidos:\n{dup}")

    df["codigo_ibge_6"] = df["codigo_ibge_7"] // 10
    df["uf_codigo"] = df["codigo_ibge_7"] // 100000

    if df["codigo_ibge_6"].duplicated().any():
        dup = df[df["codigo_ibge_6"].duplicated(keep=False)].sort_values("codigo_ibge_6")
        parar(
            "Colisão ao derivar codigo_ibge_6 (dropar o dígito verificador "
            "gerou códigos de 6 dígitos duplicados) — isso não deveria "
            "acontecer com a malha oficial do IBGE. Pare e investigue estes "
            f"municípios antes de seguir:\n{dup.to_string(index=False)}"
        )

    cols = ["codigo_ibge_7", "codigo_ibge_6", "nome_municipio", "uf_sigla", "uf_nome", "uf_codigo"]
    return df[cols].sort_values("codigo_ibge_7").reset_index(drop=True)


def main() -> None:
    log("=== 01_de_para_municipio.py: início ===")
    bruto = carregar_municipios_ibge()
    de_para = construir_de_para(bruto)
    de_para.to_csv(SAIDA, index=False, encoding="utf-8")
    log(f"OK: {len(de_para)} municípios -> {SAIDA}")
    log(
        f"Conferência: {de_para['codigo_ibge_7'].nunique()} códigos de 7 dígitos "
        f"únicos, {de_para['codigo_ibge_6'].nunique()} códigos de 6 dígitos únicos, "
        f"{de_para['uf_sigla'].nunique()} UFs."
    )
    log("=== 01_de_para_municipio.py: fim ===")


if __name__ == "__main__":
    main()
