"""Log de execução: arquivo por run + tabela etl_controle_execucao no datamart."""

from __future__ import annotations

import logging
import socket
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Engine, text

log = logging.getLogger(__name__)


def configurar_log_arquivo(dir_logs: Path, carteira: str, relatorio: str, data_ref: date) -> Path:
    dir_logs.mkdir(parents=True, exist_ok=True)
    arquivo = dir_logs / (
        f"{carteira}_{relatorio}_{data_ref:%Y%m%d}_{datetime.now():%Y%m%d_%H%M%S}.log"
    )
    handler = logging.FileHandler(arquivo, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler.set_name(str(arquivo))
    logging.getLogger().addHandler(handler)
    return arquivo


def remover_log_arquivo(arquivo: Path) -> None:
    raiz = logging.getLogger()
    for h in list(raiz.handlers):
        if h.get_name() == str(arquivo):
            raiz.removeHandler(h)
            h.close()


class RegistroExecucao:
    """Linha em etl_controle_execucao: criada no início, atualizada no fim."""

    def __init__(
        self, engine: Engine, carteira: str, relatorio: str, data_ref: date, arquivo_log: Path
    ) -> None:
        self.engine = engine
        self.inicio = datetime.now()
        with engine.begin() as conn:
            self.id = conn.execute(
                text(
                    "INSERT INTO etl_controle_execucao "
                    "(carteira, relatorio, data_ref, inicio, status, arquivo_log, hostname) "
                    "VALUES (:c, :r, :d, :i, 'EXECUTANDO', :a, :h)"
                ),
                {
                    "c": carteira,
                    "r": relatorio,
                    "d": data_ref,
                    "i": self.inicio,
                    "a": str(arquivo_log),
                    "h": socket.gethostname(),
                },
            ).lastrowid

    def finalizar(
        self,
        status: str,
        linhas_extraidas: int | None = None,
        linhas_carregadas: int | None = None,
        mensagem: str | None = None,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE etl_controle_execucao SET fim = :f, status = :s, "
                    "linhas_extraidas = :le, linhas_carregadas = :lc, mensagem = :m "
                    "WHERE id = :id"
                ),
                {
                    "f": datetime.now(),
                    "s": status,
                    "le": linhas_extraidas,
                    "lc": linhas_carregadas,
                    "m": (mensagem or "")[:60000] or None,
                    "id": self.id,
                },
            )
