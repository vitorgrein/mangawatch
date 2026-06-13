# Guia do Analista — BP-ETL

Como colocar uma carteira nova no processo unificado **sem escrever Python**:
você só escreve as queries MySQL e preenche um arquivo de configuração.

## Passo a passo

1. **Copie a pasta modelo** `carteiras/exemplo_banco_x/` e renomeie para o nome
   da sua carteira (ex.: `carteiras/banco_y/`). Use só letras minúsculas,
   números e `_`.
2. **Edite o `config.yml`** — todos os campos estão comentados no modelo:
   - `carteira`: igual ao nome da pasta
   - `conexao`: qual banco de origem usar (definidos em `settings.yml`)
   - `relatorios`: quais relatórios a carteira gera (`daily`, `funil`)
   - `filtros.base_ativa`: o pedaço de SQL que define a base ativa DA SUA carteira
   - `filtros.acordo_por`: `geracao` ou `vencimento`
   - `segmentacoes`: as aberturas da sua carteira (faixa de atraso, produto, ...)
   - `funil.cascata`: `respeitar`, `nao_respeitar` ou `forcar` (ver abaixo)
   - `funil.etapas`: a ordem do funil da sua carteira
3. **Escreva as queries** na pasta `sql/`. Há uma por indicador padrão:
   `estoque`, `discado`, `email`, `sms`, `whatsapp`, `acionamento`, `acordo`,
   `pago`. Se a carteira não tem um indicador (ex.: não dispara e-mail), basta
   remover a linha dele em `consultas:` no config.
4. **Valide**: `python -m etl validate --carteira banco_y` (use `--com-banco`
   para testar as queries no MySQL sem gravar nada).
5. **Rode**: `python -m etl run --carteira banco_y` — sem `--data-ref`, roda
   para o último dia útil.

## O contrato das queries

O motor faz todo o resto (acumulado, única, segmentação, funil, carga), mas as
queries precisam devolver colunas com estes nomes:

| Indicador | Colunas obrigatórias | Opcionais |
|---|---|---|
| estoque | `id_cliente` (1 linha por cliente) | `valor` (saldo), colunas das segmentações |
| discado/email/sms/whatsapp/acionamento | `id_cliente`, `data_evento` | `qtd` (default 1) |
| acordo | `id_cliente`, `data_evento`, `id_acordo` | `valor` |
| pago | `id_cliente`, `data_evento`, `id_acordo`, `id_parcela`, `data_acordo` | `valor` |

Regras importantes:

- **Período**: filtre sempre `BETWEEN :mes_ini AND :data_fim`. O motor precisa
  do mês inteiro para o funil; o daily ele recorta sozinho.
- **Fim de semana e feriado**: não trate na query — o motor acumula
  automaticamente no dia útil anterior.
- **Estoque manda**: eventos de clientes fora do estoque são descartados (com
  aviso no log). Todo indicador "só existe" se o cliente está no estoque.
- **Pré-agregue quando puder** (`GROUP BY id_cliente, DATE(...)`) — tabelas de
  discador são gigantes e isso reduz o tráfego.

### Variáveis e parâmetros disponíveis nos .sql

- `{{ base_ativa }}` — o filtro de base ativa do config
- `{{ acordo_por }}` — `geracao` ou `vencimento` (use com `{% if %}`, ver `acordos.sql`)
- chaves de `filtros.extras` — viram `{{ minha_chave }}`
- `:data_ref`, `:data_ini`, `:data_fim`, `:mes_ini` — datas calculadas pelo motor

## Os 3 modos de cascata do funil

- **respeitar** — o cliente só conta numa etapa se contou na anterior
  (ex.: só é acordo se foi acionado). O pagamento é contado no dia em que o
  acordo foi **gerado** (por isso o `pagos.sql` retorna `data_acordo`).
- **nao_respeitar** — cada etapa mostra seu total, independente das anteriores.
- **forcar** — se o cliente é positivo numa etapa mas não na anterior, a
  anterior "vira" positiva (um acordo sem CPC força o CPC).

Em todos os modos o **estoque é sempre respeitado**: nada conta fora dele.

## Onde os dados aparecem

- `fato_daily` — uma linha por carteira × dia útil × segmentação × segmento ×
  métrica (`qtd_<indicador>_unica`, `qtd_<indicador>_acum`, `valor_<indicador>`).
- `fato_funil` — foto do funil acumulado do mês até cada dia útil.
- `etl_controle_execucao` — status de cada execução (monitore no Power BI).

O Power BI conecta direto nessas tabelas; taxas e visão mensal são medidas DAX.

## Erros comuns

| Mensagem | Causa provável |
|---|---|
| `a query não retornou as colunas obrigatórias` | renomeie as colunas no SELECT (`AS id_cliente`, `AS data_evento`) |
| `estoque tem N id_cliente duplicado(s)` | o estoque deve ter 1 linha por cliente — agrupe |
| `indicador 'x' retornou 0 linhas` | período sem dados; se for normal, adicione em `qualidade.permitir_zero_linhas` |
| `funil.cascata = 'respeitar' exige ... data_acordo` | inclua a data de geração do acordo no `pagos.sql` |
| `data_ref ... não é dia útil` | rode para o dia útil anterior (o motor acumula o fds nele) |
