# Dependência estrutural dos municípios brasileiros

Pipeline reprodutível para medir, por município e agregado por UF, três
dimensões de dependência estrutural da economia local em relação ao poder
público.

## ⚠️ Status: pipeline construído sem acesso à internet — validação pendente

Este pipeline foi escrito numa sessão cujo ambiente de execução bloqueava
todo acesso HTTPS externo (política de rede do ambiente cloud, não das
fontes em si — `google.com` e `wikipedia.org` também foram bloqueados no
teste). Isso significa que **nenhuma URL, nenhum nome de coluna e nenhum
layout de arquivo abaixo foi conferido contra o dado real**. O código foi
escrito para ser correto na lógica e seguro por padrão — cada script para
com uma mensagem clara (`PipelineParadoError`) em vez de seguir com uma
suposição errada — mas isso não substitui a conferência real.

**Antes de considerar qualquer saída deste pipeline confiável, resolva o
checklist abaixo, na ordem:**

| # | Item | Onde está o TODO no código |
|---|---|---|
| 1 | Link direto da planilha-base do IFGF (Firjan) — o nome do arquivo muda por edição | `src/config_fontes.py` → `ifgf_firjan` |
| 2 | Endpoint/parâmetros reais da API do Siconfi para o anexo de receitas da DCA (ou export FINBRA em lote) | `src/config_fontes.py` → `siconfi_dca` |
| 3 | Nomes exatos das contas contábeis que compõem "receita própria" no anexo da DCA | `src/02_indicador1_fiscal.py` → `CONTAS_RECEITA_PROPRIA` |
| 4 | Nome/aba real das colunas na planilha do IFGF | `src/02_indicador1_fiscal.py` → `COLUNAS_IFGF` |
| 5 | VIS DATA/MDS não tem endpoint estável conhecido — exportação é manual pela interface | `src/config_fontes.py` → `bolsafamilia_visdata` |
| 6 | Números das tabelas SIDRA do Censo 2022 (população e domicílios, nível município) | `src/config_fontes.py` → `censo2022_sidra` |
| 7 | Nome exato dos arquivos da RAIS por UF no FTP do MTE e se vêm como `.7z` | `src/config_fontes.py` → `rais_microdados` |
| 8 | Nomes de coluna do layout da RAIS (`Município`, `Natureza Jurídica`, `CNAE 2.0 Seção`, `CNPJ Raiz`, `Vínculo Ativo 31/12`) | `src/lib_rais.py` → `COLUNAS_RAIS` |
| 9 | **Códigos de Natureza Jurídica que isolam a administração municipal** — conferir contra a tabela vigente do Concla, não usar de memória | `src/lib_rais.py` → `CODIGOS_NATUREZA_JURIDICA_MUNICIPAL` |
| 10 | Tabela SIDRA da PNAD Contínua usada para a informalidade por UF (coluna de contexto) | `src/04_indicador3_empregador.py` → `COLUNAS_PNADC` |

O pipeline inteiro foi testado de ponta a ponta com dados **fictícios**
(gerados só para validar a lógica, nunca commitados) — a mecânica de
junção, os denominadores declarados, os flags de cobertura e o dashboard
funcionam. O que falta é apontar cada script para o dado real e ajustar os
mapeamentos de coluna quando `assert_columns` acusar divergência.

## Objetivo

Medir três indicadores, sempre com resultado agregado **por UF (27
linhas)** e com o detalhe municipal preservado:

1. **Autossustentação fiscal** — % de municípios cuja receita própria não
   cobre o custo mínimo da máquina pública.
2. **Dependência de transferência de renda** — % de municípios com alta
   penetração do Bolsa Família na população/domicílios.
3. **Estado como principal empregador** — % de municípios em que a
   administração pública municipal é o maior empregador formal da cidade.
   **Indicador central do projeto — não existe publicado, é calculado aqui.**

## Estrutura do repositório

```
.
├── data/raw/          # imutável, + MANIFEST.md (URL, data, SHA-256 de cada arquivo)
├── data/interim/      # produtos intermediários (de/para, agregados da RAIS)
├── src/
│   ├── _common.py               # paths, log, PipelineParadoError, assert_columns, manifesto
│   ├── config_fontes.py         # URLs e status de verificação de cada fonte
│   ├── lib_rais.py              # leitura/agregação da RAIS (compartilhada por 03 e 04)
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

### Ordem de execução

```
pip install -r requirements.txt
python src/00_download.py
python src/01_de_para_municipio.py
python src/02_indicador1_fiscal.py
python src/04_indicador3_empregador.py   # roda antes do 03 de propósito, ver nota abaixo
python src/03_indicador2_bolsafamilia.py
python src/05_consolida_e_dashboard.py
```

**Por que 04 antes de 03, apesar da numeração?** O indicador 2 usa
`familias_bf / vinculos_formais_ativos` como uma de suas três razões, e
esse total de vínculos formais é um subproduto do processamento da RAIS
que o indicador 3 já faz. Os dois scripts chamam a mesma função
(`lib_rais.agregar_rais_por_municipio`) para não duplicar a lógica de
leitura. Se você rodar `03` antes de `04`, ele calcula sozinho o que
precisar (mais lento) ou, na ausência dos brutos da RAIS, deixa aquela
razão como `NA` e segue — nunca trava o resto do indicador 2 por causa
disso.

## Regras do pipeline

- **Nunca preencher dado faltante** com estimativa, interpolação ou valor
  de outra fonte. Ausência é `NA` explícito. Toda tabela agregada por UF
  traz `n_municipios_com_dado` / `n_municipios_total`.
- **Chave de junção:** código IBGE de 7 dígitos. RAIS/CAGED usam 6 dígitos
  (sem dígito verificador) — a conversão é feita em
  `01_de_para_municipio.py` a partir da malha oficial do IBGE
  (`codigo_ibge_6 = codigo_ibge_7 // 10`, a regra documentada no layout da
  RAIS, não um truncamento arbitrário), com verificação de unicidade —
  se colidir, o pipeline para.
- **Percentuais por UF sempre com denominador declarado no nome da
  coluna** (ex.: `pct_nota_zero_sobre_ifgf_analisados` ≠
  `pct_nota_zero_sobre_total_uf`).
- `data/raw/` é imutável — nada de editar arquivo baixado.
- Falha de download, layout mudado ou schema divergente: o pipeline
  **para e avisa** (`PipelineParadoError`), nunca segue com um parser
  alternativo inventado.

## Indicador 1 — Autossustentação fiscal

Duas medidas independentes e **propositalmente não reconciliadas** —a
discordância entre elas é informação:

- **1a. IFGF Autonomia (Firjan):** % de municípios com nota zero em
  Autonomia. A cobertura por UF é reportada explicitamente
  (`cobertura_ifgf_pct`), e UFs abaixo de 90% são sinalizadas
  (`alerta_cobertura_ifgf_abaixo_90pct`) — a hipótese de trabalho é que a
  ausência de dado não é aleatória entre UFs (municípios que não prestam
  contas ao Siconfi tendem a ser os mais frágeis).
- **1b. Grau de dependência de transferências (Siconfi/DCA):** receita
  própria (impostos de competência municipal + taxas + contribuição de
  melhoria + COSIP, excluindo transferências, cota-parte, FPM, royalties e
  aplicação financeira) sobre receita corrente total. Cortes em ≤20% e
  ≥90% de dependência.

Saída: `out/indicador1_fiscal_municipio.csv`, `out/indicador1_fiscal_uf.csv`.

## Indicador 2 — Penetração do Bolsa Família

Três razões por município: famílias/domicílios (Censo 2022), pessoas/população
(Censo 2022), famílias/vínculos formais ativos (RAIS). Por UF, % de
municípios acima de 30%, 50% e 80% dos domicílios.

**Flag de anomalia:** municípios com razão acima de 100% dos domicílios
são mantidos e marcados em `flag_razao_acima_100` — nunca excluídos, nunca
tratados como erro de dado (podem refletir subcontagem do Censo em área
rural dispersa, cadastro desatualizado ou fraude; a causa não é assumida).

Saída: `out/indicador2_bolsafamilia_municipio.csv`, `out/indicador2_bolsafamilia_uf.csv`.

## Indicador 3 — Administração pública municipal como maior empregador

O indicador central do projeto. Duas definições de "maior empregador",
calculadas em paralelo porque divergem e ambas são defensáveis:

- **(a) Por setor:** vínculos da administração municipal vs. maior seção
  CNAE privada do município.
- **(b) Por empregador individual:** vínculos da prefeitura (CNPJ raiz)
  vs. maior CNPJ raiz privado do município.

**O vínculo municipal é isolado por Natureza Jurídica, não por CNAE** — a
seção CNAE "O" mistura administração federal, estadual e municipal
instaladas no mesmo território, o que infla o resultado em capitais e
cidades com guarnição militar, campus federal ou unidade estadual. Os
códigos de Natureza Jurídica usados estão em
`src/lib_rais.py::CODIGOS_NATUREZA_JURIDICA_MUNICIPAL` — **precisam ser
conferidos contra a tabela vigente do Concla antes de rodar** (item 9 do
checklist acima).

### Limitação metodológica obrigatória

A RAIS só enxerga o emprego **formal**. Onde a informalidade é alta —
Norte, Nordeste, municípios rurais pequenos — o peso relativo do setor
público aparece superestimado frente à ocupação real. Isso **não é
corrigido por estimativa**; a taxa de informalidade da PNAD Contínua é
trazida como coluna de contexto (`taxa_informalidade`,
`fonte_taxa_informalidade`), claramente marcada como fonte diferente, não
como correção do indicador.

Saída: `out/indicador3_empregador_municipio.csv`, `out/indicador3_empregador_uf.csv`.

## Saídas finais

1. `out/consolidado_uf.csv` — 27 linhas (uma por UF) com os três
   indicadores lado a lado e as colunas de cobertura.
2. `out/consolidado_municipio.csv` — base municipal completa.
3. `out/dashboard.html` — arquivo único, autocontido, **sem dependência de
   CDN**. Seletor de indicador sobre um mapa esquemático por UF, tabela
   ordenável e scatter Indicador 1 × Indicador 3 (a hipótese a testar é
   que são a mesma coisa vista de dois ângulos).

   **Nota sobre o mapa:** sem acesso à internet nesta sessão não foi
   possível obter um TopoJSON real das fronteiras estaduais, e a regra de
   não depender de CDN afasta bibliotecas de mapa prontas. O mapa é uma
   **grade esquemática (cartograma)** das 27 UFs — topologicamente
   plausível (Norte em cima, Nordeste à direita, Sul embaixo), não
   geografia real. Trocar por um TopoJSON oficial do IBGE é a melhoria
   natural quando houver acesso à internet; a estrutura de dados (um
   valor por sigla de UF) já está pronta para isso — só trocar
   `GRADE_UF` em `05_consolida_e_dashboard.py` pela renderização de
   polígonos reais.

## Fontes

| Indicador | Fonte primária | Complementares |
|---|---|---|
| 1a — IFGF Autonomia | Firjan, `firjan.com.br/ifgf` | — |
| 1b — Dependência de transferências | Siconfi/DCA (Tesouro Nacional) | — |
| 2 — Bolsa Família | VIS DATA / Painel MDS | Censo 2022 (SIDRA/IBGE), RAIS |
| 3 — Adm. pública como maior empregador | RAIS (microdados) | Novo CAGED (fallback), CEMPRE/IBGE (validação cruzada), PNAD Contínua (informalidade, contexto) |
| De/para de município | API de localidades do IBGE | — |

Nenhuma data de acesso é registrada aqui porque nenhuma fonte foi
efetivamente baixada nesta sessão — `data/raw/MANIFEST.md` é gerado
automaticamente por `00_download.py` a cada download real, com URL, data
UTC e SHA-256, e deve ser tratado como a fonte de verdade sobre
proveniência assim que o pipeline rodar contra dados reais.

## Divergências conhecidas entre fontes (a documentar com dados reais)

- IFGF Autonomia (1a) e dependência de transferências via Siconfi (1b)
  medem autossustentação fiscal de formas diferentes e **vão discordar**
  em alguns municípios — isso é esperado e ambas as métricas são mantidas
  lado a lado, sem reconciliação forçada.
- Indicador 3 por setor (a) e por empregador individual (b) podem apontar
  respostas diferentes para o mesmo município (ex.: a prefeitura pode não
  ser o maior CNPJ raiz individual mesmo quando o setor público é o maior
  "setor").
- A informalidade (PNAD Contínua) é uma fonte de natureza amostral
  diferente da RAIS (registro administrativo) — comparar as duas exige
  cautela e por isso a informalidade entra só como coluna de contexto.
- Uma vez rodado com dados reais, preencher aqui: % de municípios onde
  IFGF nota zero e dependência Siconfi ≥90% discordam; correlação
  observada entre Indicador 1 e Indicador 3 (o scatter do dashboard existe
  exatamente para testar essa hipótese).
