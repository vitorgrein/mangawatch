-- DISCADO (sistema): colunas obrigatórias id_cliente, data_evento; opcional qtd.
-- Sempre extraia o mês inteiro: BETWEEN :mes_ini AND :data_fim
-- (o motor acumula fim de semana/feriado no dia útil anterior automaticamente)
SELECT
    e.id_cliente,
    DATE(e.data_hora) AS data_evento,
    COUNT(*) AS qtd
FROM eventos_canal e
WHERE e.canal = 'discado'
  AND DATE(e.data_hora) BETWEEN :mes_ini AND :data_fim
GROUP BY e.id_cliente, DATE(e.data_hora)
