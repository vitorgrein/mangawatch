-- ACORDOS: colunas obrigatórias id_cliente, data_evento, id_acordo; opcional valor.
-- {{ acordo_por }} vem do config.yml (geracao | vencimento) — um único template
-- atende as duas regras.
SELECT
    a.id_acordo,
    a.id_cliente,
    {% if acordo_por == 'vencimento' %}a.data_vencimento{% else %}a.data_geracao{% endif %} AS data_evento,
    a.valor
FROM acordos a
WHERE {% if acordo_por == 'vencimento' %}a.data_vencimento{% else %}a.data_geracao{% endif %}
      BETWEEN :mes_ini AND :data_fim
