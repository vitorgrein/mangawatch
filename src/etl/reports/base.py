"""Registry de relatórios: um relatório novo = um módulo novo com @registrar.

As carteiras optam por relatório na lista `relatorios:` do config.yml.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, TYPE_CHECKING

import polars as pl

from etl.calendario import CalendarioUtil
from etl.config.schema import CarteiraConfig

if TYPE_CHECKING:
    pass


@dataclass
class ContextoRun:
    """Tudo que um relatório precisa para agregar (extração já aconteceu)."""

    cfg: CarteiraConfig
    data_ref: date
    data_fim: date  # último dia (inclusive) cujos eventos acumulam em data_ref
    cal: CalendarioUtil
    estoque: pl.LazyFrame  # com colunas seg_*
    eventos: dict[str, pl.LazyFrame]  # indicador -> eventos preparados (dia_util)
    pago_por_data_acordo: pl.LazyFrame | None  # pago reatribuído à data do acordo
    avisos: list[str] = field(default_factory=list)

    @property
    def mes_ini(self) -> date:
        return self.data_ref.replace(day=1)


@dataclass(frozen=True)
class Relatorio:
    nome: str
    tabela: str  # tabela de destino no datamart
    gerar: Callable[[ContextoRun], pl.DataFrame]


REGISTRY: dict[str, Relatorio] = {}


def registrar(nome: str, tabela: str):
    def deco(fn: Callable[[ContextoRun], pl.DataFrame]):
        REGISTRY[nome] = Relatorio(nome=nome, tabela=tabela, gerar=fn)
        return fn

    return deco


def visoes_segmentacao(ctx: ContextoRun) -> list[tuple[str, pl.Expr]]:
    """Pares (nome_da_segmentacao, expressão do segmento), incluindo a visão total."""
    visoes: list[tuple[str, pl.Expr]] = [("total", pl.lit("total"))]
    for seg in ctx.cfg.segmentacoes:
        visoes.append(
            (seg.nome, pl.col(f"seg_{seg.nome}").fill_null("(não informado)"))
        )
    return visoes
