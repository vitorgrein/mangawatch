import polars as pl

from etl.config.schema import Segmentacao
from etl.transform.segmenter import aplicar_segmentacoes


def _seg_faixas():
    return Segmentacao(
        nome="faixa_atraso",
        tipo="faixas",
        coluna_origem="dias_atraso",
        faixas=[
            {"ate": 30, "rotulo": "00-30"},
            {"ate": 90, "rotulo": "31-90"},
            {"rotulo": "90+"},
        ],
    )


def test_faixas_limite_inclusivo_e_aberta():
    lf = pl.LazyFrame({"dias_atraso": [0, 30, 31, 90, 91, 5000, None]})
    out = aplicar_segmentacoes(lf, [_seg_faixas()]).collect()
    assert out["seg_faixa_atraso"].to_list() == [
        "00-30", "00-30", "31-90", "31-90", "90+", "90+", None,
    ]


def test_tipo_coluna_vira_texto():
    seg = Segmentacao(nome="produto", tipo="coluna", coluna_origem="produto")
    lf = pl.LazyFrame({"produto": ["CARTAO", None]})
    out = aplicar_segmentacoes(lf, [seg]).collect()
    assert out["seg_produto"].to_list() == ["CARTAO", None]


def test_multiplas_segmentacoes():
    seg2 = Segmentacao(nome="produto", tipo="coluna", coluna_origem="produto")
    lf = pl.LazyFrame({"dias_atraso": [10], "produto": ["CDC"]})
    out = aplicar_segmentacoes(lf, [_seg_faixas(), seg2]).collect()
    assert set(out.columns) >= {"seg_faixa_atraso", "seg_produto"}
