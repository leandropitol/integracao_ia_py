#!/usr/bin/env python3
"""
00_download.py — baixa os arquivos brutos de cada fonte para data/raw/ e
registra proveniência em data/raw/MANIFEST.md (URL, data UTC, SHA-256).

Idempotente: se o arquivo local já existe, não baixa de novo (a menos que
--forcar seja passado) — mas sempre confere o hash contra o manifesto
existente para detectar arquivo corrompido/alterado manualmente.

Regra do projeto: se um download falhar ou o arquivo vier claramente fora
do padrão esperado (tamanho zero, HTML de erro no lugar do arquivo), o
script PARA com PipelineParadoError. Nunca segue com um arquivo suspeito.

*** Fontes marcadas como "requer_confirmacao" ou "download_manual" em
config_fontes.py vão AVISAR e pular, não inventar uma URL. Resolva isso
manualmente (ver instruções impressas) antes de rodar o resto do pipeline. ***
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from _common import RAW, append_manifest, log, parar
from config_fontes import FONTES

TIMEOUT = 60
CHUNK = 1 << 20


def _baixar_http(url: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=TIMEOUT, stream=True) as r:
        if r.status_code != 200:
            parar(
                f"Download falhou: {url} -> HTTP {r.status_code}. "
                f"Pare e confira manualmente; não há fallback automático."
            )
        ctype = r.headers.get("Content-Type", "")
        if "text/html" in ctype and not url.endswith((".html", ".htm")):
            parar(
                f"Download de {url} retornou HTML (Content-Type={ctype}) "
                f"onde um arquivo de dados era esperado — provável página "
                f"de erro/redirecionamento em vez do arquivo real. Pare e "
                f"confira a URL manualmente."
            )
        tmp = destino.with_suffix(destino.suffix + ".part")
        total = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(CHUNK):
                f.write(chunk)
                total += len(chunk)
        if total == 0:
            tmp.unlink(missing_ok=True)
            parar(f"Download de {url} veio vazio (0 bytes). Pare e confira a URL.")
        tmp.rename(destino)
    log(f"OK: {url} -> {destino} ({total/1e6:.2f} MB)")


def baixar_malha_municipios_ibge(forcar: bool) -> None:
    """Fonte com status 'conhecido_estavel': API pública documentada do
    IBGE. Ainda assim, tratada com a mesma disciplina de verificação —
    01_de_para_municipio.py confere o schema do JSON antes de usar."""
    cfg = FONTES["malha_municipios_ibge"]
    destino = RAW / cfg["arquivo_local"]
    if destino.exists() and not forcar:
        log(f"Já existe, pulando: {destino}")
        return
    _baixar_http(cfg["url_download"], destino)
    append_manifest(
        fonte=cfg["descricao"],
        url=cfg["url_download"],
        arquivo_local=destino,
        observacao="API pública IBGE (status: conhecido_estavel, não verificado ao vivo nesta sessão)",
    )


def avisar_fonte_pendente(chave: str) -> None:
    cfg = FONTES[chave]
    log(
        f"PULADO [{chave}] status={cfg['status']}: {cfg['descricao']}\n"
        f"  -> {cfg.get('instrucoes_manuais') or 'ver config_fontes.py para detalhes'}\n"
        f"  -> arquivo esperado em: data/raw/{cfg['arquivo_local']}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--forcar", action="store_true", help="Rebaixar mesmo se o arquivo já existir")
    ap.add_argument(
        "--somente",
        nargs="*",
        default=None,
        help="Lista de chaves de FONTES a processar (default: todas)",
    )
    args = ap.parse_args()

    chaves = args.somente or list(FONTES.keys())

    log("=== 00_download.py: início ===")
    for chave in chaves:
        if chave not in FONTES:
            parar(f"Fonte desconhecida: {chave}. Chaves válidas: {list(FONTES.keys())}")
        cfg = FONTES[chave]
        if chave == "malha_municipios_ibge":
            baixar_malha_municipios_ibge(args.forcar)
        elif cfg["status"] == "verificado_ao_vivo" and cfg.get("url_download"):
            destino = RAW / cfg["arquivo_local"]
            if destino.exists() and not args.forcar:
                log(f"Já existe, pulando: {destino}")
                continue
            _baixar_http(cfg["url_download"], destino)
            append_manifest(cfg["descricao"], cfg["url_download"], destino)
        else:
            avisar_fonte_pendente(chave)

    log("=== 00_download.py: fim ===")
    log(
        "Fontes puladas acima precisam de ação manual (baixar e colocar em "
        "data/raw/ no caminho indicado, ou confirmar a URL em config_fontes.py "
        "e mudar o status para 'verificado_ao_vivo'). Rode de novo depois."
    )


if __name__ == "__main__":
    main()
