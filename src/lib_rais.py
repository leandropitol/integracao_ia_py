"""
lib_rais.py — carregamento e agregação da RAIS, compartilhado entre
03_indicador2_bolsafamilia.py (que só precisa do total de vínculos formais
ativos por município) e 04_indicador3_empregador.py (que precisa do
detalhe por natureza jurídica / CNAE / CNPJ raiz).

Ficar num módulo à parte evita duas cópias divergentes da mesma lógica de
leitura da RAIS, e resolve a dependência circular de numeração: o
indicador 2 usa vínculos formais como denominador de uma das razões, mas
esse número é, na prática, um subproduto do processamento da RAIS que o
indicador 3 também faz — em vez de o script 03 depender da ordem de
execução do script 04, os dois chamam esta função.

*** LAYOUT NÃO VERIFICADO AO VIVO NESTA SESSÃO ***
Os nomes de coluna abaixo (COLUNAS_RAIS) refletem o layout historicamente
documentado no "Manual de Orientação RAIS" (arquivo texto delimitado por
';', encoding latin-1, uma linha por vínculo). Confirme contra o arquivo
real de 00_download.py antes de rodar em produção — se os nomes de coluna
tiverem mudado, assert_columns vai parar o pipeline com uma mensagem clara
em vez de deixar passar uma agregação errada.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from _common import RAW, assert_columns, log, parar

RAIS_DIR = RAW / "rais"
ENCODING_RAIS = "latin-1"
SEP_RAIS = ";"
CHUNKSIZE = 500_000

COLUNAS_RAIS = {
    "codigo_ibge_6": "Município",
    "natureza_juridica": "Natureza Jurídica",
    "cnae_secao": "CNAE 2.0 Seção",
    "cnpj_raiz": "CNPJ Raiz",
    "vinculo_ativo_31_12": "Vínculo Ativo 31/12",
}

# Códigos de Natureza Jurídica (Concla/IBGE) que caracterizam
# especificamente a administração pública MUNICIPAL — não confundir com
# administração federal/estadual instalada no território (por isso não se
# usa CNAE seção O para isso, conforme instrução original do projeto).
#
# *** TODO-VERIFICAR contra a tabela vigente do Concla
# (https://concla.ibge.gov.br/estrutura/natjur-estrutura) ANTES de rodar.
# Os códigos abaixo (formato 1xxx-x da Natureza Jurídica 2021 do Concla)
# são o ponto de partida a partir da estrutura conhecida da administração
# pública municipal — não foram conferidos linha a linha nesta sessão. ***
CODIGOS_NATUREZA_JURIDICA_MUNICIPAL = [
    "1104-6",  # Órgão Público do Poder Executivo Municipal
    "1105-4",  # Órgão Público do Poder Legislativo Municipal
    "1113-5",  # Autarquia Municipal
    "1120-8",  # Fundação Pública de Direito Público Municipal
    "1139-6",  # Fundação Pública de Direito Privado Municipal
    "1236-8",  # Fundo Público Municipal (conferir vigência/aplicabilidade)
    "3999-1",  # NÃO deve estar aqui em produção — placeholder para lembrar
    # de conferir também autarquias e empresas públicas municipais que às
    # vezes usam código de natureza jurídica de "Empresa Pública" (2011-8)
    # mas capital 100% municipal. Decidir e documentar no README como essa
    # borda foi tratada antes de considerar o indicador 3 final.
]


def _validar_arquivo(caminho: Path) -> None:
    if not caminho.exists():
        parar(
            f"Arquivo RAIS não encontrado: {caminho}. Rode 00_download.py "
            f"para a fonte 'rais_microdados' (ou confirme manualmente o "
            f"nome do arquivo por UF no FTP do MTE)."
        )


def agregar_rais_por_municipio(arquivos_uf: list[Path]) -> pd.DataFrame:
    """
    Lê um ou mais arquivos de microdados da RAIS (um por UF) em chunks e
    devolve um DataFrame agregado por município com:
      - total_vinculos_ativos
      - vinculos_adm_municipal
      - vinculos_maior_secao_cnae_privada   (contagem da maior seção CNAE
        excluindo a própria administração pública)
      - secao_cnae_maior_privada            (qual seção é essa)
      - vinculos_prefeitura_cnpj_raiz       (soma por CNPJ raiz cuja
        natureza jurídica é municipal — aproxima "vínculos da prefeitura
        agregada por CNPJ raiz")
      - vinculos_maior_cnpj_raiz_privado
      - cnpj_raiz_maior_privado

    Filtra sempre por Vínculo Ativo 31/12 == 1 (define "emprego formal
    atual" como vínculo ativo no fim do ano-base).
    """
    if not arquivos_uf:
        parar("Nenhum arquivo de UF da RAIS foi passado para agregação.")

    # Acumuladores em nível (município, chave) — muito menores que os
    # microdados originais, então cabem em memória mesmo somando todas as UFs.
    acc_total = {}
    acc_adm_municipal = {}
    acc_por_secao = {}       # (municipio, secao) -> contagem, secao != adm. municipal
    acc_por_cnpj_raiz = {}   # (municipio, cnpj_raiz, is_municipal) -> contagem

    colunas_esperadas = list(COLUNAS_RAIS.values())

    for caminho in arquivos_uf:
        _validar_arquivo(caminho)
        log(f"Lendo RAIS: {caminho.name}")
        primeiro_chunk = True
        for chunk in pd.read_csv(
            caminho,
            sep=SEP_RAIS,
            encoding=ENCODING_RAIS,
            dtype=str,
            chunksize=CHUNKSIZE,
        ):
            if primeiro_chunk:
                assert_columns(chunk, colunas_esperadas, f"rais:{caminho.name}")
                primeiro_chunk = False
            chunk = chunk.rename(columns={v: k for k, v in COLUNAS_RAIS.items()})

            chunk["vinculo_ativo_31_12"] = pd.to_numeric(chunk["vinculo_ativo_31_12"], errors="coerce")
            chunk = chunk[chunk["vinculo_ativo_31_12"] == 1]
            if chunk.empty:
                continue

            chunk["codigo_ibge_6"] = pd.to_numeric(chunk["codigo_ibge_6"], errors="coerce").astype("Int64")
            chunk["is_municipal"] = chunk["natureza_juridica"].isin(CODIGOS_NATUREZA_JURIDICA_MUNICIPAL)

            for muni, n in chunk.groupby("codigo_ibge_6").size().items():
                acc_total[muni] = acc_total.get(muni, 0) + int(n)

            for muni, n in chunk[chunk["is_municipal"]].groupby("codigo_ibge_6").size().items():
                acc_adm_municipal[muni] = acc_adm_municipal.get(muni, 0) + int(n)

            nao_municipal = chunk[~chunk["is_municipal"]]
            for (muni, secao), n in nao_municipal.groupby(["codigo_ibge_6", "cnae_secao"]).size().items():
                key = (muni, secao)
                acc_por_secao[key] = acc_por_secao.get(key, 0) + int(n)

            for (muni, cnpj, is_muni), n in chunk.groupby(["codigo_ibge_6", "cnpj_raiz", "is_municipal"]).size().items():
                key = (muni, cnpj, is_muni)
                acc_por_cnpj_raiz[key] = acc_por_cnpj_raiz.get(key, 0) + int(n)

    if not acc_total:
        parar(
            "Nenhum vínculo ativo em 31/12 foi lido de nenhum arquivo RAIS "
            "fornecido. Confira se o filtro de coluna/valor de "
            "'Vínculo Ativo 31/12' está correto (ex.: pode vir como '1'/'0' "
            "ou 'Sim'/'Não' dependendo da edição)."
        )

    municipios = sorted(acc_total.keys())
    linhas = []
    for muni in municipios:
        total = acc_total.get(muni, 0)
        adm = acc_adm_municipal.get(muni, 0)

        secoes_muni = {s: n for (m, s), n in acc_por_secao.items() if m == muni}
        if secoes_muni:
            secao_maior, n_secao_maior = max(secoes_muni.items(), key=lambda kv: kv[1])
        else:
            secao_maior, n_secao_maior = pd.NA, 0

        cnpjs_muni_privado = {c: n for (m, c, is_muni), n in acc_por_cnpj_raiz.items() if m == muni and not is_muni}
        if cnpjs_muni_privado:
            cnpj_maior, n_cnpj_maior = max(cnpjs_muni_privado.items(), key=lambda kv: kv[1])
        else:
            cnpj_maior, n_cnpj_maior = pd.NA, 0

        linhas.append(
            {
                "codigo_ibge_6": muni,
                "total_vinculos_ativos": total,
                "vinculos_adm_municipal": adm,
                "pct_vinculos_adm_municipal": adm / total if total else pd.NA,
                "secao_cnae_maior_privada": secao_maior,
                "vinculos_maior_secao_cnae_privada": n_secao_maior,
                "cnpj_raiz_maior_privado": cnpj_maior,
                "vinculos_maior_cnpj_raiz_privado": n_cnpj_maior,
                "adm_municipal_maior_que_maior_setor_privado": adm > n_secao_maior,
                "adm_municipal_maior_que_maior_empregador_individual": adm > n_cnpj_maior,
            }
        )

    return pd.DataFrame(linhas)
