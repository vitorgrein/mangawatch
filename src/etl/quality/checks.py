"""Checks de qualidade dos dados extraídos.

ERRO aborta a carga da carteira; AVISO segue, mas marca a execução (exit 3).
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from etl.config.schema import CarteiraConfig
from etl.transform.indicadores import COL_ID


@dataclass(frozen=True)
class Resultado:
    nivel: str  # 'ERRO' | 'AVISO'
    mensagem: str


class ErroQualidade(Exception):
    pass


def checar_extracao(
    cfg: CarteiraConfig,
    linhas_por_indicador: dict[str, int],
    fora_do_estoque: dict[str, int],
    estoque: pl.LazyFrame,
) -> list[Resultado]:
    resultados: list[Resultado] = []

    if linhas_por_indicador.get("estoque", 0) == 0:
        resultados.append(
            Resultado("ERRO", "estoque retornou 0 linhas — nada a processar")
        )
        return resultados  # sem estoque, os demais checks não fazem sentido

    duplicados = (
        estoque.group_by(COL_ID).len().filter(pl.col("len") > 1).select(pl.len())
        .collect().item()
    )
    if duplicados:
        resultados.append(
            Resultado(
                "ERRO",
                f"estoque tem {duplicados} id_cliente duplicado(s) — a query de "
                "estoque deve retornar uma linha por cliente",
            )
        )

    for ind, linhas in linhas_por_indicador.items():
        if ind != "estoque" and linhas == 0:
            nivel = (
                "AVISO" if ind in cfg.qualidade.permitir_zero_linhas else "ERRO"
            )
            sufixo = (
                "" if nivel == "AVISO"
                else " (se for esperado, adicione em qualidade.permitir_zero_linhas)"
            )
            resultados.append(
                Resultado(nivel, f"indicador '{ind}' retornou 0 linhas{sufixo}")
            )

    for ind, qtd in fora_do_estoque.items():
        if qtd:
            resultados.append(
                Resultado(
                    "AVISO",
                    f"indicador '{ind}': {qtd} evento(s) de clientes fora do "
                    "estoque foram descartados",
                )
            )

    total_estoque = estoque.select(pl.len()).collect().item()
    for seg in cfg.segmentacoes:
        nulos = (
            estoque.filter(pl.col(f"seg_{seg.nome}").is_null())
            .select(pl.len()).collect().item()
        )
        pct = 100 * nulos / total_estoque
        if pct > cfg.qualidade.max_pct_segmento_nulo:
            resultados.append(
                Resultado(
                    "AVISO",
                    f"segmentação '{seg.nome}': {pct:.1f}% do estoque sem valor "
                    f"(limite {cfg.qualidade.max_pct_segmento_nulo}%)",
                )
            )
    return resultados
