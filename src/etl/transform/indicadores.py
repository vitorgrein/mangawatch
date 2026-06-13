"""Constrói a tabela larga por cliente (intermediária, nunca vai ao Power BI).

Uma linha por cliente do ESTOQUE; para cada indicador configurado:
  {ind}_acum  -> total de eventos do cliente na janela
  {ind}_unica -> 1/0 (teve ao menos um evento)
  {ind}_valor -> soma de `valor` (apenas estoque/acordo/pago, se a query retornar)

Eventos de clientes fora do estoque são descartados (e contabilizados para
aviso de qualidade). Eventos têm a data rolada para o dia útil dono dela.
"""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from etl.calendario import CalendarioUtil
from etl.config.schema import INDICADORES_COM_VALOR

COL_ID = "id_cliente"
COL_DATA = "data_evento"


def mapa_dias_uteis(cal: CalendarioUtil, ini: date, fim: date) -> pl.LazyFrame:
    """Tabela pequena (data_evento -> dia_util) para join, cobrindo [ini, fim]."""
    dias: list[date] = []
    d = ini
    while d <= fim:
        dias.append(d)
        d += timedelta(days=1)
    return pl.LazyFrame(
        {COL_DATA: dias, "dia_util": [cal.rolar_para_dia_util(x) for x in dias]}
    )


def preparar_eventos(
    eventos: pl.LazyFrame,
    mapa: pl.LazyFrame,
    ids_estoque: pl.LazyFrame,
    coluna_data: str = COL_DATA,
) -> tuple[pl.LazyFrame, int]:
    """Normaliza um indicador de evento: qtd default 1, dia_util, só clientes do estoque.

    Retorna (LazyFrame preparado, qtd de linhas descartadas por estarem fora do estoque).
    """
    schema = eventos.collect_schema()
    if "qtd" not in schema.names():
        eventos = eventos.with_columns(pl.lit(1).alias("qtd"))
    tipo_id = ids_estoque.collect_schema()[COL_ID]
    eventos = eventos.with_columns(
        pl.col(COL_ID).cast(tipo_id),  # extrações vazias chegam com dtype Null
        pl.col(coluna_data).cast(pl.Date).alias(COL_DATA),
        pl.col("qtd").cast(pl.Int64),
    )

    fora = (
        eventos.join(ids_estoque, on=COL_ID, how="anti")
        .select(pl.len())
        .collect()
        .item()
    )
    dentro = eventos.join(ids_estoque, on=COL_ID, how="semi")
    return dentro.join(mapa, on=COL_DATA, how="left"), int(fora)


def tabela_larga(
    estoque: pl.LazyFrame,
    eventos: dict[str, pl.LazyFrame],
    dia_util_ini: date,
    dia_util_fim: date,
) -> pl.LazyFrame:
    """Agrega cada indicador por cliente na janela [dia_util_ini, dia_util_fim]
    e junta tudo no estoque (left join + zeros)."""
    tem_valor_estoque = "valor" in estoque.collect_schema().names()
    larga = estoque.with_columns(
        pl.lit(1, dtype=pl.Int64).alias("estoque_acum"),
        pl.lit(1, dtype=pl.Int8).alias("estoque_unica"),
        (
            pl.col("valor").cast(pl.Float64)
            if tem_valor_estoque
            else pl.lit(None, dtype=pl.Float64)
        ).alias("estoque_valor"),
    ).drop("valor", strict=False)

    for ind, lf in eventos.items():
        na_janela = lf.filter(
            pl.col("dia_util").is_between(dia_util_ini, dia_util_fim)
        )
        aggs = [pl.col("qtd").sum().cast(pl.Int64).alias(f"{ind}_acum")]
        if ind in INDICADORES_COM_VALOR and "valor" in lf.collect_schema().names():
            aggs.append(pl.col("valor").sum().cast(pl.Float64).alias(f"{ind}_valor"))
        por_cliente = na_janela.group_by(COL_ID).agg(aggs)
        larga = larga.join(por_cliente, on=COL_ID, how="left").with_columns(
            pl.col(f"{ind}_acum").fill_null(0),
        )
        larga = larga.with_columns(
            (pl.col(f"{ind}_acum") > 0).cast(pl.Int8).alias(f"{ind}_unica")
        )
    return larga
