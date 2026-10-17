# Relatório: votação no 1º turno 2026 em presídios × perfil penal

## Objetivo

Cruzar, por estabelecimento prisional, o resultado do 1º turno das Eleições
2026 (4/10/2026) nas seções eleitorais instaladas em presídios com o perfil
da população presa (tipos penais e % de provisórios). Análise ecológica, no
nível da unidade.

## ⚠️ Status: pipeline pronto, aguardando dados reais

Esta sessão não tem acesso à internet (mesmo bloqueio de rede do outro
projeto no repositório — `dadosabertos.tse.jus.br` e `gov.br` testados e
rejeitados pelo proxy de egress). Nada foi baixado ainda. Ver
`data/raw/PENDENTE.md` para a lista exata do que falta buscar e onde.

Decisão combinada: processar com cobertura parcial em vez de esperar tudo
— cada script documenta explicitamente o que falta (UF sem arquivo,
estabelecimento sem match no SISDEPEN) como "sem dados", nunca estima.
Pode mandar os arquivos aos poucos; o pipeline é idempotente, rode de novo
a cada arquivo novo.

Os scripts foram testados de ponta a ponta com dados **fictícios** (nunca
commitados), então a mecânica — join, agregação, matching fuzzy,
categorização, checagem do total nacional, fichas, scatter — está
validada. **O que não está verificado** são os nomes de coluna reais do
TSE e do SISDEPEN (ver `src/config.py`, dicionários `COLUNAS_TSE_*` e
`COLUNAS_SISDEPEN_*`) — cada script para com mensagem clara
(`PipelineParadoError`) se a coluna esperada não existir no arquivo real,
em vez de seguir com um mapeamento errado.

## Plano de processamento (`src/`, já escrito; testado de ponta a ponta com dados fictícios)

```
pip install -r requirements.txt
python src/01_carregar_eleitorado.py   # identifica seções em presídio
python src/02_carregar_votacao.py      # agrega votação por estabelecimento + benchmark municipal
python src/03_carregar_sisdepen.py     # perfil penal por unidade
python src/04_matching.py              # casa TSE <-> SISDEPEN (fuzzy, nunca forçado)
python src/05_consolida_relatorio.py   # base_cruzada.csv + relatorio_presidios_2026.html
```

Cada script roda com o que encontrar em `data/raw/` e documenta cobertura
parcial com avisos — não trava esperando todos os arquivos. Pode rodar de
novo a qualquer momento conforme mais arquivos forem chegando; é
idempotente.

1. **Identificar seções em presídios** — cruza "Eleitorado por local de
   votação 2026" do TSE com padrões de nome (PENITENCIÁRIA, PRESÍDIO, CDP,
   CADEIA, COMPLEXO PENITENCIÁRIO, CENTRO DE DETENÇÃO, FUNDAÇÃO CASA, CASE,
   PRESIDIO). Esperado: ~240 seções.
2. **Agregar votação por estabelecimento** — pode haver mais de uma seção
   por unidade; soma votos por candidato, brancos, nulos, para presidente,
   governador e senador. Também calcula o benchmark do município inteiro
   (todas as seções, não só a do presídio) para medir descolamento.
3. **Casar TSE ↔ SISDEPEN** por UF + nome normalizado (sem acento,
   abreviações expandidas: PEN→PENITENCIÁRIA, CDP→CENTRO DE DETENÇÃO
   PROVISÓRIA etc.) com `rapidfuzz`. Pares de score médio vão para
   `output/matching_revisar.csv` — nunca forço um match duvidoso.
4. **Categorizar tipos penais** (item 5.14 SISDEPEN) nas 7 categorias +
   "outros". % de cada grupo + % de provisórios, por unidade.
5. **Consolidar** — junta tudo, confere o total nacional contra a
   referência publicada, monta as fichas dos presídios-foco (por fuzzy
   match, não substring — evita confundir unidades de nome parecido como
   Tremembé I/II), a comparação Lula×Flávio, o scatter com correlação
   ponderada, e gera o HTML.


## Verificação obrigatória antes de qualquer análise

Conferir o total nacional das seções de presídio contra a referência
publicada (~11,2 mil votos válidos, Lula ~72,6%, Flávio ~23,3%). Se o total
sair muito diferente, investigar o filtro de seções antes de seguir — não
publicar nada em cima de um universo errado.

## Regras

- Nunca inventar número. Presídio sem match ou sem item 5.14: "sem dados"
  no relatório, não estimativa.
- Nota metodológica curta no final do relatório (o usuário já conhece as
  limitações da análise ecológica, não precisa de aviso extenso).

## Entregáveis (em `output/`)

- `relatorio_presidios_2026.html` — autocontido, gráficos embutidos,
  sumário executivo, fichas dos presídios-foco, tabelas filtráveis, nota
  metodológica curta.
- `base_cruzada.csv` — uma linha por estabelecimento, todos os indicadores.
- `matching_revisar.csv`.
- Scripts Python/pandas reproduzíveis em `src/`, numerados, com este README
  explicando como rodar.
