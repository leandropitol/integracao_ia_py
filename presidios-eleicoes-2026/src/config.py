"""
Configuração central: padrões de nome de local prisional, categorização de
tipos penais, lista de presídios-foco, e mapeamento de colunas esperado em
cada fonte.

*** LAYOUTS NÃO VERIFICADOS *** — nenhum arquivo real do TSE ou SISDEPEN foi
inspecionado ainda nesta sessão. Os mapeamentos abaixo são o ponto de
partida; ajuste assim que os primeiros arquivos reais chegarem e
`assert_columns` apontar divergência.
"""
from __future__ import annotations
import re

# --- padrões para identificar seção eleitoral em estabelecimento penal ---
# Usado quando o campo de tipo de local (se existir no arquivo de
# eleitorado) não distinguir "seção especial de presos provisórios"
# explicitamente.
PADROES_NOME_PRESIDIO = [
    r"PENITENCIARI", r"PRESIDIO", r"\bCDP\b", r"CADEIA PUBLICA",
    r"COMPLEXO PENITENCIARI", r"CENTRO DE DETENCAO", r"CASA DE DETENCAO",
    r"CENTRO DE RECUPERACAO", r"CENTRO DE PROGRESSAO PENITENCIARI",
    r"COLONIA PENAL", r"HOSPITAL DE CUSTODIA", r"FUNDACAO CASA", r"\bCASE\b",
    r"CENTRO SOCIOEDUCATIVO", r"UNIDADE PRISIONAL", r"ESTABELECIMENTO PRISIONAL",
    r"PRESIDIO REGIONAL", r"INSTITUTO PENAL",
]
REGEX_PRESIDIO = re.compile("|".join(PADROES_NOME_PRESIDIO), re.IGNORECASE)


def normalizar_nome(s: str) -> str:
    """Remove acentos, caixa alta, espaços múltiplos — para o fuzzy match
    e para a checagem de padrão de nome. Não expande abreviação aqui (isso
    fica em EXPANSOES, aplicado à parte, porque abreviação errada pode
    mudar o sentido e precisa ser revisável)."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    s = s.upper().strip()
    s = re.sub(r"\s+", " ", s)
    return s


# Abreviações comuns nos nomes do TSE e/ou SISDEPEN — expandidas antes do
# fuzzy match para aumentar a chance de casar o mesmo estabelecimento
# escrito de formas diferentes nas duas bases.
EXPANSOES = {
    r"\bPEN\b": "PENITENCIARIA",
    r"\bPENIT\b": "PENITENCIARIA",
    r"\bCDP\b": "CENTRO DE DETENCAO PROVISORIA",
    r"\bC\.D\.P\b": "CENTRO DE DETENCAO PROVISORIA",
    r"\bCOMP\b": "COMPLEXO",
    r"\bFEM\b": "FEMININA",
    r"\bMASC\b": "MASCULINA",
    r"\bEST\b": "ESTABELECIMENTO",
    r"\bP\.?1\b": "I",
    r"\bP\.?2\b": "II",
}


def expandir_abreviacoes(nome_normalizado: str) -> str:
    out = nome_normalizado
    for padrao, substituto in EXPANSOES.items():
        out = re.sub(padrao, substituto, out)
    return re.sub(r"\s+", " ", out).strip()


# --- categorização de tipos penais (item 5.14 SISDEPEN) ---
# Chave = categoria final; valor = lista de padrões (regex, case-insensitive)
# que casam a descrição do tipo penal como publicada pelo SISDEPEN.
# TODO-VERIFICAR contra os rótulos reais do arquivo 5.14 — SISDEPEN descreve
# o tipo penal em texto livre (não um código fechado), então a lista de
# padrões provavelmente vai precisar de ajuste/ampliação no primeiro arquivo real.
CATEGORIAS_TIPO_PENAL = {
    "drogas": [r"trafic", r"11\.?343", r"entorpecente", r"drogas"],
    "patrimonio": [r"roubo", r"furto", r"latroc", r"extors", r"receptac", r"estelionat"],
    "contra_pessoa": [r"homicid", r"les(a|ã)o corporal", r"feminicid"],
    "dignidade_sexual": [r"estupro", r"abuso sexual", r"importuna", r"dignidade sexual"],
    "armas": [r"arma de fogo", r"desarmamento", r"10\.?826"],
    "violencia_domestica": [r"maria da penha", r"11\.?340", r"violencia domestic"],
    "organizacao_criminosa": [r"organiza(c|ç)[aã]o criminosa", r"associa(c|ç)[aã]o.*trafic", r"12\.?850"],
}
CATEGORIA_RESIDUAL = "outros"


def categorizar_tipo_penal(descricao: str) -> str:
    desc = normalizar_nome(descricao)
    for categoria, padroes in CATEGORIAS_TIPO_PENAL.items():
        for p in padroes:
            if re.search(normalizar_nome(p), desc, re.IGNORECASE):
                return categoria
    return CATEGORIA_RESIDUAL


# --- presídios-foco (fichas individuais obrigatórias no relatório) ---
# Nome como citado pelo usuário + UF, para localizar no matching. O nome
# exato na base pode diferir — a busca usa fuzzy match sobre estes termos,
# não igualdade exata.
PRESIDIOS_FOCO = [
    {"nome_busca": "Complexo Penitenciário da Papuda", "uf": "DF", "secao_tse": "0420", "zona_tse": "18"},
    {"nome_busca": "Penitenciária Feminina II de Tremembé", "uf": "SP"},
    {"nome_busca": "Penitenciária I de Tremembé", "uf": "SP"},
    {"nome_busca": "Penitenciária II de Potim", "uf": "SP"},
    {"nome_busca": "Unidade prisional de Caraguatatuba", "uf": "SP"},
    {"nome_busca": "Unidade prisional de Goianésia", "uf": "GO"},
    {"nome_busca": "CDP Feminino de Natal", "uf": "RN"},
]
# "Todas as 17 seções do RS", "10 maiores em votos válidos" e "24 unidades
# onde Flávio venceu" não são uma lista fixa de nomes — são calculadas em
# 05_consolida_relatorio.py a partir da base cruzada já pronta.
N_SECOES_RS_ESPERADO = 17

# --- referência para checagem do universo nacional (regra obrigatória) ---
REFERENCIA_TOTAL_VOTOS_VALIDOS = 11_200
REFERENCIA_PCT_LULA = 0.726
REFERENCIA_PCT_FLAVIO = 0.233
TOLERANCIA_REFERENCIA = 0.15  # 15% de margem antes de disparar alerta p/ investigar filtro


# --- mapeamento de colunas esperado em cada fonte (TODO-VERIFICAR) ---
# TSE "Eleitorado por local de votação" — layout historicamente estável do
# pacote de dados abertos do TSE (campos em maiúsculas, separador ';',
# encoding latin-1), mas não conferido nesta sessão.
COLUNAS_TSE_ELEITORADO = {
    "uf": "SG_UF",
    "codigo_municipio_tse": "CD_MUNICIPIO",
    "nome_municipio": "NM_MUNICIPIO",
    "zona": "NR_ZONA",
    "secao": "NR_SECAO",
    "nome_local": "NM_LOCAL_VOTACAO",
    "endereco": "DS_ENDERECO",
    "quantidade_eleitores": "QT_ELEITORES_PERFIL",
}

# TSE "Votação por seção eleitoral" 1º turno — uma linha por candidato por
# seção (formato longo).
COLUNAS_TSE_VOTACAO = {
    "uf": "SG_UF",
    "codigo_municipio_tse": "CD_MUNICIPIO",
    "zona": "NR_ZONA",
    "secao": "NR_SECAO",
    "cargo": "DS_CARGO",
    "numero_candidato": "NR_VOTAVEL",
    "nome_candidato": "NM_VOTAVEL",
    "votos": "QT_VOTOS",
}
CARGOS_DE_INTERESSE = {"PRESIDENTE", "GOVERNADOR", "SENADOR"}
# Rótulos usados pelo TSE para linhas que não são voto em candidato —
# TODO-VERIFICAR os textos exatos (podem vir como NM_VOTAVEL ou como
# DS_CARGO/coluna própria dependendo da edição).
ROTULOS_BRANCO = {"BRANCO"}
ROTULOS_NULO = {"NULO"}

# SISDEPEN — item 5.14 e dados de população prisional. O SISDEPEN
# historicamente publica como planilha Excel com uma aba por item; os
# nomes de coluna abaixo são um ponto de partida plausível.
COLUNAS_SISDEPEN_TIPO_PENAL = {
    "uf": "UF",
    "nome_unidade": "Estabelecimento Penal",
    "tipo_penal": "Tipo Penal",
    "genero": "Sexo",
    "quantidade": "Quantidade de Incidências",
}
COLUNAS_SISDEPEN_POPULACAO = {
    "uf": "UF",
    "nome_unidade": "Estabelecimento Penal",
    "populacao_total": "População Prisional",
    "presos_provisorios": "Presos Provisórios",
    "regime": "Regime",
    "genero_unidade": "Sexo",
    "municipio": "Município",
}
