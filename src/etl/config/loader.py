"""Descobre as pastas de carteiras, valida config.yml e traduz erros para o analista."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from etl.config.schema import CarteiraConfig


class ErroConfig(Exception):
    """Erro de configuração com mensagem amigável para o analista."""


def listar_carteiras(dir_carteiras: Path) -> list[str]:
    if not dir_carteiras.exists():
        raise ErroConfig(f"Pasta de carteiras não encontrada: {dir_carteiras}")
    return sorted(
        p.name for p in dir_carteiras.iterdir() if (p / "config.yml").exists()
    )


def carregar_carteira(dir_carteiras: Path, nome: str) -> CarteiraConfig:
    pasta = dir_carteiras / nome
    arquivo = pasta / "config.yml"
    if not arquivo.exists():
        existentes = ", ".join(listar_carteiras(dir_carteiras)) or "(nenhuma)"
        raise ErroConfig(
            f"Carteira '{nome}' não encontrada: falta {arquivo}. "
            f"Carteiras existentes: {existentes}"
        )
    try:
        dados = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ErroConfig(f"{arquivo}: YAML inválido — {e}") from e
    if not isinstance(dados, dict):
        raise ErroConfig(f"{arquivo}: o arquivo deve conter um mapeamento YAML")

    try:
        cfg = CarteiraConfig(**dados)
    except ValidationError as e:
        raise ErroConfig(_traduzir_erros(arquivo, e)) from e

    if cfg.carteira != nome:
        raise ErroConfig(
            f"{arquivo}: campo 'carteira' ('{cfg.carteira}') deve ser igual ao "
            f"nome da pasta ('{nome}')"
        )
    _validar_arquivos_sql(pasta, cfg)
    return cfg


def _validar_arquivos_sql(pasta: Path, cfg: CarteiraConfig) -> None:
    faltando = [
        f"{indicador} -> sql/{arquivo}"
        for indicador, arquivo in cfg.consultas.items()
        if not (pasta / "sql" / arquivo).exists()
    ]
    if faltando:
        raise ErroConfig(
            f"{pasta / 'config.yml'}: arquivos .sql não encontrados na pasta sql/:\n  "
            + "\n  ".join(faltando)
        )


def _traduzir_erros(arquivo: Path, e: ValidationError) -> str:
    linhas = [f"{arquivo}: configuração inválida:"]
    for erro in e.errors():
        campo = ".".join(str(p) for p in erro["loc"]) or "(raiz)"
        msg = erro["msg"]
        if erro["type"] == "missing":
            msg = "campo obrigatório ausente"
        elif erro["type"] == "literal_error":
            msg = f"valor inválido — opções: {erro.get('ctx', {}).get('expected', '')}"
        linhas.append(f"  - campo '{campo}': {msg}")
    return "\n".join(linhas)
