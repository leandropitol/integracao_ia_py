"""
Configuração central de fontes: URLs, status de verificação e instruções
manuais quando o download não pode ser automatizado com segurança.

*** LEIA ANTES DE RODAR 00_download.py ***

Este arquivo foi escrito em uma sessão sem acesso à internet (política de
rede do ambiente bloqueava todo egress externo — ver README.md, seção
"Avisos de validação pendente"). As URLs abaixo vêm do conhecimento geral
sobre essas fontes públicas, não de uma inspeção ao vivo nesta execução.
Cada entrada tem um campo `status`:

  - "verificado_ao_vivo": a URL/layout foi conferida rodando o script.
  - "conhecido_estavel": API pública documentada e historicamente estável
    (ex.: servicodados.ibge.gov.br), mas não testada nesta sessão.
  - "requer_confirmacao": estrutura plausível, mas o padrão de URL exato
    (nome de arquivo, parâmetros) muda por edição/ano e PRECISA ser
    confirmado manualmente antes de rodar em produção.
  - "download_manual": a fonte não expõe um endpoint estável para
    download automatizado (ex.: app JS que gera export sob demanda) —
    o script espera o arquivo já colocado em data/raw/ pelo usuário,
    seguindo o nome de arquivo indicado.

Ao confirmar/corrigir uma URL, atualize o campo e mude o status para
"verificado_ao_vivo".
"""

FONTES = {
    "ifgf_firjan": {
        "descricao": "Índice Firjan de Gestão Fiscal (IFGF) — planilha por município",
        "pagina_referencia": "https://www.firjan.com.br/ifgf/",
        "url_download": None,  # TODO-VERIFICAR: pegar o link direto da seção
        # "Análises e Rankings" -> "Base de dados". O nome do arquivo muda
        # a cada edição (ex.: algo como
        # https://www.firjan.com.br/data/files/.../IFGF_2025_base_dados.xlsx).
        "status": "requer_confirmacao",
        "arquivo_local": "ifgf/ifgf_base_municipios.xlsx",
        "instrucoes_manuais": (
            "Acesse https://www.firjan.com.br/ifgf/ > Análises e Rankings > "
            "baixe a planilha-base por município (não o PDF do relatório) e "
            "salve em data/raw/ifgf/ifgf_base_municipios.xlsx"
        ),
    },
    "siconfi_dca": {
        "descricao": "Siconfi — Declaração de Contas Anuais (DCA), anexo de receitas orçamentárias",
        "pagina_referencia": "https://www.tesourotransparente.gov.br/consultas/consultas-siconfi/siconfi-api-de-dados-abertos",
        "api_base": "https://apidatalake.tesouro.gov.br/api/rest/rest.php",
        # Padrão de chamada documentado publicamente pelo Tesouro (API de
        # dados abertos do Siconfi): endpoint "/dca_receita_orcamentaria" ou
        # similar, parâmetros an_exercicio, no_anexo, id_ente (código IBGE).
        # TODO-VERIFICAR nome exato do path/endpoint e dos parâmetros na
        # execução da rota /docs/siconfi/ antes de rodar em lote nos ~5.570
        # municípios — considerar também o export "FINBRA" em lote (CSV
        # único por exercício) como alternativa mais barata que 5.570
        # chamadas de API.
        "status": "requer_confirmacao",
        "arquivo_local": "siconfi/dca_receitas_{exercicio}.csv",
        "instrucoes_manuais": (
            "Confirme o endpoint em http://apidatalake.tesouro.gov.br/docs/siconfi/ "
            "e, se existir, prefira o export consolidado (FINBRA/DCA) em "
            "https://www.tesourotransparente.gov.br em vez de laço por município."
        ),
    },
    "bolsafamilia_visdata": {
        "descricao": "VIS DATA / Painel de Dados do Bolsa Família (MDS) — famílias beneficiárias por município",
        "pagina_referencia": "https://aplicacoes.mds.gov.br/sagi/vis/data/index.php",
        "url_download": None,
        "status": "download_manual",
        "arquivo_local": "bolsafamilia/bf_familias_beneficiarias_{aaaa_mm}.csv",
        "instrucoes_manuais": (
            "VIS DATA é uma aplicação interativa (seleção de indicador + "
            "recorte + mês/ano + exportar). Não há um endpoint GET estável "
            "conhecido para essa exportação. Acesse o VIS DATA, selecione "
            "'Bolsa Família' > 'Famílias beneficiárias', recorte por "
            "município, mês de referência fixo, exporte CSV e salve em "
            "data/raw/bolsafamilia/bf_familias_beneficiarias_AAAA_MM.csv "
            "(o nome do arquivo DEVE conter o mês de referência)."
        ),
    },
    "censo2022_sidra": {
        "descricao": "Censo 2022 (IBGE/SIDRA) — domicílios particulares permanentes e população residente, por município",
        "pagina_referencia": "https://sidra.ibge.gov.br/",
        "api_base": "https://apisidra.ibge.gov.br/values",
        # TODO-VERIFICAR os números exatos das tabelas SIDRA do Censo 2022
        # para (a) população residente e (b) domicílios particulares
        # permanentes, no recorte município (nível geográfico N6). Não
        # assumir os números de tabela do Censo 2010 — mudaram.
        "status": "requer_confirmacao",
        "arquivo_local": "censo2022/censo2022_populacao_domicilios_municipio.csv",
        "instrucoes_manuais": (
            "Em sidra.ibge.gov.br, localize a tabela do Censo 2022 com "
            "'População residente' e a de 'Domicílios particulares "
            "permanentes', nível geográfico Município, confirme o número "
            "da tabela e ajuste TABELA_POPULACAO / TABELA_DOMICILIOS neste arquivo."
        ),
    },
    "malha_municipios_ibge": {
        "descricao": "Relação oficial de municípios do IBGE (código de 7 dígitos, nome, UF)",
        "url_download": "https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
        # API pública, documentada, em uso estável há anos — mas não
        # testada nesta sessão por bloqueio de rede.
        "status": "conhecido_estavel",
        "arquivo_local": "ibge/municipios.json",
        "instrucoes_manuais": None,
    },
    "rais_microdados": {
        "descricao": "RAIS — microdados de vínculos ativos em 31/12, por UF",
        "pagina_referencia": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho",
        "ftp_base": "ftp://ftp.mtps.gov.br/pdet/microdados/RAIS/",
        # Layout historicamente estável (arquivos .7z por UF, texto
        # delimitado por ';', encoding latin-1), mas o ano mais recente
        # disponível e o nome exato dos arquivos por UF devem ser
        # confirmados no FTP antes de baixar as 27 UFs.
        "status": "requer_confirmacao",
        "arquivo_local": "rais/RAIS_VINC_PUB_{uf}.txt",
        "instrucoes_manuais": (
            "Liste ftp://ftp.mtps.gov.br/pdet/microdados/RAIS/ , confirme o "
            "ano mais recente e o padrão de nome de arquivo por UF (pode "
            "vir como .7z — necessário extrair com py7zr/7z antes de ler)."
        ),
    },
    "caged_estoque_fallback": {
        "descricao": "Novo CAGED — estoque de vínculos (fallback caso RAIS do ano-alvo não esteja disponível)",
        "pagina_referencia": "http://pdet.mte.gov.br/novo-caged",
        "status": "download_manual",
        "arquivo_local": "caged/caged_estoque_{aaaa_mm}.txt",
        "instrucoes_manuais": "Usar somente se a RAIS do ano-alvo não estiver publicada.",
    },
    "cempre_ibge_validacao": {
        "descricao": "CEMPRE/IBGE — pessoal ocupado por seção CNAE, recorte municipal (validação cruzada do indicador 3)",
        "pagina_referencia": "https://www.ibge.gov.br/estatisticas/economicas/comercio/9014-cadastro-central-de-empresas.html",
        "status": "requer_confirmacao",
        "arquivo_local": "cempre/cempre_municipio.csv",
        "instrucoes_manuais": "Confirmar tabela SIDRA do CEMPRE mais recente com recorte municipal e seção CNAE.",
    },
    "pnad_continua_informalidade": {
        "descricao": "PNAD Contínua — taxa de informalidade por UF (coluna de contexto do indicador 3)",
        "pagina_referencia": "https://sidra.ibge.gov.br/pesquisa/pnadct/tabelas",
        "status": "requer_confirmacao",
        "arquivo_local": "pnadc/pnadc_informalidade_uf.csv",
        "instrucoes_manuais": "Confirmar tabela SIDRA da PNAD Contínua trimestral com taxa de informalidade por UF.",
    },
    "concla_natureza_juridica": {
        "descricao": "Concla/IBGE — tabela de Natureza Jurídica vigente (para isolar códigos da administração municipal)",
        "pagina_referencia": "https://concla.ibge.gov.br/estrutura/natjur-estrutura/natureza-juridica-2021",
        "status": "requer_confirmacao",
        "arquivo_local": "concla/natureza_juridica.csv",
        "instrucoes_manuais": (
            "Baixar a tabela vigente de Natureza Jurídica do Concla e "
            "conferir os códigos usados em CODIGOS_NATUREZA_JURIDICA_MUNICIPAL "
            "no topo de 04_indicador3_empregador.py ANTES de rodar — "
            "não confiar nos códigos de memória (ver instrução original)."
        ),
    },
}
