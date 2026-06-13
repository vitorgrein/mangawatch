"""Funil acumulado do mês (até 12/06) nos 3 modos de cascata.

Flags por cliente no mês (ver conftest):
  estoque: c1..c4 | acionado_sistema: c1,c2 | acionamento: c1,c3 | acordo: c1,c3
  pago por data de pagamento: c1,c4
  pago por data do acordo (modo respeitar): c1 (o acordo do c4 é de maio)
"""

import polars as pl
import pytest

from etl.reports.funil import gerar


def _qtds(df: pl.DataFrame) -> list[int]:
    return (
        df.filter((pl.col("segmentacao") == "total"))
        .sort("etapa_ordem")["qtd_clientes"]
        .to_list()
    )


def test_cascata_respeitar(contexto):
    df = gerar(contexto)
    # estoque 4 -> acionado {c1,c2} -> AND acionamento {c1} -> acordo {c1} -> pago {c1}
    assert _qtds(df) == [4, 2, 1, 1, 1]
    total = df.filter(pl.col("segmentacao") == "total").sort("etapa_ordem")
    assert total["pct_da_base"].to_list() == pytest.approx([1.0, 0.5, 0.25, 0.25, 0.25])
    assert total["pct_etapa_anterior"].to_list() == pytest.approx([1.0, 0.5, 0.5, 1.0, 1.0])
    assert total["cascata"].unique().to_list() == ["respeitar"]


def test_cascata_nao_respeitar(contexto):
    contexto.cfg = contexto.cfg.model_copy(deep=True)
    contexto.cfg.funil.cascata = "nao_respeitar"
    # totais independentes; pago pela data de pagamento: c1 e c4
    assert _qtds(gerar(contexto)) == [4, 2, 2, 2, 2]


def test_cascata_forcar(contexto):
    contexto.cfg = contexto.cfg.model_copy(deep=True)
    contexto.cfg.funil.cascata = "forcar"
    # pago {c1,c4} força acordo {c1,c3}+{c4}=3, acionamento 3, acionado vira 4
    assert _qtds(gerar(contexto)) == [4, 4, 3, 3, 2]


def test_funil_por_segmento(contexto):
    df = gerar(contexto)
    cartao = df.filter(
        (pl.col("segmentacao") == "produto") & (pl.col("segmento") == "CARTAO")
    ).sort("etapa_ordem")
    # CARTAO = c1,c3: estoque 2 -> acionado {c1} -> acionamento {c1} -> acordo -> pago
    assert cartao["qtd_clientes"].to_list() == [2, 1, 1, 1, 1]


def test_ordem_das_etapas_vem_do_config(contexto):
    df = gerar(contexto)
    total = df.filter(pl.col("segmentacao") == "total").sort("etapa_ordem")
    assert total["etapa"].to_list() == [
        "estoque", "acionado_sistema", "acionamento", "acordo", "pago",
    ]
