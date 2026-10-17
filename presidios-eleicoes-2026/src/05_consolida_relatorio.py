#!/usr/bin/env python3
"""
05_consolida_relatorio.py — junta votação (02), perfil penal (03) e
matching (04) numa base por estabelecimento, confere o total nacional
contra a referência publicada, monta as fichas dos presídios-foco e as
comparações pedidas, e gera o relatório HTML autocontido.

Pré-requisitos: 01, 02, 03, 04 já rodados (mesmo que com cobertura
parcial — este script documenta o que faltar como "sem dados", não trava).

Saídas:
  - output/base_cruzada.csv
  - output/relatorio_presidios_2026.html
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from _common import INTERIM, OUTPUT, log, parar
from config import (
    PRESIDIOS_FOCO,
    N_SECOES_RS_ESPERADO,
    REFERENCIA_TOTAL_VOTOS_VALIDOS,
    REFERENCIA_PCT_LULA,
    REFERENCIA_PCT_FLAVIO,
    TOLERANCIA_REFERENCIA,
    normalizar_nome,
    expandir_abreviacoes,
)

CATEGORIAS_PCT = [
    "pct_drogas", "pct_patrimonio", "pct_contra_pessoa", "pct_dignidade_sexual",
    "pct_armas", "pct_violencia_domestica", "pct_organizacao_criminosa", "pct_outros",
]


def _checar(caminho, script):
    if not caminho.exists():
        parar(f"{caminho} não encontrado. Rode {script} antes deste script.")


def montar_base() -> pd.DataFrame:
    for c, s in [
        (INTERIM / "votacao_estabelecimento.csv", "02_carregar_votacao.py"),
        (INTERIM / "perfil_penal_unidade.csv", "03_carregar_sisdepen.py"),
        (INTERIM / "matching.csv", "04_matching.py"),
    ]:
        _checar(c, s)

    votacao = pd.read_csv(INTERIM / "votacao_estabelecimento.csv")
    perfil = pd.read_csv(INTERIM / "perfil_penal_unidade.csv")
    matching = pd.read_csv(INTERIM / "matching.csv")

    # pivota votação (uma linha por cargo) para uma linha por estabelecimento
    votacao["votos_validos"] = pd.to_numeric(votacao["votos_validos"], errors="coerce")
    wide = votacao.pivot_table(
        index=["uf", "codigo_municipio_tse", "nome_local"],
        columns="cargo",
        values=["votos_validos", "vencedor_nome"],
        aggfunc="first",
    )
    wide.columns = [f"{a}_{b.lower()}" for a, b in wide.columns]
    wide = wide.reset_index()

    # % Lula / % Flávio / % outros para presidente — identificação por
    # substring no nome do vencedor OU, quando houver mais candidatos que
    # só o vencedor nos dados brutos, seria melhor recalcular a partir de
    # votacao_secao_presidio; aqui assume-se que "vencedor_nome_presidente"
    # cobre o caso de interesse central (Lula x Flávio), e os demais ficam
    # em "outros" por diferença.
    secao_presidio = pd.read_csv(INTERIM / "votacao_secao_presidio.csv")
    secao_presidio["votos"] = pd.to_numeric(secao_presidio["votos"], errors="coerce")
    pres = secao_presidio[secao_presidio["cargo_norm"] == "PRESIDENTE"]
    votos_por_cand = pres.groupby(["uf", "codigo_municipio_tse", "nome_local", "nome_candidato"])["votos"].sum().reset_index()
    tot_validos_pres = pres[~pres["eh_branco"] & ~pres["eh_nulo"]].groupby(
        ["uf", "codigo_municipio_tse", "nome_local"]
    )["votos"].sum().rename("votos_validos_pres_check")

    def pct_candidato(padrao_nome: str) -> pd.Series:
        alvo = votos_por_cand[votos_por_cand["nome_candidato"].str.upper().str.contains(padrao_nome, na=False)]
        soma = alvo.groupby(["uf", "codigo_municipio_tse", "nome_local"])["votos"].sum()
        return soma

    votos_lula = pct_candidato("LULA").rename("votos_lula")
    votos_flavio = pct_candidato("FLAVIO|FLÁVIO").rename("votos_flavio")

    base = wide.merge(tot_validos_pres, on=["uf", "codigo_municipio_tse", "nome_local"], how="left")
    base = base.merge(votos_lula, on=["uf", "codigo_municipio_tse", "nome_local"], how="left")
    base = base.merge(votos_flavio, on=["uf", "codigo_municipio_tse", "nome_local"], how="left")
    base["votos_lula"] = base["votos_lula"].fillna(0)
    base["votos_flavio"] = base["votos_flavio"].fillna(0)
    base["pct_lula"] = base["votos_lula"] / base["votos_validos_pres_check"]
    base["pct_flavio"] = base["votos_flavio"] / base["votos_validos_pres_check"]
    base["pct_outros_presidente"] = 1 - base["pct_lula"] - base["pct_flavio"]

    # matching: só pares automáticos entram direto; "revisar"/"nao_casado"
    # ficam sem perfil penal (NA), documentado, nunca forçado.
    matching_auto = matching[matching["status"] == "auto"][["uf", "nome_local_tse", "nome_unidade_sisdepen"]]
    base = base.merge(
        matching_auto, left_on=["uf", "nome_local"], right_on=["uf", "nome_local_tse"], how="left"
    ).drop(columns="nome_local_tse")

    perfil_cols = ["uf", "nome_unidade"] + CATEGORIAS_PCT + [
        "pct_provisorios", "populacao_total", "presos_provisorios", "genero_unidade", "regime", "municipio",
    ]
    perfil_cols = [c for c in perfil_cols if c in perfil.columns]
    base = base.merge(
        perfil[perfil_cols], left_on=["uf", "nome_unidade_sisdepen"], right_on=["uf", "nome_unidade"], how="left"
    )

    # benchmark municipal
    bench_path = INTERIM / "benchmark_municipio.csv"
    if bench_path.exists():
        bench = pd.read_csv(bench_path)
        base = base.merge(bench, on=["uf", "codigo_municipio_tse"], how="left")
        base["descolamento_pct_vencedor"] = np.where(
            base["vencedor_nome_presidente"] == base["vencedor_municipio"],
            base["pct_lula"].where(base["vencedor_nome_presidente"].str.upper().str.contains("LULA", na=False), base["pct_flavio"])
            - base["pct_vencedor_municipio"],
            pd.NA,
        )
    else:
        log("AVISO: benchmark_municipio.csv ausente — coluna de descolamento vs. município ficará vazia.")

    base["sem_dados_perfil_penal"] = base.get("nome_unidade_sisdepen").isna() if "nome_unidade_sisdepen" in base.columns else True

    return base


def checar_universo_nacional(base: pd.DataFrame) -> None:
    total = base["votos_validos_presidente"].sum()
    pct_lula = (base["votos_lula"].sum() / total) if total else np.nan
    pct_flavio = (base["votos_flavio"].sum() / total) if total else np.nan

    log(f"Total nacional (seções de presídio, presidente): {total:.0f} votos válidos")
    log(f"  % Lula: {pct_lula:.1%} (referência: {REFERENCIA_PCT_LULA:.1%})")
    log(f"  % Flávio: {pct_flavio:.1%} (referência: {REFERENCIA_PCT_FLAVIO:.1%})")

    desvio_total = abs(total - REFERENCIA_TOTAL_VOTOS_VALIDOS) / REFERENCIA_TOTAL_VOTOS_VALIDOS if REFERENCIA_TOTAL_VOTOS_VALIDOS else 1
    if desvio_total > TOLERANCIA_REFERENCIA:
        log(
            f"ALERTA: total nacional difere da referência em {desvio_total:.0%} "
            f"(> {TOLERANCIA_REFERENCIA:.0%} de tolerância). Isso é esperado "
            f"se a base ainda estiver com cobertura parcial de UFs — mas se "
            f"todas as UFs já estiverem carregadas, INVESTIGAR O FILTRO DE "
            f"SEÇÕES antes de considerar o relatório confiável."
        )


def montar_fichas(base: pd.DataFrame) -> list[dict]:
    """Busca cada presídio-foco por fuzzy match (não substring ingênua —
    um termo genérico como 'Penitenciária' bateria com qualquer unidade da
    UF e sempre devolveria a primeira linha, errado). Exige um score
    mínimo; abaixo disso, fica como não encontrado em vez de chutar a
    unidade errada."""
    LIMIAR_FICHA = 60
    fichas = []
    for alvo in PRESIDIOS_FOCO:
        termo = expandir_abreviacoes(normalizar_nome(alvo["nome_busca"]))
        candidatos = base[base["uf"] == alvo["uf"]].copy()
        if candidatos.empty:
            fichas.append({"busca": alvo["nome_busca"], "uf": alvo["uf"], "encontrado": False})
            continue
        candidatos["_score"] = candidatos["nome_local"].map(
            lambda n: fuzz.token_sort_ratio(termo, expandir_abreviacoes(normalizar_nome(n)))
        )
        melhor = candidatos.sort_values("_score", ascending=False).iloc[0]
        if melhor["_score"] < LIMIAR_FICHA:
            fichas.append({"busca": alvo["nome_busca"], "uf": alvo["uf"], "encontrado": False})
        else:
            linha = melhor.drop("_score").to_dict()
            linha["busca"] = alvo["nome_busca"]
            linha["encontrado"] = True
            fichas.append(linha)
    return fichas


def main() -> None:
    log("=== 05_consolida_relatorio.py: início ===")
    base = montar_base()
    checar_universo_nacional(base)

    base.to_csv(OUTPUT / "base_cruzada.csv", index=False, encoding="utf-8")
    log(f"OK: output/base_cruzada.csv ({len(base)} estabelecimentos)")

    fichas = montar_fichas(base)
    rs = base[base["uf"] == "RS"]
    if len(rs) != N_SECOES_RS_ESPERADO:
        log(f"AVISO: {len(rs)} unidades no RS, esperado {N_SECOES_RS_ESPERADO} — conferir cobertura/matching no RS.")
    top10 = base.nlargest(10, "votos_validos_presidente")
    flavio_venceu = base[base["vencedor_nome_presidente"].str.upper().str.contains("FLAVIO|FLÁVIO", na=False)]
    log(f"Unidades onde Flávio venceu (presidente): {len(flavio_venceu)} (referência citada: 24)")

    comparacao = base.groupby(
        np.where(base["vencedor_nome_presidente"].str.upper().str.contains("LULA", na=False), "Lula venceu",
                 np.where(base["vencedor_nome_presidente"].str.upper().str.contains("FLAVIO|FLÁVIO", na=False), "Flávio venceu", "Outro"))
    )[CATEGORIAS_PCT + ["pct_provisorios"]].mean(numeric_only=True)

    payload = {
        "base": json.loads(base.to_json(orient="records")),
        "fichas": fichas,
        "top10": json.loads(top10[["uf", "nome_local", "votos_validos_presidente", "vencedor_nome_presidente"]].to_json(orient="records")),
        "flavio_venceu": json.loads(flavio_venceu[["uf", "nome_local", "pct_flavio"]].to_json(orient="records")),
        "comparacao_lula_flavio": json.loads(comparacao.reset_index().rename(columns={"index": "grupo"}).to_json(orient="records")),
        "categorias_pct": CATEGORIAS_PCT,
    }
    (OUTPUT / "relatorio_payload.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    html = montar_html(payload, base)
    (OUTPUT / "relatorio_presidios_2026.html").write_text(html, encoding="utf-8")
    log("OK: output/relatorio_presidios_2026.html")
    log("=== 05_consolida_relatorio.py: fim ===")


def montar_html(payload: dict, base: pd.DataFrame) -> str:
    n_sem_dados = int(base["sem_dados_perfil_penal"].sum()) if "sem_dados_perfil_penal" in base.columns else len(base)
    sumario = (
        f"{len(base)} estabelecimentos com dado de votação carregado. "
        f"{n_sem_dados} sem perfil penal casado (SISDEPEN) — marcados como "
        f"'sem dados', não estimados."
    )
    return TEMPLATE.replace("__PAYLOAD_JSON__", json.dumps(payload, ensure_ascii=False)).replace(
        "__SUMARIO__", sumario
    )


TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Votação em presídios — 1º turno 2026</title>
<style>
  :root { --bg:#f7f5f2; --fg:#1f2933; --muted:#6b7280; --card:#fff; --border:#e2e0db; --accent:#7a2e2e; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) { --bg:#16181b; --fg:#eceef0; --muted:#9aa2ab; --card:#202327; --border:#33373d; --accent:#d98080; }
  }
  :root[data-theme="dark"] { --bg:#16181b; --fg:#eceef0; --muted:#9aa2ab; --card:#202327; --border:#33373d; --accent:#d98080; }
  * { box-sizing: border-box; }
  body { background:var(--bg); color:var(--fg); font-family:-apple-system,"Segoe UI",Roboto,sans-serif; margin:0; padding:24px; }
  h1 { font-size:1.4rem; margin:0 0 4px; }
  h2 { font-size:1.05rem; margin:28px 0 10px; border-bottom:1px solid var(--border); padding-bottom:6px; }
  .sub { color:var(--muted); font-size:.85rem; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; margin-bottom:16px; }
  table { width:100%; border-collapse:collapse; font-size:.8rem; }
  th, td { padding:5px 8px; text-align:right; border-bottom:1px solid var(--border); }
  th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align:left; }
  th { cursor:pointer; color:var(--muted); white-space:nowrap; }
  .ficha-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px,1fr)); gap:12px; }
  .ficha { border:1px solid var(--border); border-radius:8px; padding:12px; font-size:.8rem; }
  .ficha b { display:block; margin-bottom:4px; }
  .nao-encontrado { opacity:.5; }
  input[type=text] { background:var(--card); color:var(--fg); border:1px solid var(--border); border-radius:6px; padding:6px 8px; font-size:.8rem; width:260px; }
  svg text { fill: var(--fg); font-size:10px; }
  .axis-label { fill: var(--muted); font-size:11px; }
</style>
</head>
<body>
  <h1>Votação no 1º turno 2026 em presídios × perfil penal</h1>
  <div class="sub">__SUMARIO__</div>

  <div class="card">
    <h2 style="margin-top:0;border:none;">Sumário executivo</h2>
    <div id="sumarioExecutivo"></div>
  </div>

  <h2>Fichas dos presídios-foco</h2>
  <div class="card"><div class="ficha-grid" id="fichas"></div></div>

  <h2>Comparação: unidades onde Lula venceu × unidades onde Flávio venceu</h2>
  <div class="card"><table id="tabelaComparacao"></table></div>

  <h2>Dispersão: % incidências (drogas / patrimônio / contra a pessoa) × % Lula</h2>
  <div class="card">
    <label>Categoria: <select id="seletorScatter"></select></label>
    <svg id="scatter" width="100%" height="360" viewBox="0 0 560 360"></svg>
    <div class="sub" id="correlacaoTexto"></div>
  </div>

  <h2>Tabela nacional (filtrável)</h2>
  <div class="card">
    <input type="text" id="filtroTabela" placeholder="Filtrar por UF ou nome...">
    <div style="max-height:480px; overflow:auto; margin-top:10px;">
      <table id="tabelaNacional"></table>
    </div>
  </div>

  <h2>Nota metodológica</h2>
  <div class="card sub">
    Análise ecológica no nível da unidade prisional: o resultado eleitoral
    de uma seção não permite inferir o voto individual de nenhum preso
    específico. Casamento TSE↔SISDEPEN por nome normalizado (fuzzy match,
    rapidfuzz) — pares de confiança média foram para revisão manual
    (<code>matching_revisar.csv</code>) e não entram nesta base até
    confirmados; pares sem casamento aparecem como "sem dados", nunca
    estimados. Cobertura pode ser parcial se nem todas as UFs/arquivos
    tiverem sido carregados — ver contagem de UFs no payload bruto
    (<code>relatorio_payload.json</code>) para auditoria.
  </div>

<script>
const PAYLOAD = __PAYLOAD_JSON__;
const base = PAYLOAD.base;

function fmtPct(v) { return (v===null||v===undefined||Number.isNaN(v)) ? '—' : (v*100).toFixed(1)+'%'; }
function fmtInt(v) { return (v===null||v===undefined||Number.isNaN(v)) ? '—' : Math.round(v).toLocaleString('pt-BR'); }

// Sumário executivo
document.getElementById('sumarioExecutivo').innerHTML = `
  <p>Top 10 estabelecimentos por votos válidos (presidente): ${PAYLOAD.top10.map(d=>`${d.nome_local} (${d.uf})`).join(', ') || '—'}</p>
  <p>Unidades onde Flávio Bolsonaro venceu: ${PAYLOAD.flavio_venceu.length}</p>
`;

// Fichas
const fichasDiv = document.getElementById('fichas');
PAYLOAD.fichas.forEach(f => {
  const div = document.createElement('div');
  div.className = 'ficha' + (f.encontrado ? '' : ' nao-encontrado');
  if (!f.encontrado) {
    div.innerHTML = `<b>${f.busca} (${f.uf})</b>Não encontrado na base carregada até agora — sem dados.`;
  } else {
    div.innerHTML = `
      <b>${f.nome_local} (${f.uf})</b>
      Votos válidos (presidente): ${fmtInt(f.votos_validos_presidente)}<br>
      % Lula: ${fmtPct(f.pct_lula)} · % Flávio: ${fmtPct(f.pct_flavio)}<br>
      Vencedor: ${f.vencedor_nome_presidente || '—'}<br>
      % provisórios: ${fmtPct(f.pct_provisorios)}<br>
      ${f.sem_dados_perfil_penal ? '<i>perfil penal: sem dados (não casado no SISDEPEN)</i>' : ''}
    `;
  }
  fichasDiv.appendChild(div);
});

// Comparação Lula x Flávio
(function() {
  const tabela = document.getElementById('tabelaComparacao');
  const dados = PAYLOAD.comparacao_lula_flavio;
  if (!dados.length) { tabela.innerHTML = '<tr><td>Sem dados suficientes ainda.</td></tr>'; return; }
  const cols = PAYLOAD.categorias_pct.concat(['pct_provisorios']);
  tabela.innerHTML = '<thead><tr><th>Grupo</th>' + cols.map(c=>`<th>${c}</th>`).join('') + '</tr></thead>' +
    '<tbody>' + dados.map(row => '<tr><td>'+row.grupo+'</td>' + cols.map(c=>`<td>${fmtPct(row[c])}</td>`).join('') + '</tr>').join('') + '</tbody>';
})();

// Scatter
const seletorScatter = document.getElementById('seletorScatter');
['pct_drogas','pct_patrimonio','pct_contra_pessoa'].forEach(c => {
  const opt = document.createElement('option'); opt.value = c; opt.textContent = c; seletorScatter.appendChild(opt);
});
function correlacaoPonderada(pontos, xKey, yKey, wKey) {
  const n = pontos.length;
  if (n < 2) return null;
  const somaW = pontos.reduce((s,p)=>s+p[wKey], 0);
  const mx = pontos.reduce((s,p)=>s+p[xKey]*p[wKey],0)/somaW;
  const my = pontos.reduce((s,p)=>s+p[yKey]*p[wKey],0)/somaW;
  let cov=0, vx=0, vy=0;
  pontos.forEach(p => { const dx=p[xKey]-mx, dy=p[yKey]-my; cov+=p[wKey]*dx*dy; vx+=p[wKey]*dx*dx; vy+=p[wKey]*dy*dy; });
  if (vx===0||vy===0) return null;
  return cov/Math.sqrt(vx*vy);
}
function desenharScatter(catKey) {
  const svg = document.getElementById('scatter');
  const W=560,H=360,M=44;
  const pontos = base.filter(d => d[catKey]!=null && d.pct_lula!=null && d.votos_validos_presidente>0 && !Number.isNaN(d[catKey]));
  document.getElementById('correlacaoTexto').textContent = pontos.length
    ? `n = ${pontos.length} unidades · correlação ponderada por votos válidos: ${(correlacaoPonderada(pontos, catKey, 'pct_lula', 'votos_validos_presidente')||0).toFixed(2)}`
    : 'Sem dados suficientes ainda.';
  if (!pontos.length) { svg.innerHTML = `<text x="20" y="40" class="axis-label">Sem dados suficientes (rode o pipeline com mais UFs carregadas).</text>`; return; }
  const xmax = Math.max(.01, ...pontos.map(p=>p[catKey]));
  const wmax = Math.max(1, ...pontos.map(p=>p.votos_validos_presidente));
  const sx = v => M + v/xmax*(W-2*M);
  const sy = v => H-M - v*(H-2*M);
  let s = `<line x1="${M}" y1="${H-M}" x2="${W-M}" y2="${H-M}" stroke="var(--border)"/>`;
  s += `<line x1="${M}" y1="${M}" x2="${M}" y2="${H-M}" stroke="var(--border)"/>`;
  s += `<text x="${W/2}" y="${H-8}" text-anchor="middle" class="axis-label">${catKey}</text>`;
  s += `<text x="12" y="${H/2}" text-anchor="middle" class="axis-label" transform="rotate(-90 12 ${H/2})">% Lula</text>`;
  pontos.forEach(p => {
    const r = 3 + 7*Math.sqrt(p.votos_validos_presidente/wmax);
    s += `<circle cx="${sx(p[catKey])}" cy="${sy(p.pct_lula)}" r="${r}" fill="var(--accent)" fill-opacity="0.55"><title>${p.nome_local} (${p.uf})</title></circle>`;
  });
  svg.innerHTML = s;
}
seletorScatter.addEventListener('change', () => desenharScatter(seletorScatter.value));
desenharScatter('pct_drogas');

// Tabela nacional
(function() {
  const tabela = document.getElementById('tabelaNacional');
  const filtro = document.getElementById('filtroTabela');
  const cols = ['uf','nome_local','votos_validos_presidente','pct_lula','pct_flavio','vencedor_nome_presidente','pct_provisorios','pct_drogas','pct_patrimonio'];
  function render(termo) {
    const t = (termo||'').toUpperCase();
    const linhas = base.filter(d => !t || (d.uf+' '+d.nome_local).toUpperCase().includes(t));
    tabela.innerHTML = '<thead><tr>' + cols.map(c=>`<th>${c}</th>`).join('') + '</tr></thead>' +
      '<tbody>' + linhas.map(row => '<tr>' + cols.map(c => {
        const v = row[c];
        if (c==='uf'||c==='nome_local'||c==='vencedor_nome_presidente') return `<td>${v??'—'}</td>`;
        if (typeof v === 'number' && c.startsWith('pct_')) return `<td>${fmtPct(v)}</td>`;
        return `<td>${fmtInt(v)}</td>`;
      }).join('') + '</tr>').join('') + '</tbody>';
  }
  filtro.addEventListener('input', () => render(filtro.value));
  render('');
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
