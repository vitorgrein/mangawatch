"""Fábrica de engines SQLAlchemy com retry (conexões corporativas caem)."""

from __future__ import annotations

import logging

from sqlalchemy import Engine, create_engine, text
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}


def obter_engine(url: str) -> Engine:
    if url not in _engines:
        _engines[url] = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
    return _engines[url]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
    before_sleep=lambda rs: log.warning(
        "Falha ao conectar (tentativa %s): %s", rs.attempt_number, rs.outcome.exception()
    ),
)
def testar_conexao(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
