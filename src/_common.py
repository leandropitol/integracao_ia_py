"""
Utilidades compartilhadas por todos os scripts do pipeline.

Convenções do projeto (ver README.md):
- data/raw/     é imutável; nunca editar um arquivo baixado.
- data/interim/ guarda produtos intermediários derivados de data/raw.
- out/          guarda os entregáveis finais (CSVs por indicador, consolidado, dashboard).
- Falha de download ou mudança inesperada de layout: o pipeline PARA
  (levanta exceção com mensagem clara) em vez de seguir com um parser
  alternativo inventado. Isso é feito aqui via `assert_columns` /
  `PipelineParadoError`.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / "data" / "raw"
INTERIM = PROJECT_ROOT / "data" / "interim"
OUT = PROJECT_ROOT / "out"
MANIFEST_PATH = RAW / "MANIFEST.md"

for _d in (RAW, INTERIM, OUT):
    _d.mkdir(parents=True, exist_ok=True)


class PipelineParadoError(RuntimeError):
    """
    Levantada quando o pipeline encontra algo que não pode seguir sem
    intervenção humana: download falhou, layout de coluna mudou, fonte
    saiu do ar, cobertura caiu abaixo do esperado, etc.

    Por regra do projeto: nunca capturar esta exceção para "seguir mesmo
    assim" com um parser alternativo silencioso. Corrigir a causa (nova
    URL, novo nome de coluna no CONFIG do script) e rodar de novo.
    """


def assert_columns(df: pd.DataFrame, expected: list[str], source_name: str) -> None:
    """Confere que as colunas esperadas existem no DataFrame; se não,
    para o pipeline com uma mensagem que lista o que era esperado e o
    que foi de fato encontrado no arquivo — para diagnóstico rápido
    quando a fonte muda de layout entre edições."""
    faltando = [c for c in expected if c not in df.columns]
    if faltando:
        raise PipelineParadoError(
            f"[{source_name}] Layout mudou ou coluna não encontrada.\n"
            f"  Colunas esperadas ausentes: {faltando}\n"
            f"  Colunas encontradas no arquivo: {list(df.columns)}\n"
            f"  Ação: ajuste o mapeamento de colunas no topo do script "
            f"correspondente após confirmar manualmente o novo layout. "
            f"Não prossiga adivinhando a coluna certa."
        )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def append_manifest(fonte: str, url: str, arquivo_local: Path, observacao: str = "") -> None:
    """Registra proveniência: URL, data/hora do download (UTC) e SHA-256
    do arquivo baixado, em data/raw/MANIFEST.md. Nunca sobrescreve
    entradas anteriores — apenas acrescenta."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    novo = not MANIFEST_PATH.exists()
    with open(MANIFEST_PATH, "a", encoding="utf-8") as f:
        if novo:
            f.write("# Manifesto de proveniência dos dados brutos\n\n")
            f.write("| Fonte | URL | Arquivo local | Baixado em (UTC) | SHA-256 | Observação |\n")
            f.write("|---|---|---|---|---|---|\n")
        agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        digest = sha256_file(arquivo_local) if arquivo_local.exists() else "N/A"
        rel = arquivo_local.relative_to(PROJECT_ROOT)
        f.write(f"| {fonte} | {url} | `{rel}` | {agora} | `{digest}` | {observacao} |\n")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


def parar(msg: str) -> None:
    """Ponto único de parada explícita do pipeline (usado quando a causa
    não é uma coluna faltando, mas algo mais amplo: download falhou,
    fonte fora do ar, cobertura suspeita)."""
    raise PipelineParadoError(msg)
