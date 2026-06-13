CREATE TABLE IF NOT EXISTS etl_controle_execucao (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY,
  carteira          VARCHAR(60),
  relatorio         VARCHAR(40),
  data_ref          DATE,
  inicio            DATETIME,
  fim               DATETIME,
  status            ENUM('EXECUTANDO','SUCESSO','ERRO','AVISO') NOT NULL,
  linhas_extraidas  BIGINT,
  linhas_carregadas BIGINT,
  mensagem          TEXT,
  arquivo_log       VARCHAR(255),
  hostname          VARCHAR(80),
  KEY ix_controle (carteira, relatorio, data_ref)
);
