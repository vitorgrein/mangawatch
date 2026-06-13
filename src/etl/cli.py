"""CLI do BP-ETL.

Exemplos:
  python -m etl run --carteira exemplo_banco_x --relatorio daily --data-ref 2026-06-11
  python -m etl run --carteira todas
  python -m etl validate --carteira todas
  python -m etl list
  python -m etl init-datamart

Exit codes (para o Agendador de Tarefas):
  0 = sucesso | 1 = erro de configuração | 2 = erro de execução | 3 = sucesso com avisos
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer

from etl.calendario import CalendarioUtil
from etl.config.loader import ErroConfig, carregar_carteira, listar_carteiras
from etl.db.connection import obter_engine, testar_conexao
from etl.db.datamart import init_datamart
from etl.extract import sql_renderer
from etl.pipeline import executar_carteira, resolver_data_ref
from etl.quality.checks import ErroQualidade
from etl.settings import carregar_settings

app = typer.Typer(help="BP-ETL — processo unificado de relatórios de carteiras")

EXIT_OK, EXIT_CONFIG, EXIT_ERRO, EXIT_AVISO = 0, 1, 2, 3


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def _raiz() -> Path:
    return Path.cwd()


def _parse_data(valor: Optional[str]) -> Optional[date]:
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        typer.echo(f"ERRO: data inválida '{valor}' — use o formato YYYY-MM-DD", err=True)
        raise typer.Exit(EXIT_CONFIG)


def _nomes_carteiras(dir_carteiras: Path, carteira: str) -> list[str]:
    if carteira.lower() == "todas":
        nomes = listar_carteiras(dir_carteiras)
        if not nomes:
            typer.echo(f"ERRO: nenhuma carteira encontrada em {dir_carteiras}", err=True)
            raise typer.Exit(EXIT_CONFIG)
        return nomes
    return [carteira]


@app.command()
def run(
    carteira: str = typer.Option(..., help="Nome da carteira ou 'todas'"),
    relatorio: Optional[list[str]] = typer.Option(
        None, help="daily/funil (repetível). Padrão: todos habilitados no config"
    ),
    data_ref: Optional[str] = typer.Option(
        None, "--data-ref", help="YYYY-MM-DD (padrão: último dia útil)"
    ),
) -> None:
    """Executa extração + transformação + carga no datamart."""
    _setup_logging()
    settings = carregar_settings(_raiz())
    dir_carteiras = _raiz() / "carteiras"
    data = _parse_data(data_ref)

    pior = EXIT_OK
    for nome in _nomes_carteiras(dir_carteiras, carteira):
        try:
            resultados = executar_carteira(settings, dir_carteiras, nome, relatorio, data)
            for r in resultados:
                typer.echo(
                    f"[{r.status}] {r.carteira} {r.relatorio} {r.data_ref}: "
                    f"{r.linhas_carregadas} linhas no datamart"
                )
                if r.status == "AVISO":
                    pior = max(pior, EXIT_AVISO)
        except (ErroConfig, ErroQualidade) as e:
            typer.echo(f"[ERRO] {nome}: {e}", err=True)
            pior = max(pior, EXIT_CONFIG if isinstance(e, ErroConfig) else EXIT_ERRO)
        except Exception as e:  # noqa: BLE001 — uma carteira não derruba as demais
            logging.getLogger(__name__).exception("Falha na carteira %s", nome)
            typer.echo(f"[ERRO] {nome}: {e}", err=True)
            pior = max(pior, EXIT_ERRO)
    raise typer.Exit(pior)


@app.command()
def validate(
    carteira: str = typer.Option(..., help="Nome da carteira ou 'todas'"),
    com_banco: bool = typer.Option(
        False, "--com-banco", help="Também testa cada query no MySQL (LIMIT 0)"
    ),
) -> None:
    """Valida config.yml e renderiza as queries, sem gravar nada."""
    _setup_logging()
    settings = carregar_settings(_raiz())
    dir_carteiras = _raiz() / "carteiras"
    cal = CalendarioUtil(settings.calendario.feriados_extras)
    falhou = False

    for nome in _nomes_carteiras(dir_carteiras, carteira):
        try:
            cfg = carregar_carteira(dir_carteiras, nome)
            data = resolver_data_ref(cal, None)
            params = sql_renderer.parametros_data(data, cal.fim_janela(data))
            for ind in cfg.indicadores_ativos:
                sql = sql_renderer.renderizar(dir_carteiras / nome, cfg, ind)
                if com_banco:
                    from sqlalchemy import text

                    engine = obter_engine(settings.url_conexao(cfg.conexao))
                    testar_conexao(engine)
                    with engine.connect() as conn:
                        conn.execute(
                            text(f"SELECT * FROM ({sql}) AS _v LIMIT 0"), params
                        )
            typer.echo(f"[OK] {nome}: config e {len(cfg.indicadores_ativos)} queries válidas")
        except Exception as e:  # noqa: BLE001
            typer.echo(f"[ERRO] {nome}: {e}", err=True)
            falhou = True
    raise typer.Exit(EXIT_CONFIG if falhou else EXIT_OK)


@app.command(name="list")
def listar() -> None:
    """Lista as carteiras encontradas e seus relatórios habilitados."""
    dir_carteiras = _raiz() / "carteiras"
    for nome in listar_carteiras(dir_carteiras):
        try:
            cfg = carregar_carteira(dir_carteiras, nome)
            typer.echo(
                f"{nome}: relatorios={','.join(cfg.relatorios)} "
                f"cascata={cfg.funil.cascata} "
                f"segmentacoes={','.join(s.nome for s in cfg.segmentacoes) or '(nenhuma)'}"
            )
        except ErroConfig as e:
            typer.echo(f"{nome}: CONFIG INVÁLIDA — {e}")


@app.command(name="init-datamart")
def init_dm() -> None:
    """Cria as tabelas do datamart (fato_daily, fato_funil, etl_controle_execucao)."""
    _setup_logging()
    settings = carregar_settings(_raiz())
    engine = obter_engine(settings.url_conexao(settings.datamart))
    testar_conexao(engine)
    for nome in init_datamart(engine, _raiz() / "sql" / "datamart"):
        typer.echo(f"[OK] {nome}")


if __name__ == "__main__":
    app()
