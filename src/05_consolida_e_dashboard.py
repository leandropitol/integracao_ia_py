#!/usr/bin/env python3
"""
05_consolida_e_dashboard.py — junta os três indicadores em
out/consolidado_uf.csv (27 linhas) e out/consolidado_municipio.csv, e gera
out/dashboard.html (arquivo único, autocontido, sem dependência de CDN).

Pré-requisito: rodar 02, 03 e 04 antes (o script para com mensagem clara
se algum dos três CSVs de indicador estiver ausente).

O dashboard tem:
  - um mapa por UF (grade esquemática de 27 unidades — ver nota abaixo)
    com seletor de indicador;
  - uma tabela ordenável por UF;
  - um scatter Indicador 1 (dependência fiscal) x Indicador 3 (estado como
    maior empregador) — a hipótese a testar é que são a mesma coisa vista
    de dois ângulos.

*** NOTA SOBRE O MAPA ***
Sem acesso à internet nesta sessão não foi possível buscar um TopoJSON real
das fronteiras dos estados, e a regra de não depender de CDN afasta
bibliotecas de mapa prontas. O "mapa" abaixo é uma GRADE ESQUEMÁTICA das 27
UFs (cartograma, não geografia real), só para dar uma leitura espacial
aproximada (Norte em cima, Nordeste à direita, Sul embaixo). Se depois
houver acesso à internet, trocar por um TopoJSON real do IBGE é a melhoria
natural — deixei a estrutura de dados (um valor por sigla de UF) pronta
para isso.
"""
from __future__ import annotations

import json

import pandas as pd

from _common import OUT, log, parar

IND1_UF = OUT / "indicador1_fiscal_uf.csv"
IND2_UF = OUT / "indicador2_bolsafamilia_uf.csv"
IND3_UF = OUT / "indicador3_empregador_uf.csv"
IND1_MUN = OUT / "indicador1_fiscal_municipio.csv"
IND2_MUN = OUT / "indicador2_bolsafamilia_municipio.csv"
IND3_MUN = OUT / "indicador3_empregador_municipio.csv"

# Posição (linha, coluna) de cada UF na grade esquemática — layout
# topologicamente plausível (Norte acima, Nordeste à direita, Centro-Oeste
# no meio, Sudeste/Sul embaixo), não uma projeção geográfica real.
GRADE_UF = {
    "RR": (0, 3), "AP": (0, 6),
    "AM": (1, 2), "PA": (1, 5), "MA": (1, 7), "CE": (1, 9),
    "AC": (2, 1), "RO": (2, 3), "TO": (2, 6), "PI": (2, 8), "RN": (2, 10),
    "PB": (3, 10), "PE": (3, 9),
    "MT": (3, 4), "AL": (4, 9), "SE": (4, 8),
    "GO": (4, 5), "DF": (4, 6), "BA": (4, 7),
    "MS": (5, 4), "MG": (5, 6), "ES": (5, 7),
    "SP": (6, 5), "RJ": (6, 7),
    "PR": (7, 4),
    "SC": (8, 4),
    "RS": (9, 3),
}


def _checar_existe(caminho, etapa_anterior: str) -> None:
    if not caminho.exists():
        parar(f"{caminho} não encontrado. Rode {etapa_anterior} antes deste script.")


def consolidar_uf() -> pd.DataFrame:
    for c, script in [(IND1_UF, "02_indicador1_fiscal.py"), (IND2_UF, "03_indicador2_bolsafamilia.py"), (IND3_UF, "04_indicador3_empregador.py")]:
        _checar_existe(c, script)

    i1 = pd.read_csv(IND1_UF)
    i2 = pd.read_csv(IND2_UF)
    i3 = pd.read_csv(IND3_UF)

    df = i1.merge(i2, on="uf_sigla", how="outer", suffixes=("_ind1", "_ind2"))
    df = df.merge(i3, on="uf_sigla", how="outer")
    if len(df) != 27:
        log(f"AVISO: consolidado_uf tem {len(df)} linhas, esperado 27 (uma por UF). Confira UFs ausentes/duplicadas em algum dos três indicadores.")
    return df.sort_values("uf_sigla").reset_index(drop=True)


def consolidar_municipio() -> pd.DataFrame:
    for c, script in [(IND1_MUN, "02_indicador1_fiscal.py"), (IND2_MUN, "03_indicador2_bolsafamilia.py"), (IND3_MUN, "04_indicador3_empregador.py")]:
        _checar_existe(c, script)

    i1 = pd.read_csv(IND1_MUN)
    i2 = pd.read_csv(IND2_MUN)
    i3 = pd.read_csv(IND3_MUN)

    df = i1.merge(i2, on="codigo_ibge_7", how="outer", suffixes=("", "_ind2"))
    df = df.merge(i3, on="codigo_ibge_7", how="outer", suffixes=("", "_ind3"))
    return df


def montar_dashboard(uf_df: pd.DataFrame) -> str:
    indicadores_disponiveis = {
        "pct_nota_zero_sobre_total_uf": "Ind.1a — nota zero IFGF (Autonomia) / total UF",
        "pct_dependencia_alta_sobre_total_uf": "Ind.1b — dependência de transferências ≥90% / total UF",
        "pct_acima_50pct_domicilios_sobre_total_uf": "Ind.2 — Bolsa Família >50% domicílios / total UF",
        "pct_adm_maior_empregador_por_setor_sobre_total_uf": "Ind.3a — adm. municipal maior setor / total UF",
        "pct_adm_maior_empregador_individual_sobre_total_uf": "Ind.3b — adm. municipal maior empregador individual / total UF",
    }
    disponiveis = {k: v for k, v in indicadores_disponiveis.items() if k in uf_df.columns}
    if not disponiveis:
        parar("Nenhuma das colunas de indicador esperadas está em consolidado_uf — confira se 02/03/04 rodaram até o fim sem erro.")

    dados_uf = json.loads(uf_df.to_json(orient="records"))
    scatter_x = "pct_nota_zero_sobre_total_uf"
    scatter_y = "pct_adm_maior_empregador_por_setor_sobre_total_uf"

    payload = {
        "dados_uf": dados_uf,
        "grade_uf": GRADE_UF,
        "indicadores": disponiveis,
        "scatter_x": scatter_x,
        "scatter_y": scatter_y,
    }

    return TEMPLATE.replace("__PAYLOAD_JSON__", json.dumps(payload, ensure_ascii=False))


TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Dependência estrutural dos municípios — painel por UF</title>
<style>
  :root {
    --bg: #f7f5f2; --fg: #1f2933; --muted: #6b7280; --card: #ffffff;
    --border: #e2e0db; --accent: #7a2e2e; --accent-soft: #f1e3e3;
    --scale-0: #f4ede9; --scale-4: #7a2e2e;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #16181b; --fg: #eceef0; --muted: #9aa2ab; --card: #202327;
      --border: #33373d; --accent: #d98080; --accent-soft: #3a2426;
      --scale-0: #2a2320; --scale-4: #d98080;
    }
  }
  :root[data-theme="dark"] {
    --bg: #16181b; --fg: #eceef0; --muted: #9aa2ab; --card: #202327;
    --border: #33373d; --accent: #d98080; --accent-soft: #3a2426;
    --scale-0: #2a2320; --scale-4: #d98080;
  }
  * { box-sizing: border-box; }
  body { background: var(--bg); color: var(--fg); font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 24px; }
  h1 { font-size: 1.3rem; margin: 0 0 4px; }
  .sub { color: var(--muted); font-size: .85rem; margin-bottom: 20px; }
  .grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 20px; align-items: start; }
  @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
  select, input { background: var(--card); color: var(--fg); border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; font-size: .85rem; }
  table { width: 100%; border-collapse: collapse; font-size: .8rem; }
  th, td { padding: 5px 8px; text-align: right; border-bottom: 1px solid var(--border); }
  th:first-child, td:first-child { text-align: left; }
  th { cursor: pointer; color: var(--muted); user-select: none; white-space: nowrap; }
  th.sorted { color: var(--accent); }
  .table-wrap { max-height: 480px; overflow: auto; }
  .cell-uf { display: inline-block; width: 40px; height: 40px; border-radius: 6px; font-size: .68rem; display: flex; align-items: center; justify-content: center; border: 1px solid var(--border); cursor: default; }
  .grid-map { position: relative; width: 100%; }
  .legend { display: flex; gap: 8px; align-items: center; font-size: .72rem; color: var(--muted); margin-top: 10px; }
  .legend-swatch { width: 14px; height: 14px; border-radius: 3px; display: inline-block; }
  .na { opacity: .35; }
  svg text { fill: var(--fg); font-size: 10px; }
  .axis-label { fill: var(--muted); font-size: 11px; }
  .tooltip { position: fixed; pointer-events: none; background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 6px 9px; font-size: .75rem; display: none; z-index: 10; box-shadow: 0 4px 14px rgba(0,0,0,.15); }
</style>
</head>
<body>
  <h1>Dependência estrutural dos municípios brasileiros</h1>
  <div class="sub">Painel por UF — três dimensões: autossustentação fiscal, dependência de transferência de renda, estado como maior empregador. Grade esquemática (cartograma), não geografia real — ver README.</div>

  <div class="grid">
    <div class="card">
      <label>Indicador no mapa: <select id="seletorIndicador"></select></label>
      <div class="grid-map" id="mapaContainer" style="margin-top:14px;"></div>
      <div class="legend" id="legenda"></div>
    </div>

    <div class="card">
      <div style="margin-bottom:8px; color:var(--muted); font-size:.8rem;">
        Indicador 1 (dependência fiscal) × Indicador 3 (adm. municipal maior empregador) — hipótese: mesma coisa, dois ângulos.
      </div>
      <svg id="scatter" width="100%" height="320" viewBox="0 0 480 320"></svg>
    </div>
  </div>

  <div class="card" style="margin-top:20px;">
    <div class="table-wrap">
      <table id="tabelaUf"></table>
    </div>
  </div>

  <div class="tooltip" id="tooltip"></div>

<script>
const PAYLOAD = __PAYLOAD_JSON__;
const dadosUf = PAYLOAD.dados_uf;
const gradeUf = PAYLOAD.grade_uf;
const indicadores = PAYLOAD.indicadores;
const tooltip = document.getElementById('tooltip');

function fmtPct(v) {
  if (v === null || v === undefined || v === '' || Number.isNaN(v)) return '—';
  return (v * 100).toFixed(1) + '%';
}

function corEscala(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return null;
  const t = Math.max(0, Math.min(1, v));
  // interpola entre --scale-0 e --scale-4 (tons de vinho, sem dependência de libs de cor)
  const c0 = [244, 237, 233], c1 = [122, 46, 46];
  const rgb = c0.map((c, i) => Math.round(c + (c1[i] - c) * t));
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
}

function montarSeletor() {
  const sel = document.getElementById('seletorIndicador');
  Object.entries(indicadores).forEach(([chave, label]) => {
    const opt = document.createElement('option');
    opt.value = chave; opt.textContent = label;
    sel.appendChild(opt);
  });
  sel.addEventListener('change', () => desenharMapa(sel.value));
}

function desenharMapa(chave) {
  const container = document.getElementById('mapaContainer');
  container.innerHTML = '';
  const cellSize = 46;
  const maxRow = Math.max(...Object.values(gradeUf).map(p => p[0]));
  const maxCol = Math.max(...Object.values(gradeUf).map(p => p[1]));
  container.style.height = (maxRow + 1) * cellSize + 'px';
  container.style.position = 'relative';

  const valores = dadosUf.map(d => d[chave]).filter(v => v !== null && v !== undefined && !Number.isNaN(v));
  const vmax = valores.length ? Math.max(...valores) : 1;

  dadosUf.forEach(row => {
    const uf = row.uf_sigla;
    const pos = gradeUf[uf];
    if (!pos) return;
    const [r, c] = pos;
    const v = row[chave];
    const vNorm = (v !== null && v !== undefined && !Number.isNaN(v) && vmax > 0) ? v / vmax : null;
    const cor = corEscala(vNorm);
    const div = document.createElement('div');
    div.className = 'cell-uf' + (cor === null ? ' na' : '');
    div.style.position = 'absolute';
    div.style.left = (c * cellSize) + 'px';
    div.style.top = (r * cellSize) + 'px';
    div.style.background = cor || 'transparent';
    div.style.color = cor ? '#fff' : 'var(--muted)';
    div.textContent = uf;
    div.addEventListener('mousemove', (e) => {
      tooltip.style.display = 'block';
      tooltip.style.left = (e.clientX + 12) + 'px';
      tooltip.style.top = (e.clientY + 12) + 'px';
      tooltip.innerHTML = `<b>${uf}</b><br>${indicadores[chave]}: ${fmtPct(v)}`;
    });
    div.addEventListener('mouseleave', () => tooltip.style.display = 'none');
    container.appendChild(div);
  });

  const legenda = document.getElementById('legenda');
  legenda.innerHTML = '<span>0%</span>' +
    [0, .25, .5, .75, 1].map(t => `<span class="legend-swatch" style="background:${corEscala(t)}"></span>`).join('') +
    `<span>${fmtPct(vmax)}</span> <span style="margin-left:8px;">(escala relativa ao máximo observado)</span>`;
}

function montarTabela() {
  const tabela = document.getElementById('tabelaUf');
  const colunas = ['uf_sigla', ...Object.keys(indicadores)];
  let sortCol = 'uf_sigla', sortAsc = true;

  function render() {
    const linhas = [...dadosUf].sort((a, b) => {
      const va = a[sortCol], vb = b[sortCol];
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
    const thead = '<thead><tr>' + colunas.map(c =>
      `<th data-col="${c}" class="${c === sortCol ? 'sorted' : ''}">${c === 'uf_sigla' ? 'UF' : indicadores[c]}</th>`
    ).join('') + '</tr></thead>';
    const tbody = '<tbody>' + linhas.map(row =>
      '<tr>' + colunas.map(c => `<td>${c === 'uf_sigla' ? row[c] : fmtPct(row[c])}</td>`).join('') + '</tr>'
    ).join('') + '</tbody>';
    tabela.innerHTML = thead + tbody;
    tabela.querySelectorAll('th').forEach(th => th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (sortCol === col) sortAsc = !sortAsc; else { sortCol = col; sortAsc = true; }
      render();
    }));
  }
  render();
}

function desenharScatter() {
  const svg = document.getElementById('scatter');
  const W = 480, H = 320, M = 40;
  const xKey = PAYLOAD.scatter_x, yKey = PAYLOAD.scatter_y;
  const pontos = dadosUf.filter(d => d[xKey] != null && d[yKey] != null && !Number.isNaN(d[xKey]) && !Number.isNaN(d[yKey]));

  if (!pontos.length) {
    svg.innerHTML = `<text x="20" y="40" class="axis-label">Sem dados suficientes para o scatter (${xKey} × ${yKey}). Rode o pipeline com dados reais.</text>`;
    return;
  }

  const xs = pontos.map(p => p[xKey]), ys = pontos.map(p => p[yKey]);
  const xmax = Math.max(.01, ...xs), ymax = Math.max(.01, ...ys);
  const sx = v => M + (v / xmax) * (W - 2 * M);
  const sy = v => H - M - (v / ymax) * (H - 2 * M);

  let svgContent = `<line x1="${M}" y1="${H-M}" x2="${W-M}" y2="${H-M}" stroke="var(--border)"/>`;
  svgContent += `<line x1="${M}" y1="${M}" x2="${M}" y2="${H-M}" stroke="var(--border)"/>`;
  svgContent += `<text x="${W/2}" y="${H-8}" text-anchor="middle" class="axis-label">${indicadores[xKey] || xKey}</text>`;
  svgContent += `<text x="12" y="${H/2}" text-anchor="middle" class="axis-label" transform="rotate(-90 12 ${H/2})">${indicadores[yKey] || yKey}</text>`;

  pontos.forEach(p => {
    const cx = sx(p[xKey]), cy = sy(p[yKey]);
    svgContent += `<circle cx="${cx}" cy="${cy}" r="5" fill="var(--accent)" fill-opacity="0.75" data-uf="${p.uf_sigla}" data-x="${p[xKey]}" data-y="${p[yKey]}"></circle>`;
    svgContent += `<text x="${cx+7}" y="${cy+3}" font-size="9">${p.uf_sigla}</text>`;
  });
  svg.innerHTML = svgContent;

  svg.querySelectorAll('circle').forEach(c => {
    c.addEventListener('mousemove', (e) => {
      tooltip.style.display = 'block';
      tooltip.style.left = (e.clientX + 12) + 'px';
      tooltip.style.top = (e.clientY + 12) + 'px';
      tooltip.innerHTML = `<b>${c.dataset.uf}</b><br>x: ${fmtPct(+c.dataset.x)}<br>y: ${fmtPct(+c.dataset.y)}`;
    });
    c.addEventListener('mouseleave', () => tooltip.style.display = 'none');
  });
}

montarSeletor();
desenharMapa(Object.keys(indicadores)[0]);
montarTabela();
desenharScatter();
</script>
</body>
</html>
"""


def main() -> None:
    log("=== 05_consolida_e_dashboard.py: início ===")
    uf_df = consolidar_uf()
    uf_df.to_csv(OUT / "consolidado_uf.csv", index=False, encoding="utf-8")
    log(f"OK: out/consolidado_uf.csv ({len(uf_df)} linhas)")

    mun_df = consolidar_municipio()
    mun_df.to_csv(OUT / "consolidado_municipio.csv", index=False, encoding="utf-8")
    log(f"OK: out/consolidado_municipio.csv ({len(mun_df)} linhas)")

    html = montar_dashboard(uf_df)
    (OUT / "dashboard.html").write_text(html, encoding="utf-8")
    log("OK: out/dashboard.html")
    log("=== 05_consolida_e_dashboard.py: fim ===")


if __name__ == "__main__":
    main()
