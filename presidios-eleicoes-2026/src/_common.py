"""
Utilidades compartilhadas pelos scripts deste projeto.

Mesmo padrão do pipeline de municípios no restante do repositório: para
com mensagem clara (PipelineParadoError) em vez de seguir com layout
divergente; nunca estima dado ausente.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / "data" / "raw"
INTERIM = PROJECT_ROOT / "data" / "interim"
OUTPUT = PROJECT_ROOT / "output"

for _d in (RAW, INTERIM, OUTPUT):
    _d.mkdir(parents=True, exist_ok=True)


class PipelineParadoError(RuntimeError):
    """Levantada quando falta um arquivo de entrada ou o layout não bate
    com o esperado. Nunca capturar para seguir com um parser alternativo
    inventado — corrigir o CONFIG do script e rodar de novo."""


def assert_columns(df: pd.DataFrame, expected: list[str], source_name: str) -> None:
    faltando = [c for c in expected if c not in df.columns]
    if faltando:
        raise PipelineParadoError(
            f"[{source_name}] Coluna(s) esperada(s) ausente(s): {faltando}\n"
            f"  Colunas encontradas: {list(df.columns)}\n"
            f"  Ajuste o mapeamento de colunas no topo do script e rode de novo."
        )


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


def parar(msg: str) -> None:
    raise PipelineParadoError(msg)


def listar_arquivos(diretorio: Path, padrao: str) -> list[Path]:
    arquivos = sorted(diretorio.glob(padrao))
    return arquivos
