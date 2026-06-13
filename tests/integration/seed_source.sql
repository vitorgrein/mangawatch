-- Fontes fake (mesmo cenário calculado à mão de tests/conftest.py) + datamart vazio.
CREATE DATABASE cobranca;
CREATE DATABASE datamart;
USE cobranca;

CREATE TABLE contratos (
  id_cliente      BIGINT PRIMARY KEY,
  status_contrato VARCHAR(20),
  produto         VARCHAR(20),
  dias_atraso     INT,
  valor_divida    DECIMAL(12,2)
);
INSERT INTO contratos VALUES
  (1, 'ATIVO',   'CARTAO', 10,   100),
  (2, 'ATIVO',   'CDC',    90,   200),
  (3, 'ATIVO',   'CARTAO', 200,  300),
  (4, 'ATIVO',   'CDC',    NULL, 400),
  (5, 'QUITADO', 'CDC',    0,    0);     -- fora da base ativa

CREATE TABLE eventos_canal (
  id_evento  BIGINT AUTO_INCREMENT PRIMARY KEY,
  id_cliente BIGINT,
  canal      VARCHAR(20),
  data_hora  DATETIME
);
INSERT INTO eventos_canal (id_cliente, canal, data_hora) VALUES
  (1, 'discado',  '2026-06-12 09:00:00'),
  (1, 'discado',  '2026-06-12 15:00:00'),
  (1, 'discado',  '2026-06-13 10:00:00'),  -- sábado: acumula na sexta 12/06
  (2, 'discado',  '2026-06-10 11:00:00'),
  (2, 'sms',      '2026-06-10 12:00:00'),
  (1, 'whatsapp', '2026-06-12 13:00:00'),
  (5, 'discado',  '2026-06-12 09:30:00');  -- cliente fora do estoque: descartado

CREATE TABLE acionamentos_humanos (
  id_acionamento BIGINT AUTO_INCREMENT PRIMARY KEY,
  id_cliente     BIGINT,
  data_hora      DATETIME
);
INSERT INTO acionamentos_humanos (id_cliente, data_hora) VALUES
  (1, '2026-06-12 10:00:00'),
  (3, '2026-06-12 11:00:00');

CREATE TABLE acordos (
  id_acordo       VARCHAR(20) PRIMARY KEY,
  id_cliente      BIGINT,
  data_geracao    DATE,
  data_vencimento DATE,
  valor           DECIMAL(12,2)
);
INSERT INTO acordos VALUES
  ('A1', 1, '2026-06-12', '2026-06-20', 50),
  ('A2', 3, '2026-06-10', '2026-06-25', 70),
  ('A0', 4, '2026-05-20', '2026-05-30', 90);  -- acordo de maio pago em junho

CREATE TABLE pagamentos (
  id_pagamento   BIGINT AUTO_INCREMENT PRIMARY KEY,
  id_cliente     BIGINT,
  id_acordo      VARCHAR(20),
  id_parcela     INT,
  data_pagamento DATE,
  valor          DECIMAL(12,2)
);
INSERT INTO pagamentos (id_cliente, id_acordo, id_parcela, data_pagamento, valor) VALUES
  (1, 'A1', 1, '2026-06-12', 25),
  (4, 'A0', 9, '2026-06-12', 10);
