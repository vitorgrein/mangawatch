"""Relatório DAILY: indicadores do dia útil (data_ref), em formato longo.

Métricas por indicador configurado:
  qtd_{ind}_unica -> clientes distintos do estoque com o indicador no dia
  qtd_{ind}_acum  -> total de eventos no dia (acumulativo por cliente somado)
  valor_{ind}     -> soma de valor (estoque, acordo, pago — se a query retornar)

Taxas e consolidação mensal são calculadas no Power BI.
"""

from __future__ import annotations

import polars as pl

from etl.reports.base import ContextoRun, registrar, visoes_segmentacao
from etl.transform.indicadores import tabela_larga

COLUNAS_SAIDA = ["segmentacao", "segmento", "metrica", "valor"]


@registrar("daily", tabela="fato_daily")
def gerar(ctx: ContextoRun) -> pl.DataFrame:
    larga = tabela_larga(
        ctx.estoque, ctx.eventos, dia_util_ini=ctx.data_ref, dia_util_fim=ctx.data_ref
    ).collect()

    metricas: list[tuple[str, str]] = []  # (coluna na larga, nome da métrica)
    for ind in ctx.cfg.indicadores_ativos:
        metricas.append((f"{ind}_unica", f"qtd_{ind}_unica"))
        metricas.append((f"{ind}_acum", f"qtd_{ind}_acum"))
        if f"{ind}_valor" in larga.columns:
            metricas.append((f"{ind}_valor", f"valor_{ind}"))

    partes: list[pl.DataFrame] = []
    for nome_seg, expr_seg in visoes_segmentacao(ctx):
        agregado = (
            larga.lazy()
            .group_by(expr_seg.alias("segmento"))
            .agg(
                [
                    pl.col(col).sum().cast(pl.Float64).alias(metrica)
                    for col, metrica in metricas
                ]
            )
            .collect()
        )
        partes.append(
            agregado.unpivot(
                index="segmento", variable_name="metrica", value_name="valor"
            )
            .with_columns(pl.lit(nome_seg).alias("segmentacao"))
            .drop_nulls("valor")
        )

    return pl.concat(partes).select(COLUNAS_SAIDA).sort(COLUNAS_SAIDA[:3])
