"""Relatório FUNIL: foto acumulada do mês até a data_ref (uma por dia útil).

A ordem das etapas vem do config da carteira (funil.etapas). Modos de cascata:
  respeitar     -> cliente só conta na etapa N se conta na N-1; o pagamento é
                   atribuído à data de GERAÇÃO do acordo (via data_acordo)
  nao_respeitar -> total de cada etapa independente das anteriores
  forcar        -> cliente positivo na etapa N força as anteriores a positivas
O estoque sempre abre a cascata e é respeitado em todos os modos (a tabela
larga só contém clientes do estoque).
"""

from __future__ import annotations

import polars as pl

from etl.reports.base import ContextoRun, registrar, visoes_segmentacao
from etl.transform.indicadores import tabela_larga

COLUNAS_SAIDA = [
    "segmentacao",
    "segmento",
    "etapa_ordem",
    "etapa",
    "qtd_clientes",
    "pct_da_base",
    "pct_etapa_anterior",
    "cascata",
]


@registrar("funil", tabela="fato_funil")
def gerar(ctx: ContextoRun) -> pl.DataFrame:
    cfg_funil = ctx.cfg.funil
    eventos = dict(ctx.eventos)
    if cfg_funil.cascata == "respeitar" and ctx.pago_por_data_acordo is not None:
        eventos["pago"] = ctx.pago_por_data_acordo

    larga = tabela_larga(
        ctx.estoque, eventos, dia_util_ini=ctx.mes_ini, dia_util_fim=ctx.data_ref
    )

    # flag de cada etapa = algum indicador da etapa com _unica = 1
    etapas = cfg_funil.etapas
    flags = [
        pl.max_horizontal([pl.col(f"{ind}_unica") for ind in etapa.indicadores])
        .cast(pl.Int8)
        .alias(f"_flag_{i}")
        for i, etapa in enumerate(etapas)
    ]
    larga = larga.with_columns(flags)

    if cfg_funil.cascata == "respeitar":
        for i in range(1, len(etapas)):
            larga = larga.with_columns(
                (pl.col(f"_flag_{i}") * pl.col(f"_flag_{i - 1}")).alias(f"_flag_{i}")
            )
    elif cfg_funil.cascata == "forcar":
        for i in range(len(etapas) - 2, -1, -1):
            larga = larga.with_columns(
                pl.max_horizontal(pl.col(f"_flag_{i}"), pl.col(f"_flag_{i + 1}")).alias(
                    f"_flag_{i}"
                )
            )
    larga = larga.collect()

    partes: list[pl.DataFrame] = []
    for nome_seg, expr_seg in visoes_segmentacao(ctx):
        agregado = (
            larga.lazy()
            .group_by(expr_seg.alias("segmento"))
            .agg(
                [
                    pl.col(f"_flag_{i}").sum().cast(pl.Int64).alias(f"_qtd_{i}")
                    for i in range(len(etapas))
                ]
            )
            .collect()
        )
        for i, etapa in enumerate(etapas):
            qtd = pl.col(f"_qtd_{i}")
            base = pl.col("_qtd_0")
            anterior = pl.col(f"_qtd_{i - 1}") if i > 0 else base
            partes.append(
                agregado.select(
                    pl.lit(nome_seg).alias("segmentacao"),
                    pl.col("segmento"),
                    pl.lit(i + 1, dtype=pl.Int32).alias("etapa_ordem"),
                    pl.lit(etapa.nome).alias("etapa"),
                    qtd.alias("qtd_clientes"),
                    pl.when(base > 0).then(qtd / base).alias("pct_da_base"),
                    pl.when(anterior > 0)
                    .then(qtd / anterior)
                    .alias("pct_etapa_anterior"),
                    pl.lit(cfg_funil.cascata).alias("cascata"),
                )
            )

    return pl.concat(partes).select(COLUNAS_SAIDA).sort(
        ["segmentacao", "segmento", "etapa_ordem"]
    )
