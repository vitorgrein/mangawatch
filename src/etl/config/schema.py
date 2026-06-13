"""Schema (pydantic) do config.yml de cada carteira.

Indicadores padrão do processo: estoque, discado, email, sms, whatsapp,
acionamento (contato humano), acordo, pago. Cada um tem uma query .sql própria.
Todo indicador só conta se o cliente consta no ESTOQUE da carteira.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

INDICADORES = [
    "estoque",
    "discado",
    "email",
    "sms",
    "whatsapp",
    "acionamento",
    "acordo",
    "pago",
]

# Indicadores cujas queries podem retornar coluna `valor` (gera métrica valor_*)
INDICADORES_COM_VALOR = {"estoque", "acordo", "pago"}

Indicador = Literal[
    "estoque", "discado", "email", "sms", "whatsapp", "acionamento", "acordo", "pago"
]

ModoCascata = Literal["respeitar", "nao_respeitar", "forcar"]


class Faixa(BaseModel):
    ate: float | None = None  # limite superior inclusivo; None = faixa aberta (última)
    rotulo: str


class Segmentacao(BaseModel):
    nome: str
    tipo: Literal["coluna", "faixas"]
    coluna_origem: str
    faixas: list[Faixa] | None = None

    @model_validator(mode="after")
    def _validar_faixas(self) -> "Segmentacao":
        if self.tipo == "faixas":
            if not self.faixas:
                raise ValueError(
                    f"segmentação '{self.nome}': tipo 'faixas' exige a lista 'faixas'"
                )
            abertas = [f for f in self.faixas if f.ate is None]
            if len(abertas) != 1 or self.faixas[-1].ate is not None:
                raise ValueError(
                    f"segmentação '{self.nome}': a última faixa (e somente ela) "
                    "deve ser aberta (sem 'ate')"
                )
            limites = [f.ate for f in self.faixas[:-1]]
            if limites != sorted(limites):
                raise ValueError(
                    f"segmentação '{self.nome}': faixas devem estar em ordem crescente de 'ate'"
                )
        return self


class EtapaFunil(BaseModel):
    nome: str
    indicadores: list[Indicador]


class ConfigFunil(BaseModel):
    cascata: ModoCascata = "respeitar"
    etapas: list[EtapaFunil] = Field(
        default_factory=lambda: [
            EtapaFunil(nome="estoque", indicadores=["estoque"]),
            EtapaFunil(
                nome="acionado_sistema",
                indicadores=["discado", "email", "sms", "whatsapp"],
            ),
            EtapaFunil(nome="acionamento", indicadores=["acionamento"]),
            EtapaFunil(nome="acordo", indicadores=["acordo"]),
            EtapaFunil(nome="pago", indicadores=["pago"]),
        ]
    )

    @model_validator(mode="after")
    def _validar_etapas(self) -> "ConfigFunil":
        if not self.etapas:
            raise ValueError("funil: lista 'etapas' não pode ser vazia")
        primeira = self.etapas[0]
        if primeira.indicadores != ["estoque"]:
            raise ValueError(
                "funil: a primeira etapa deve ser exatamente o estoque "
                "(indicadores: [estoque]) — o estoque sempre abre a cascata"
            )
        vistos: set[str] = set()
        for etapa in self.etapas:
            for ind in etapa.indicadores:
                if ind in vistos:
                    raise ValueError(
                        f"funil: indicador '{ind}' aparece em mais de uma etapa"
                    )
                vistos.add(ind)
        return self


class Filtros(BaseModel):
    base_ativa: str = "1=1"
    acordo_por: Literal["vencimento", "geracao"] = "geracao"
    extras: dict[str, str] = Field(default_factory=dict)


class ConfigExtracao(BaseModel):
    chunk_size: int = Field(default=500_000, gt=0)


class ConfigQualidade(BaseModel):
    permitir_zero_linhas: list[Indicador] = Field(default_factory=list)
    max_pct_segmento_nulo: float = Field(default=5.0, ge=0, le=100)


class CarteiraConfig(BaseModel):
    carteira: str
    nome_exibicao: str
    conexao: str
    relatorios: list[Literal["daily", "funil"]]
    filtros: Filtros = Filtros()
    consultas: dict[Indicador, str]
    segmentacoes: list[Segmentacao] = Field(default_factory=list)
    funil: ConfigFunil = ConfigFunil()
    extracao: ConfigExtracao = ConfigExtracao()
    qualidade: ConfigQualidade = ConfigQualidade()

    @field_validator("relatorios")
    @classmethod
    def _relatorios_nao_vazio(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("lista 'relatorios' não pode ser vazia")
        return v

    @model_validator(mode="after")
    def _validar(self) -> "CarteiraConfig":
        if "estoque" not in self.consultas:
            raise ValueError(
                "consultas: o indicador 'estoque' é obrigatório — ele define a base "
                "da carteira e nenhum outro indicador conta fora dele"
            )
        if "funil" in self.relatorios:
            faltando = [
                ind
                for etapa in self.funil.etapas
                for ind in etapa.indicadores
                if ind not in self.consultas
            ]
            if faltando:
                raise ValueError(
                    "funil: indicadores sem query em 'consultas': "
                    + ", ".join(sorted(set(faltando)))
                )
        nomes = [s.nome for s in self.segmentacoes]
        if len(nomes) != len(set(nomes)):
            raise ValueError("segmentacoes: nomes duplicados")
        if "total" in nomes:
            raise ValueError(
                "segmentacoes: o nome 'total' é reservado (visão total é automática)"
            )
        return self

    @property
    def indicadores_ativos(self) -> list[str]:
        """Indicadores com query configurada, na ordem padrão."""
        return [i for i in INDICADORES if i in self.consultas]
