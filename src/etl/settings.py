"""Carrega settings.yml + .env (configuração global, não por carteira)."""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

_ENV_VAR = re.compile(r"\$\{(\w+)\}")


class Caminhos(BaseModel):
    staging: Path = Path("staging")
    logs: Path = Path("logs")


class Calendario(BaseModel):
    feriados_extras: list[date] = Field(default_factory=list)


class Conexao(BaseModel):
    url: str


class Settings(BaseModel):
    conexoes: dict[str, Conexao]
    datamart: str
    caminhos: Caminhos = Caminhos()
    calendario: Calendario = Calendario()
    raiz: Path = Path(".")

    def url_conexao(self, nome: str) -> str:
        if nome not in self.conexoes:
            disponiveis = ", ".join(sorted(self.conexoes))
            raise KeyError(
                f"Conexão '{nome}' não existe em settings.yml (disponíveis: {disponiveis})"
            )
        return _interpolar_env(self.conexoes[nome].url)

    @property
    def dir_staging(self) -> Path:
        return self._abs(self.caminhos.staging)

    @property
    def dir_logs(self) -> Path:
        return self._abs(self.caminhos.logs)

    def _abs(self, p: Path) -> Path:
        return p if p.is_absolute() else self.raiz / p


def _interpolar_env(texto: str) -> str:
    def sub(m: re.Match) -> str:
        valor = os.environ.get(m.group(1))
        if valor is None:
            raise KeyError(
                f"Variável de ambiente '{m.group(1)}' não definida — preencha o arquivo .env"
            )
        return valor

    return _ENV_VAR.sub(sub, texto)


def carregar_settings(raiz: Path | None = None) -> Settings:
    raiz = Path(raiz) if raiz else Path.cwd()
    load_dotenv(raiz / ".env")
    arquivo = raiz / "settings.yml"
    if not arquivo.exists():
        raise FileNotFoundError(f"settings.yml não encontrado em {raiz}")
    dados = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    return Settings(**dados, raiz=raiz)
