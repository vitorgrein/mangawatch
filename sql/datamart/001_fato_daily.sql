CREATE TABLE IF NOT EXISTS fato_daily (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  carteira      VARCHAR(60)   NOT NULL,
  data_ref      DATE          NOT NULL,
  segmentacao   VARCHAR(40)   NOT NULL,  -- 'total', 'faixa_atraso', 'produto', ...
  segmento      VARCHAR(80)   NOT NULL,  -- 'total', '31-90', 'CARTAO', ...
  metrica       VARCHAR(60)   NOT NULL,  -- 'qtd_acordo_unica', 'valor_pago', ...
  valor         DECIMAL(18,4) NOT NULL,
  carregado_em  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_daily (carteira, data_ref, segmentacao, segmento, metrica),
  KEY ix_daily_pbi (data_ref, carteira, segmentacao)
);
