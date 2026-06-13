# BP-ETL — Processo unificado de relatórios de carteiras

Um único processo Python gera os relatórios padrão (**daily** e **funil**) de
todas as carteiras e carrega o resultado agregado num **datamart MySQL**
consumido pelo Power BI. Cada analista contribui apenas com as queries MySQL e
um `config.yml` por carteira — filtros (base ativa, acordo por
geração/vencimento), segmentações e ordem do funil são todos configuráveis por
carteira. Veja o [Guia do Analista](docs/guia_do_analista.md).

## Arquitetura

```
carteiras/<nome>/config.yml + sql/*.sql        (por carteira, feito pelo analista)
        │
        ▼  python -m etl run
MySQL origem ──extração em chunks──► Parquet (staging) ──polars──► agregados
                                                                      │
                              fato_daily / fato_funil (datamart) ◄────┘
                                          │
                                       Power BI
```

- **Indicadores padrão**: estoque, discado, email, sms, whatsapp, acionamento
  (contato humano), acordo, pago. Por cliente: `_acum` (total de eventos) e
  `_unica` (1/0). Nada conta fora do estoque da carteira.
- **Dias úteis**: o processo roda para o último dia útil; eventos de fim de
  semana/feriado acumulam no dia útil anterior (feriados nacionais automáticos
  + extras em `settings.yml`).
- **Funil**: acumulado do mês até a data_ref, uma foto por dia útil, com 3
  modos de cascata (`respeitar` / `nao_respeitar` / `forcar`).
- **Volume**: extração em chunks + staging Parquet + agregação lazy (polars) —
  roda em servidor Windows comum, sem Spark.
- **Idempotente**: re-executar um dia substitui as linhas daquele dia.

## Instalação (servidor Windows)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env       :: e preencha as credenciais
```

Ajuste `settings.yml` (conexões, pastas de rede para staging/logs) e crie as
tabelas do datamart uma única vez:

```bat
python -m etl init-datamart
```

## Uso

```bat
python -m etl list                                       :: carteiras encontradas
python -m etl validate --carteira todas --com-banco      :: valida config + queries
python -m etl run --carteira banco_y --relatorio daily --data-ref 2026-06-12
python -m etl run --carteira todas                       :: tudo, último dia útil
```

Exit codes: `0` sucesso · `1` erro de configuração · `2` erro de execução ·
`3` sucesso com avisos de qualidade. Com `--carteira todas`, a falha de uma
carteira não interrompe as demais.

**Agendamento**: aponte o Agendador de Tarefas do Windows para `run_etl.bat`
("Executar estando o usuário conectado ou não"). Cada execução grava um log em
`logs/` e uma linha em `etl_controle_execucao` (monitorável no Power BI).

## Desenvolvimento e testes

```bash
pip install -e ".[dev]"
pytest tests/unit -q                  # sem banco

# ponta-a-ponta (precisa de Docker, só em dev — produção não usa Docker):
docker compose -f tests/integration/docker-compose.test.yml up -d --wait
pytest tests/integration -q
```

## Estrutura

```
src/etl/            motor (config, extração, transformação, relatórios, carga)
carteiras/          uma pasta por carteira (config.yml + sql/) — analista
sql/datamart/       DDL do datamart
docs/               guia do analista
tests/              unit (fixtures calculadas à mão) + integração (MySQL 8)
```

Um relatório novo = um módulo em `src/etl/reports/` registrado com
`@registrar("nome", tabela="fato_nome")`; as carteiras aderem via `relatorios:`
no config.
