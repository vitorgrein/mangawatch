-- ESTOQUE: uma linha por cliente da carteira (foto em :data_ref).
-- Colunas obrigatórias: id_cliente
-- Opcionais: valor (saldo devedor -> métrica valor_estoque)
--            + toda coluna_origem usada nas segmentações do config.yml
-- Variáveis: {{ base_ativa }} | Parâmetros: :data_ref
SELECT
    c.id_cliente,
    c.dias_atraso,
    c.produto,
    c.valor_divida AS valor
FROM contratos c
WHERE {{ base_ativa }}
