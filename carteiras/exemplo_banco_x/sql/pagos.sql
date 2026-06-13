-- PAGOS: colunas obrigatórias id_cliente, data_evento (data do pagamento),
-- id_acordo, id_parcela, data_acordo (data de GERAÇÃO do acordo); opcional valor.
-- data_acordo é usada no funil com cascata 'respeitar': o pagamento é contado
-- no dia em que o acordo foi gerado.
SELECT
    p.id_cliente,
    p.id_acordo,
    p.id_parcela,
    p.data_pagamento AS data_evento,
    a.data_geracao   AS data_acordo,
    p.valor
FROM pagamentos p
JOIN acordos a ON a.id_acordo = p.id_acordo
WHERE p.data_pagamento BETWEEN :mes_ini AND :data_fim
