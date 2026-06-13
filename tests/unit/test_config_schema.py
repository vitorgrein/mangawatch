import pytest
from pydantic import ValidationError

from etl.config.schema import CarteiraConfig, ConfigFunil, EtapaFunil, Segmentacao


def _base(**extra):
    dados = {
        "carteira": "x",
        "nome_exibicao": "X",
        "conexao": "c",
        "relatorios": ["daily"],
        "consultas": {"estoque": "estoque.sql"},
    }
    dados.update(extra)
    return dados


def test_config_minimo_valido():
    cfg = CarteiraConfig(**_base())
    assert cfg.indicadores_ativos == ["estoque"]
    assert cfg.funil.cascata == "respeitar"  # default


def test_estoque_obrigatorio():
    with pytest.raises(ValidationError, match="estoque"):
        CarteiraConfig(**_base(consultas={"discado": "d.sql"}))


def test_funil_exige_queries_das_etapas():
    with pytest.raises(ValidationError, match="indicadores sem query"):
        CarteiraConfig(**_base(relatorios=["funil"]))


def test_funil_primeira_etapa_deve_ser_estoque():
    with pytest.raises(ValidationError, match="primeira etapa"):
        ConfigFunil(
            cascata="respeitar",
            etapas=[EtapaFunil(nome="acordo", indicadores=["acordo"])],
        )


def test_funil_indicador_duplicado_entre_etapas():
    with pytest.raises(ValidationError, match="mais de uma etapa"):
        ConfigFunil(
            etapas=[
                EtapaFunil(nome="estoque", indicadores=["estoque"]),
                EtapaFunil(nome="a", indicadores=["sms"]),
                EtapaFunil(nome="b", indicadores=["sms"]),
            ]
        )


def test_faixas_em_ordem_crescente():
    with pytest.raises(ValidationError, match="ordem crescente"):
        Segmentacao(
            nome="s",
            tipo="faixas",
            coluna_origem="x",
            faixas=[{"ate": 90, "rotulo": "a"}, {"ate": 30, "rotulo": "b"}, {"rotulo": "c"}],
        )


def test_ultima_faixa_deve_ser_aberta():
    with pytest.raises(ValidationError, match="aberta"):
        Segmentacao(
            nome="s",
            tipo="faixas",
            coluna_origem="x",
            faixas=[{"ate": 30, "rotulo": "a"}, {"ate": 90, "rotulo": "b"}],
        )


def test_acordo_por_valores_validos():
    with pytest.raises(ValidationError):
        CarteiraConfig(**_base(filtros={"acordo_por": "vencimentos"}))


def test_nome_total_reservado():
    with pytest.raises(ValidationError, match="reservado"):
        CarteiraConfig(
            **_base(
                segmentacoes=[{"nome": "total", "tipo": "coluna", "coluna_origem": "x"}]
            )
        )
