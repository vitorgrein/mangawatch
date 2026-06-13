"""Ponta-a-ponta contra MySQL real (docker-compose.test.yml na porta 3307).

Roda a CLI como o analista rodaria, num sandbox que copia carteiras/ e sql/
do repositório, com chunk_size=2 para exercitar a extração em chunks.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
URL = "mysql+pymysql://root:testpass@127.0.0.1:3307/{db}?charset=utf8mb4"
DATA_REF = "2026-06-12"


def _mysql_disponivel() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 3307), timeout=2):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _mysql_disponivel(),
    reason="MySQL de teste fora do ar — suba com: "
    "docker compose -f tests/integration/docker-compose.test.yml up -d --wait",
)


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory) -> Path:
    raiz = tmp_path_factory.mktemp("projeto")
    shutil.copytree(RAIZ / "carteiras", raiz / "carteiras")
    shutil.copytree(RAIZ / "sql", raiz / "sql")
    (raiz / "settings.yml").write_text(
        f"""
conexoes:
  mysql_producao:
    url: "{URL.format(db='cobranca')}"
  mysql_datamart:
    url: "{URL.format(db='datamart')}"
datamart: mysql_datamart
caminhos: {{staging: staging, logs: logs}}
calendario: {{feriados_extras: []}}
""",
        encoding="utf-8",
    )
    config = raiz / "carteiras" / "exemplo_banco_x" / "config.yml"
    texto = config.read_text(encoding="utf-8")
    texto = texto.replace("chunk_size: 500000", "chunk_size: 2")
    texto = texto.replace(
        "base_ativa: \"c.status_contrato = 'ATIVO' AND c.dias_atraso BETWEEN 5 AND 360\"",
        "base_ativa: \"c.status_contrato = 'ATIVO'\"",
    )
    config.write_text(texto, encoding="utf-8")
    return raiz


def _cli(sandbox: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "etl", *args],
        cwd=sandbox,
        capture_output=True,
        text=True,
    )


def _query(db: str, sql: str) -> list[tuple]:
    from sqlalchemy import create_engine, text

    engine = create_engine(URL.format(db=db))
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql))]


@pytest.fixture(scope="module", autouse=True)
def datamart_pronto(sandbox):
    proc = _cli(sandbox, "init-datamart")
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_validate_com_banco(sandbox):
    proc = _cli(sandbox, "validate", "--carteira", "todas", "--com-banco")
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_run_daily_e_funil(sandbox):
    proc = _cli(
        sandbox, "run", "--carteira", "exemplo_banco_x", "--data-ref", DATA_REF
    )
    # exit 3: e-mail tem 0 linhas (permitido -> AVISO) e há segmento nulo no estoque
    assert proc.returncode == 3, proc.stderr + proc.stdout

    dict_metricas = {
        (m,): v
        for m, v in _query(
            "datamart",
            "SELECT metrica, valor FROM fato_daily "
            "WHERE carteira='exemplo_banco_x' AND data_ref='2026-06-12' "
            "AND segmentacao='total'",
        )
    }
    metrica = lambda m: float(dict_metricas[(m,)])  # noqa: E731
    assert metrica("qtd_estoque_unica") == 4
    assert metrica("valor_estoque") == 1000.0
    assert metrica("qtd_discado_unica") == 1
    assert metrica("qtd_discado_acum") == 3  # inclui o evento de sábado
    assert metrica("qtd_acionamento_unica") == 2
    assert metrica("qtd_acordo_unica") == 1
    assert metrica("valor_acordo") == 50.0
    assert metrica("qtd_pago_unica") == 2
    assert metrica("valor_pago") == 35.0
    assert metrica("qtd_email_unica") == 0

    funil = _query(
        "datamart",
        "SELECT etapa, qtd_clientes FROM fato_funil "
        "WHERE carteira='exemplo_banco_x' AND data_ref='2026-06-12' "
        "AND segmentacao='total' ORDER BY etapa_ordem",
    )
    assert funil == [
        ("estoque", 4),
        ("acionado_sistema", 2),
        ("acionamento", 1),
        ("acordo", 1),
        ("pago", 1),  # pago do c4 cai fora: acordo gerado em maio
    ]

    status = _query(
        "datamart",
        "SELECT DISTINCT status FROM etl_controle_execucao "
        "WHERE carteira='exemplo_banco_x' AND data_ref='2026-06-12'",
    )
    assert status == [("AVISO",)]


def test_extracao_em_chunks(sandbox):
    staging = sandbox / "staging" / "exemplo_banco_x" / DATA_REF
    # chunk_size=2 e 5 contratos ativos -> estoque em 3 parquets
    assert len(list(staging.glob("estoque_*.parquet"))) >= 2


def test_reexecucao_idempotente(sandbox):
    antes = _query("datamart", "SELECT COUNT(*) FROM fato_daily")[0][0]
    proc = _cli(
        sandbox, "run", "--carteira", "exemplo_banco_x", "--data-ref", DATA_REF
    )
    assert proc.returncode == 3, proc.stderr + proc.stdout
    depois = _query("datamart", "SELECT COUNT(*) FROM fato_daily")[0][0]
    assert antes == depois


def test_data_sem_eventos_gera_erro_de_qualidade(sandbox):
    # 01/07/2026 (qua): estoque existe mas nenhum indicador tem eventos -> ERRO
    proc = _cli(
        sandbox, "run", "--carteira", "exemplo_banco_x", "--data-ref", "2026-07-01"
    )
    assert proc.returncode == 2, proc.stderr + proc.stdout
    assert "0 linhas" in proc.stderr


def test_data_ref_em_fim_de_semana_e_rejeitada(sandbox):
    proc = _cli(
        sandbox, "run", "--carteira", "exemplo_banco_x", "--data-ref", "2026-06-13"
    )
    assert proc.returncode == 1, proc.stderr + proc.stdout
    assert "não é dia útil" in proc.stderr
