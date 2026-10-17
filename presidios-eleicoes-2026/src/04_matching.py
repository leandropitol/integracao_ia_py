#!/usr/bin/env python3
"""
04_matching.py — casa estabelecimentos do TSE (data/interim/votacao_estabelecimento.csv)
com unidades do SISDEPEN (data/interim/perfil_penal_unidade.csv) por UF +
nome normalizado/expandido, usando rapidfuzz.

Regra: nunca forçar um match duvidoso.
  - score >= LIMIAR_AUTO: aceito automaticamente.
  - LIMIAR_REVISAR <= score < LIMIAR_AUTO: vai para matching_revisar.csv,
    fica como "não casado" na base principal até alguém confirmar.
  - score < LIMIAR_REVISAR: não casado, "sem dados" no relatório final.

Saída:
  - data/interim/matching.csv          (todas as tentativas, com score)
  - output/matching_revisar.csv        (só os pares de score médio, p/ revisão humana)
"""
from __future__ import annotations

import pandas as pd
from rapidfuzz import fuzz

from _common import INTERIM, OUTPUT, log, parar
from config import normalizar_nome, expandir_abreviacoes

LIMIAR_AUTO = 92
LIMIAR_REVISAR = 75


def chave_matching(nome: str) -> str:
    return expandir_abreviacoes(normalizar_nome(nome))


def main() -> None:
    log("=== 04_matching.py: início ===")
    tse_path = INTERIM / "votacao_estabelecimento.csv"
    sisdepen_path = INTERIM / "perfil_penal_unidade.csv"
    if not tse_path.exists():
        parar(f"{tse_path} não existe. Rode 02_carregar_votacao.py primeiro.")
    if not sisdepen_path.exists():
        parar(f"{sisdepen_path} não existe. Rode 03_carregar_sisdepen.py primeiro.")

    tse = pd.read_csv(tse_path, dtype=str)
    sisdepen = pd.read_csv(sisdepen_path, dtype=str)

    tse_estab = tse[["uf", "nome_local"]].drop_duplicates().reset_index(drop=True)
    tse_estab["chave"] = tse_estab["nome_local"].map(chave_matching)
    sisdepen_estab = sisdepen[["uf", "nome_unidade"]].drop_duplicates().reset_index(drop=True)
    sisdepen_estab["chave"] = sisdepen_estab["nome_unidade"].map(chave_matching)

    resultados = []
    for _, row_tse in tse_estab.iterrows():
        candidatos = sisdepen_estab[sisdepen_estab["uf"] == row_tse["uf"]]
        if candidatos.empty:
            resultados.append(
                {
                    "uf": row_tse["uf"],
                    "nome_local_tse": row_tse["nome_local"],
                    "nome_unidade_sisdepen": pd.NA,
                    "score": 0,
                    "status": "sem_candidato_na_uf",
                }
            )
            continue

        scores = candidatos["chave"].map(lambda c: fuzz.token_sort_ratio(row_tse["chave"], c))
        melhor_idx = scores.idxmax()
        melhor_score = scores.loc[melhor_idx]
        melhor_nome = candidatos.loc[melhor_idx, "nome_unidade"]

        if melhor_score >= LIMIAR_AUTO:
            status = "auto"
        elif melhor_score >= LIMIAR_REVISAR:
            status = "revisar"
        else:
            status = "nao_casado"

        resultados.append(
            {
                "uf": row_tse["uf"],
                "nome_local_tse": row_tse["nome_local"],
                "nome_unidade_sisdepen": melhor_nome,
                "score": melhor_score,
                "status": status,
            }
        )

    matching = pd.DataFrame(resultados)
    matching.to_csv(INTERIM / "matching.csv", index=False, encoding="utf-8")

    n_auto = (matching["status"] == "auto").sum()
    n_revisar = (matching["status"] == "revisar").sum()
    n_sem_match = (matching["status"].isin(["nao_casado", "sem_candidato_na_uf"])).sum()
    log(
        f"Matching: {n_auto} automáticos, {n_revisar} para revisão manual, "
        f"{n_sem_match} sem casamento (score < {LIMIAR_REVISAR} ou sem candidato na UF) "
        f"de {len(matching)} estabelecimentos TSE."
    )

    revisar = matching[matching["status"] == "revisar"].sort_values("score", ascending=False)
    revisar.to_csv(OUTPUT / "matching_revisar.csv", index=False, encoding="utf-8")
    if len(revisar):
        log(f"AVISO: {len(revisar)} pares de score médio em output/matching_revisar.csv — revisar manualmente antes de considerar o relatório final.")

    log("=== 04_matching.py: fim ===")


if __name__ == "__main__":
    main()
