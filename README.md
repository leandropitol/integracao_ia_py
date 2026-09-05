# Dependência estrutural dos municípios brasileiros

Pipeline reprodutível para medir, por município e agregado por UF, três
dimensões de dependência estrutural da economia local em relação ao poder
público:

1. **Autossustentação fiscal** — % de municípios cuja receita própria não
   cobre o custo mínimo da máquina pública (nota zero no IFGF Autonomia /
   Firjan) e grau de dependência de transferências (Siconfi/DCA).
2. **Dependência de transferência de renda** — penetração do Bolsa Família
   sobre domicílios/população (Censo 2022) e sobre vínculos formais (RAIS).
3. **Estado como principal empregador** — % de municípios em que a
   administração pública municipal é o maior empregador formal, por setor
   (CNAE) e por empregador individual (CNPJ raiz), a partir da RAIS filtrada
   por natureza jurídica. **Indicador central do projeto — não existe
   publicado, é calculado aqui.**

## Status atual do projeto

> **Bloqueado em: reconhecimento das fontes (etapa anterior a qualquer parser).**

Esta sessão de execução (ambiente cloud do Claude Code) tem a política de
rede configurada para **bloquear todo egress HTTPS externo** — não é algo
específico das fontes deste projeto: tentativas de acesso a
`firjan.com.br`, `tesouro.gov.br`, `ibge.gov.br`, `mds.gov.br` e até
`google.com`/`wikipedia.org` retornaram `403 connect_rejected` no proxy de
egress da organização.

Por isso, seguindo a regra combinada de **nunca escrever um parser sem antes
inspecionar o arquivo real**, nenhum script de download ou de tratamento foi
escrito ainda. Os próximos passos, na ordem em que devem ser retomados assim
que houver acesso à internet (ambiente com network policy liberada, ou
arquivos de amostra fornecidos manualmente):

1. Baixar **um arquivo de cada fonte** (IFGF/Firjan, Siconfi/DCA, VIS
   DATA/MDS, malha de municípios IBGE, RAIS) e mostrar as primeiras linhas e
   a lista de colunas para validação antes de codar qualquer parser.
2. `src/00_download.py` — download versionado com registro em
   `data/raw/MANIFEST.md` (URL, data, SHA-256).
3. `src/01_de_para_municipio.py` — tabela de conversão de código IBGE
   6↔7 dígitos a partir da malha oficial (DTB/IBGE), nunca por `zfill`/truncamento.
4. `src/02_indicador1_fiscal.py`, `03_indicador2_bolsafamilia.py`,
   `04_indicador3_empregador.py`, `05_consolida_e_dashboard.py`.

## Estrutura do repositório

```
.
├── data/raw/          # imutável, + MANIFEST.md (URL, data, SHA-256 de cada arquivo)
├── data/interim/      # dados intermediários tratados, derivados de data/raw
├── src/
│   ├── 00_download.py
│   ├── 01_de_para_municipio.py
│   ├── 02_indicador1_fiscal.py
│   ├── 03_indicador2_bolsafamilia.py
│   ├── 04_indicador3_empregador.py
│   └── 05_consolida_e_dashboard.py
├── out/               # CSVs finais por indicador + consolidado + dashboard.html
├── requirements.txt
└── README.md
```

## Regras do pipeline (valem para todos os scripts)

- **Nunca preencher dado faltante** com estimativa, interpolação ou valor de
  outra fonte. Ausência é `NA` explícito. Toda tabela agregada por UF traz
  `n_municipios_com_dado` / `n_municipios_total`.
- **Chave de junção:** código IBGE de 7 dígitos. Bases do Ministério do
  Trabalho (RAIS/CAGED) usam 6 dígitos (sem dígito verificador) — a conversão
  é feita via `de_para_municipio.csv`, construído a partir da malha oficial
  do IBGE, nunca por `zfill` ou truncamento.
- **Percentuais por UF sempre com denominador declarado no nome da coluna**
  (ex.: `pct_nota_zero_sobre_analisados` ≠ `pct_nota_zero_sobre_total_uf`).
- `data/raw/` é imutável — nada de editar arquivo baixado.
- Falha de download ou mudança de layout: o pipeline **para e avisa**, não
  inventa parser alternativo silenciosamente.

## Fontes previstas

| Indicador | Fonte primária | Fonte(s) complementar(es) |
|---|---|---|
| 1a — IFGF Autonomia | Firjan, `firjan.com.br/ifgf` | — |
| 1b — Dependência de transferências | Siconfi/DCA (Tesouro Nacional) | — |
| 2 — Bolsa Família | VIS DATA / Painel MDS | Censo 2022 (SIDRA/IBGE), RAIS (indicador 3) |
| 3 — Adm. pública como maior empregador | RAIS (microdados, vínculos ativos) | Novo CAGED (fallback), CEMPRE/IBGE (validação cruzada), PNAD Contínua (informalidade, contexto) |

Metodologia detalhada, cortes exatos, limitações e divergências conhecidas
entre fontes serão documentados aqui à medida que cada indicador for
implementado e validado com dados reais.
