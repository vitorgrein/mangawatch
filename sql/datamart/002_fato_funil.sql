CREATE TABLE IF NOT EXISTS fato_funil (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  carteira            VARCHAR(60) NOT NULL,
  data_ref            DATE        NOT NULL,  -- foto acumulada do mês até este dia útil
  segmentacao         VARCHAR(40) NOT NULL,
  segmento            VARCHAR(80) NOT NULL,
  etapa_ordem         TINYINT     NOT NULL,
  etapa               VARCHAR(40) NOT NULL,  -- 'estoque', 'acionado_sistema', ...
  qtd_clientes        BIGINT      NOT NULL,
  pct_da_base         DECIMAL(9,6),
  pct_etapa_anterior  DECIMAL(9,6),
  cascata             VARCHAR(15) NOT NULL,  -- respeitar | nao_respeitar | forcar
  carregado_em        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_funil (carteira, data_ref, segmentacao, segmento, etapa),
  KEY ix_funil_pbi (data_ref, carteira, segmentacao)
);
