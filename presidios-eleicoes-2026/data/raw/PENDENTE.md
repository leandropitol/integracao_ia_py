# Fontes pendentes de download manual

Nada foi baixado ainda (sem acesso à internet nesta sessão). Lista do que
preciso, na ordem em que faz sentido buscar.

## Aviso de volume

Este projeto é bem maior que o anterior (planilha única da Firjan). A
"Votação por seção eleitoral" do TSE é publicada por UF, uma linha por
candidato por seção — para estados grandes isso pode passar de dezenas de
MB por arquivo, e presídios existem em praticamente todas as 27 UFs. Baixar
e anexar isso manualmente, UF por UF, é viável mas trabalhoso. Por isso a
ordem abaixo começa pelos arquivos pequenos (que já permitem adiantar
bastante trabalho) e deixa os grandes por último — ver também a conversa
no chat sobre a opção de liberar a rede desta sessão uma única vez.

## 1. SISDEPEN — perfil penal das unidades (prioridade 1, provavelmente pequeno)

- Página: https://www.gov.br/senappen/pt-br/servicos/sisdepen/bases-de-dados
- Baixar o ciclo mais recente disponível. Precisamos especificamente de:
  - item **5.14** "Quantidade de incidências por tipo penal" (Código Penal
    + legislação específica, masculino e feminino)
  - população prisional total, presos provisórios, regime e gênero da
    unidade (geralmente no mesmo pacote de planilhas do ciclo)
- Salvar em: `data/raw/sisdepen/` (manter o nome original do arquivo)

## 2. TSE — Eleitorado por local de votação 2026 (prioridade 2, pequeno/médio)

- Portal: https://dadosabertos.tse.jus.br/
- Procurar o dataset "Eleitorado por local de votação" — 2026, ou o mais
  recente antes da eleição (geralmente publicado por UF).
- Precisamos de todas as UFs (para achar todas as ~240 seções em
  presídios) — mas o arquivo é um local por linha, não um eleitor por
  linha, então deve ser pequeno mesmo somando as 27 UFs.
- Salvar em: `data/raw/tse_eleitorado/` (um arquivo por UF, nome original)

## 3. TSE — Votação por seção eleitoral, 1º turno 2026 (prioridade 3, pode ser grande)

- Mesmo portal, dataset de resultados (ex.: "Votação por seção eleitoral —
  2026", ou os boletins de urna).
- Precisamos de presidente, governador e senador.
- **Aqui o volume pode pesar.** Se topar com arquivos grandes demais para
  anexar, me avisa antes de tentar — a gente decide UF por UF, ou parte
  para a opção de liberar a rede desta sessão.
- Salvar em: `data/raw/tse_votacao/` (um arquivo por UF, nome original)

## Como me mandar

Só anexar o arquivo aqui na conversa — eu movo para o lugar certo dentro
de `data/raw/` e registro a proveniência. Pode mandar aos poucos, não
precisa juntar tudo de uma vez; eu aviso o que falta a cada etapa.
