from datetime import date
from pathlib import Path

import pytest

from etl.config.loader import carregar_carteira
from etl.extract import sql_renderer

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def cfg():
    return carregar_carteira(RAIZ / "carteiras", "exemplo_banco_x")


def test_acordo_por_geracao(cfg):
    sql = sql_renderer.renderizar(RAIZ / "carteiras" / "exemplo_banco_x", cfg, "acordo")
    assert "data_geracao" in sql
    assert "data_vencimento" not in sql
    assert "{{" not in sql and "{%" not in sql


def test_acordo_por_vencimento(cfg):
    cfg2 = cfg.model_copy(deep=True)
    cfg2.filtros.acordo_por = "vencimento"
    sql = sql_renderer.renderizar(RAIZ / "carteiras" / "exemplo_banco_x", cfg2, "acordo")
    assert "data_vencimento" in sql


def test_base_ativa_injetada(cfg):
    sql = sql_renderer.renderizar(RAIZ / "carteiras" / "exemplo_banco_x", cfg, "estoque")
    assert cfg.filtros.base_ativa in sql


def test_variavel_inexistente_da_erro_amigavel(cfg, tmp_path):
    (tmp_path / "sql").mkdir()
    (tmp_path / "sql" / "estoque.sql").write_text("SELECT {{ nao_existe }}")
    with pytest.raises(sql_renderer.ErroSql, match="Variáveis disponíveis"):
        sql_renderer.renderizar(tmp_path, cfg, "estoque")


def test_parametros_data():
    params = sql_renderer.parametros_data(date(2026, 6, 12), date(2026, 6, 14))
    assert params == {
        "data_ref": date(2026, 6, 12),
        "data_ini": date(2026, 6, 12),
        "data_fim": date(2026, 6, 14),
        "mes_ini": date(2026, 6, 1),
    }
