-- E-MAIL (sistema): colunas obrigatórias id_cliente, data_evento; opcional qtd.
SELECT
    e.id_cliente,
    DATE(e.data_hora) AS data_evento,
    COUNT(*) AS qtd
FROM eventos_canal e
WHERE e.canal = 'email'
  AND DATE(e.data_hora) BETWEEN :mes_ini AND :data_fim
GROUP BY e.id_cliente, DATE(e.data_hora)
