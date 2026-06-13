"""Deriva as colunas de segmentação (seg_*) no estoque, conforme o config.

As segmentações vivem no ESTOQUE: os demais indicadores herdam os segmentos
do cliente via join, garantindo uma única fonte de verdade por carteira.
"""

from __future__ import annotations

import polars as pl

from etl.config.schema import Segmentacao

PREFIXO = "seg_"


def aplicar_segmentacoes(
    estoque: pl.LazyFrame, segmentacoes: list[Segmentacao]
) -> pl.LazyFrame:
    exprs = [_expr_segmento(s).alias(PREFIXO + s.nome) for s in segmentacoes]
    return estoque.with_columns(exprs) if exprs else estoque


def _expr_segmento(seg: Segmentacao) -> pl.Expr:
    origem = pl.col(seg.coluna_origem)
    if seg.tipo == "coluna":
        return origem.cast(pl.Utf8)

    # tipo == "faixas": buckets por limite superior inclusivo, última faixa aberta
    expr: pl.Expr | None = None
    for faixa in seg.faixas:  # type: ignore[union-attr]
        if faixa.ate is None:
            continue
        cond = origem <= faixa.ate
        expr = pl.when(cond).then(pl.lit(faixa.rotulo)) if expr is None else expr.when(cond).then(pl.lit(faixa.rotulo))
    rotulo_aberto = seg.faixas[-1].rotulo  # type: ignore[index]
    if expr is None:
        return pl.when(origem.is_not_null()).then(pl.lit(rotulo_aberto)).otherwise(None)
    return (
        pl.when(origem.is_null())
        .then(None)
        .otherwise(expr.otherwise(pl.lit(rotulo_aberto)))
    )


def colunas_segmento(segmentacoes: list[Segmentacao]) -> list[str]:
    return [PREFIXO + s.nome for s in segmentacoes]
