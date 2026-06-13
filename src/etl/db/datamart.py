"""Carga idempotente no datamart MySQL + bootstrap das tabelas.

Re-execuções são seguras: DELETE por (carteira, data_ref) + INSERT em lotes,
na mesma transação.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import polars as pl
from sqlalchemy import Engine, text

log = logging.getLogger(__name__)

LOTE = 10_000


def init_datamart(engine: Engine, dir_ddl: Path) -> list[str]:
    executados = []
    with engine.begin() as conn:
        for arquivo in sorted(dir_ddl.glob("*.sql")):
            for stmt in arquivo.read_text(encoding="utf-8").split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
            executados.append(arquivo.name)
    return executados


def carregar_fato(
    engine: Engine,
    tabela: str,
    df: pl.DataFrame,
    carteira: str,
    data_ref: date,
) -> int:
    df = df.with_columns(
        pl.lit(carteira).alias("carteira"), pl.lit(data_ref).alias("data_ref")
    )
    colunas = df.columns
    insert = text(
        f"INSERT INTO {tabela} ({', '.join(colunas)}) "
        f"VALUES ({', '.join(':' + c for c in colunas)})"
    )
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {tabela} WHERE carteira = :c AND data_ref = :d"),
            {"c": carteira, "d": data_ref},
        )
        linhas = df.to_dicts()
        for i in range(0, len(linhas), LOTE):
            conn.execute(insert, linhas[i : i + LOTE])
    log.info("%s: %s linhas carregadas (carteira=%s data_ref=%s)", tabela, len(df), carteira, data_ref)
    return len(df)
