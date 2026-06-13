-- ACIONAMENTO (contato humano com o cliente):
-- colunas obrigatórias id_cliente, data_evento; opcional qtd.
SELECT
    a.id_cliente,
    DATE(a.data_hora) AS data_evento,
    COUNT(*) AS qtd
FROM acionamentos_humanos a
WHERE DATE(a.data_hora) BETWEEN :mes_ini AND :data_fim
GROUP BY a.id_cliente, DATE(a.data_hora)
