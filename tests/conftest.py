"""Fixtures: cenário pequeno calculado à mão (junho/2026).

Calendário do cenário: data_ref = sex 12/06/2026; sáb 13 e dom 14 acumulam
na sexta (próximo dia útil = seg 15/06). mes_ini = 01/06/2026.

Estoque (4 clientes):
  c1: atraso 10  (00-30),  CARTAO, valor 100
  c2: atraso 90  (31-90),  CDC,    valor 200
  c3: atraso 200 (180+),   CARTAO, valor 300
  c4: atraso nulo,         CDC,    valor 400

Eventos:
  discado:     c1 12/06 qtd 2; c1 13/06 (sáb -> 12/06) qtd 1; c2 10/06 qtd 1
  acionamento: c1 12/06; c3 12/06
  acordo:      c1 A1 12/06 valor 50; c3 A2 10/06 valor 70
  pago:        c1 12/06 (A1, data_acordo 12/06) valor 25
               c4 12/06 (A0, data_acordo 20/05 -> fora do mês) valor 10
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from etl.calendario import CalendarioUtil
from etl.config.loader import carregar_carteira
from etl.reports.base import ContextoRun
from etl.transform.indicadores import mapa_dias_uteis, preparar_eventos
from etl.transform.segmenter import aplicar_segmentacoes

DATA_REF = date(2026, 6, 12)
DATA_FIM = date(2026, 6, 14)
DIR_CARTEIRAS = "carteiras"


@pytest.fixture(scope="session")
def cfg_exemplo():
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    return carregar_carteira(raiz / DIR_CARTEIRAS, "exemplo_banco_x")


@pytest.fixture()
def cal():
    return CalendarioUtil()


@pytest.fixture()
def estoque_lf(cfg_exemplo):
    df = pl.DataFrame(
        {
            "id_cliente": [1, 2, 3, 4],
            "dias_atraso": [10, 90, 200, None],
            "produto": ["CARTAO", "CDC", "CARTAO", "CDC"],
            "valor": [100.0, 200.0, 300.0, 400.0],
        }
    )
    lf = aplicar_segmentacoes(df.lazy(), cfg_exemplo.segmentacoes)
    return lf.select("id_cliente", "seg_faixa_atraso", "seg_produto", "valor")


def _eventos_brutos() -> dict[str, pl.DataFrame]:
    return {
        "discado": pl.DataFrame(
            {
                "id_cliente": [1, 1, 2],
                "data_evento": [date(2026, 6, 12), date(2026, 6, 13), date(2026, 6, 10)],
                "qtd": [2, 1, 1],
            }
        ),
        "acionamento": pl.DataFrame(
            {
                "id_cliente": [1, 3],
                "data_evento": [date(2026, 6, 12), date(2026, 6, 12)],
                "qtd": [1, 1],
            }
        ),
        "acordo": pl.DataFrame(
            {
                "id_acordo": ["A1", "A2"],
                "id_cliente": [1, 3],
                "data_evento": [date(2026, 6, 12), date(2026, 6, 10)],
                "valor": [50.0, 70.0],
            }
        ),
        "pago": pl.DataFrame(
            {
                "id_cliente": [1, 4],
                "id_acordo": ["A1", "A0"],
                "id_parcela": [1, 9],
                "data_evento": [date(2026, 6, 12), date(2026, 6, 12)],
                "data_acordo": [date(2026, 6, 12), date(2026, 5, 20)],
                "valor": [25.0, 10.0],
            }
        ),
        # canais sem eventos no período
        "email": pl.DataFrame(
            schema={"id_cliente": pl.Int64, "data_evento": pl.Date, "qtd": pl.Int64}
        ),
        "sms": pl.DataFrame(
            schema={"id_cliente": pl.Int64, "data_evento": pl.Date, "qtd": pl.Int64}
        ),
        "whatsapp": pl.DataFrame(
            schema={"id_cliente": pl.Int64, "data_evento": pl.Date, "qtd": pl.Int64}
        ),
    }


@pytest.fixture()
def contexto(cfg_exemplo, cal, estoque_lf) -> ContextoRun:
    ids = estoque_lf.select("id_cliente").unique()
    mapa = mapa_dias_uteis(cal, DATA_REF.replace(day=1), DATA_FIM)
    eventos = {}
    for ind, df in _eventos_brutos().items():
        eventos[ind], _ = preparar_eventos(df.lazy(), mapa, ids)
    pago_acordo, _ = preparar_eventos(
        _eventos_brutos()["pago"].lazy(), mapa, ids, coluna_data="data_acordo"
    )
    return ContextoRun(
        cfg=cfg_exemplo,
        data_ref=DATA_REF,
        data_fim=DATA_FIM,
        cal=cal,
        estoque=estoque_lf,
        eventos=eventos,
        pago_por_data_acordo=pago_acordo,
    )
