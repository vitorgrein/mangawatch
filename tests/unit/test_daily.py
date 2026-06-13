"""Valores esperados calculados à mão — ver docstring de tests/conftest.py."""

import polars as pl

from etl.reports.daily import gerar


def _metrica(df: pl.DataFrame, segmentacao: str, segmento: str, metrica: str) -> float:
    linhas = df.filter(
        (pl.col("segmentacao") == segmentacao)
        & (pl.col("segmento") == segmento)
        & (pl.col("metrica") == metrica)
    )
    assert linhas.height == 1, f"{segmentacao}/{segmento}/{metrica}: {linhas.height} linhas"
    return linhas["valor"][0]


def test_daily_total(contexto):
    df = gerar(contexto)
    total = lambda m: _metrica(df, "total", "total", m)  # noqa: E731

    assert total("qtd_estoque_unica") == 4
    assert total("valor_estoque") == 1000.0
    # discado: c1 com 2 eventos na sexta + 1 no sábado (rola p/ sexta) = acum 3
    assert total("qtd_discado_unica") == 1
    assert total("qtd_discado_acum") == 3
    # acionamento humano: c1 e c3
    assert total("qtd_acionamento_unica") == 2
    # acordo do dia: só A1 (A2 foi dia 10)
    assert total("qtd_acordo_unica") == 1
    assert total("valor_acordo") == 50.0
    # pagos do dia (por data de pagamento): c1 e c4
    assert total("qtd_pago_unica") == 2
    assert total("valor_pago") == 35.0
    # canais sem eventos zeram
    assert total("qtd_email_unica") == 0


def test_daily_por_segmento(contexto):
    df = gerar(contexto)
    # produto CARTAO = c1 + c3
    assert _metrica(df, "produto", "CARTAO", "qtd_estoque_unica") == 2
    assert _metrica(df, "produto", "CARTAO", "valor_estoque") == 400.0
    assert _metrica(df, "produto", "CARTAO", "qtd_acionamento_unica") == 2
    # faixa nula vira "(não informado)" (c4)
    assert _metrica(df, "faixa_atraso", "(não informado)", "qtd_estoque_unica") == 1
    assert _metrica(df, "faixa_atraso", "(não informado)", "qtd_pago_unica") == 1


def test_daily_formato_longo(contexto):
    df = gerar(contexto)
    assert df.columns == ["segmentacao", "segmento", "metrica", "valor"]
    assert df.filter(pl.col("segmentacao") == "total").height > 0
    # chave única
    assert df.unique(["segmentacao", "segmento", "metrica"]).height == df.height
