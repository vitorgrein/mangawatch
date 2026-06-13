"""Orquestra uma execução: carteira × data_ref × relatórios.

A extração é compartilhada entre os relatórios da mesma execução (daily e
funil leem os mesmos parquets de staging).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl
from sqlalchemy import Engine

from etl.calendario import CalendarioUtil
from etl.config.loader import ErroConfig, carregar_carteira
from etl.config.schema import CarteiraConfig
from etl.db.connection import obter_engine, testar_conexao
from etl.db.datamart import carregar_fato
from etl.extract import extractor, sql_renderer
from etl.quality.checks import ErroQualidade, checar_extracao
from etl.reports import REGISTRY
from etl.reports.base import ContextoRun
from etl.runlog import RegistroExecucao, configurar_log_arquivo, remover_log_arquivo
from etl.settings import Settings
from etl.transform.indicadores import COL_DATA, COL_ID, mapa_dias_uteis, preparar_eventos
from etl.transform.segmenter import aplicar_segmentacoes, colunas_segmento

log = logging.getLogger(__name__)


@dataclass
class ResultadoRelatorio:
    carteira: str
    relatorio: str
    data_ref: date
    status: str  # SUCESSO | AVISO | ERRO
    linhas_carregadas: int = 0
    mensagem: str = ""


def resolver_data_ref(cal: CalendarioUtil, data_ref: date | None) -> date:
    if data_ref is None:
        return cal.ultimo_dia_util()
    if not cal.e_dia_util(data_ref):
        raise ErroConfig(
            f"data_ref {data_ref} não é dia útil — eventos de fim de semana/feriado "
            f"acumulam no dia útil anterior ({cal.rolar_para_dia_util(data_ref)})"
        )
    return data_ref


def executar_carteira(
    settings: Settings,
    dir_carteiras: Path,
    nome: str,
    relatorios: list[str] | None,
    data_ref: date | None,
) -> list[ResultadoRelatorio]:
    cfg = carregar_carteira(dir_carteiras, nome)
    pasta_carteira = dir_carteiras / nome
    cal = CalendarioUtil(settings.calendario.feriados_extras)
    data_ref = resolver_data_ref(cal, data_ref)
    data_fim = cal.fim_janela(data_ref)

    pedidos = relatorios or cfg.relatorios
    a_executar = [r for r in pedidos if r in cfg.relatorios]
    ignorados = sorted(set(pedidos) - set(a_executar))
    if ignorados:
        log.info("Carteira %s não habilita: %s (pulando)", nome, ", ".join(ignorados))
    if not a_executar:
        return []
    for r in a_executar:
        if r not in REGISTRY:
            raise ErroConfig(f"relatório '{r}' não existe (disponíveis: {', '.join(REGISTRY)})")

    arquivo_log = configurar_log_arquivo(
        settings.dir_logs, nome, "+".join(a_executar), data_ref
    )
    engine_dm = obter_engine(settings.url_conexao(settings.datamart))
    testar_conexao(engine_dm)
    registros = {
        r: RegistroExecucao(engine_dm, nome, r, data_ref, arquivo_log) for r in a_executar
    }

    resultados: list[ResultadoRelatorio] = []
    try:
        ctx, linhas_extraidas, avisos = _extrair_e_preparar(
            settings, cfg, pasta_carteira, cal, data_ref, data_fim
        )
        total_extraido = sum(linhas_extraidas.values())
        for r in a_executar:
            spec = REGISTRY[r]
            log.info("Gerando relatório %s (carteira=%s data_ref=%s)", r, nome, data_ref)
            df = spec.gerar(ctx)
            carregadas = carregar_fato(engine_dm, spec.tabela, df, nome, data_ref)
            status = "AVISO" if avisos else "SUCESSO"
            registros[r].finalizar(
                status, total_extraido, carregadas, "\n".join(avisos) or None
            )
            resultados.append(
                ResultadoRelatorio(nome, r, data_ref, status, carregadas, "\n".join(avisos))
            )
    except Exception as e:
        for r, reg in registros.items():
            if not any(res.relatorio == r for res in resultados):
                reg.finalizar("ERRO", mensagem=str(e))
        raise
    finally:
        remover_log_arquivo(arquivo_log)
    return resultados


def _extrair_e_preparar(
    settings: Settings,
    cfg: CarteiraConfig,
    pasta_carteira: Path,
    cal: CalendarioUtil,
    data_ref: date,
    data_fim: date,
) -> tuple[ContextoRun, dict[str, int], list[str]]:
    engine = obter_engine(settings.url_conexao(cfg.conexao))
    testar_conexao(engine)
    staging = extractor.preparar_staging(
        settings.dir_staging, cfg.carteira, f"{data_ref:%Y-%m-%d}"
    )
    params = sql_renderer.parametros_data(data_ref, data_fim)

    linhas: dict[str, int] = {}
    for ind in cfg.indicadores_ativos:
        sql = sql_renderer.renderizar(pasta_carteira, cfg, ind)
        linhas[ind] = extractor.extrair_indicador(
            engine, sql, params, staging, ind, cfg.extracao.chunk_size
        )

    estoque = extractor.scan_indicador(staging, "estoque")
    _validar_colunas(estoque, "estoque", [COL_ID] + [s.coluna_origem for s in cfg.segmentacoes], cfg)
    estoque = aplicar_segmentacoes(estoque, cfg.segmentacoes)
    cols_estoque = [COL_ID, *colunas_segmento(cfg.segmentacoes)]
    if "valor" in estoque.collect_schema().names():
        cols_estoque.append("valor")
    estoque = estoque.select(cols_estoque)
    ids_estoque = estoque.select(COL_ID).unique()

    mapa = mapa_dias_uteis(cal, data_ref.replace(day=1), data_fim)
    eventos: dict[str, pl.LazyFrame] = {}
    fora_do_estoque: dict[str, int] = {}
    for ind in cfg.indicadores_ativos:
        if ind == "estoque":
            continue
        bruto = extractor.scan_indicador(staging, ind)
        _validar_colunas(bruto, ind, [COL_ID, COL_DATA], cfg)
        eventos[ind], fora_do_estoque[ind] = preparar_eventos(bruto, mapa, ids_estoque)

    pago_data_acordo = None
    precisa_pago_acordo = (
        "funil" in cfg.relatorios
        and cfg.funil.cascata == "respeitar"
        and "pago" in cfg.consultas
    )
    if precisa_pago_acordo:
        bruto = extractor.scan_indicador(staging, "pago")
        if "data_acordo" not in bruto.collect_schema().names():
            raise ErroConfig(
                f"carteira '{cfg.carteira}': funil.cascata = 'respeitar' exige que "
                "pagos.sql retorne a coluna 'data_acordo' (data de geração do acordo) "
                "— o pagamento é contado no dia em que o acordo foi gerado"
            )
        pago_data_acordo, _ = preparar_eventos(
            bruto, mapa, ids_estoque, coluna_data="data_acordo"
        )

    checks = checar_extracao(cfg, linhas, fora_do_estoque, estoque)
    erros = [c.mensagem for c in checks if c.nivel == "ERRO"]
    avisos = [c.mensagem for c in checks if c.nivel == "AVISO"]
    for a in avisos:
        log.warning("Qualidade: %s", a)
    if erros:
        raise ErroQualidade(
            f"carteira '{cfg.carteira}': qualidade reprovada:\n  - " + "\n  - ".join(erros)
        )

    ctx = ContextoRun(
        cfg=cfg,
        data_ref=data_ref,
        data_fim=data_fim,
        cal=cal,
        estoque=estoque,
        eventos=eventos,
        pago_por_data_acordo=pago_data_acordo,
        avisos=avisos,
    )
    return ctx, linhas, avisos


def _validar_colunas(
    lf: pl.LazyFrame, indicador: str, obrigatorias: list[str], cfg: CarteiraConfig
) -> None:
    existentes = set(lf.collect_schema().names())
    faltando = [c for c in obrigatorias if c not in existentes]
    if faltando:
        raise ErroConfig(
            f"carteira '{cfg.carteira}', indicador '{indicador}' "
            f"(sql/{cfg.consultas[indicador]}): a query não retornou as colunas "
            f"obrigatórias: {', '.join(faltando)}. Colunas retornadas: "
            + ", ".join(sorted(existentes))
        )
