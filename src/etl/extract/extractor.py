"""Extração em chunks do MySQL para Parquet (staging).

Memória fica limitada pelo chunk_size independentemente do volume total:
stream_results + fetchmany -> um arquivo parquet por chunk. A leitura
posterior é lazy (pl.scan_parquet) sobre todos os chunks do indicador.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import polars as pl
from sqlalchemy import Engine, text
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)


def preparar_staging(dir_staging: Path, carteira: str, data_ref: str) -> Path:
    pasta = dir_staging / carteira / data_ref
    if pasta.exists():
        shutil.rmtree(pasta)  # re-execuções partem de staging limpo
    pasta.mkdir(parents=True)
    return pasta


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30), reraise=True)
def extrair_indicador(
    engine: Engine,
    sql: str,
    params: dict,
    pasta_staging: Path,
    indicador: str,
    chunk_size: int,
) -> int:
    """Executa a query e grava chunks parquet. Retorna total de linhas."""
    total = 0
    parte = 0
    with engine.connect().execution_options(stream_results=True) as conn:
        cursor = conn.execute(text(sql), params)
        colunas = list(cursor.keys())
        while True:
            linhas = cursor.fetchmany(chunk_size)
            if not linhas:
                break
            df = pl.DataFrame(
                {col: [r[i] for r in linhas] for i, col in enumerate(colunas)}
            )
            df.write_parquet(
                pasta_staging / f"{indicador}_{parte:04d}.parquet",
                compression="zstd",
            )
            total += len(df)
            parte += 1
    if total == 0:
        # garante um arquivo vazio com schema mínimo para o scan não falhar
        pl.DataFrame({c: [] for c in colunas}).write_parquet(
            pasta_staging / f"{indicador}_0000.parquet", compression="zstd"
        )
    log.info("Indicador %s: %s linhas extraídas em %s chunk(s)", indicador, total, parte or 1)
    return total


def scan_indicador(pasta_staging: Path, indicador: str) -> pl.LazyFrame:
    return pl.scan_parquet(pasta_staging / f"{indicador}_*.parquet")
