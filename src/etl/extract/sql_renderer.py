"""Renderização das queries .sql das carteiras.

Duas camadas, por segurança e clareza:
- Jinja2 para fragmentos ESTRUTURAIS vindos do config validado:
  {{ base_ativa }}, {{ acordo_por }} e chaves de filtros.extras
- Bind params do SQLAlchemy para VALORES, sempre: :data_ref, :data_ini,
  :data_fim, :mes_ini
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, StrictUndefined, TemplateError

from etl.config.schema import CarteiraConfig

_env = Environment(undefined=StrictUndefined, autoescape=False)


class ErroSql(Exception):
    pass


def parametros_data(data_ref: date, data_fim: date) -> dict[str, date]:
    return {
        "data_ref": data_ref,
        "data_ini": data_ref,
        "data_fim": data_fim,
        "mes_ini": data_ref.replace(day=1),
    }


def renderizar(pasta_carteira: Path, cfg: CarteiraConfig, indicador: str) -> str:
    arquivo = pasta_carteira / "sql" / cfg.consultas[indicador]
    texto = arquivo.read_text(encoding="utf-8")
    contexto = {
        "base_ativa": cfg.filtros.base_ativa,
        "acordo_por": cfg.filtros.acordo_por,
        **cfg.filtros.extras,
    }
    try:
        return _env.from_string(texto).render(**contexto)
    except TemplateError as e:
        raise ErroSql(
            f"{arquivo}: erro ao renderizar template — {e}. "
            "Variáveis disponíveis: " + ", ".join(sorted(contexto))
        ) from e
