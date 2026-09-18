-- Prova do ADR-070 §2/§14: FK sobre coluna gerada + as três invariantes no banco.
-- Roda em schema descartável; não é migration. Uso:
--   psql -v ON_ERROR_STOP=1 -f adr070_prova_constraints.sql
-- Cada caso roda numa subtransação, força as checagens adiadas com
-- SET CONSTRAINTS ALL IMMEDIATE e é desfeito; o resultado é comparado ao esperado.
\set ON_ERROR_STOP on
SET client_min_messages = warning;
DROP SCHEMA IF EXISTS prova_adr070 CASCADE;
CREATE SCHEMA prova_adr070;
SET search_path = prova_adr070;

CREATE TABLE tenants (id int PRIMARY KEY);
INSERT INTO tenants VALUES (1), (2);

-- Simplificação: o rota_passos real chega ao processo via rotas.process_id.
CREATE TABLE rota_passos (
  id int PRIMARY KEY, tenant_id int NOT NULL, process_id int NOT NULL,
  status text NOT NULL, deleted_at timestamptz,
  UNIQUE (tenant_id, id)
);

CREATE TABLE evidence_versions (
  id bigserial PRIMARY KEY,
  tenant_id int NOT NULL REFERENCES tenants(id),
  process_id int NOT NULL,
  object_id text NOT NULL,
  version int NOT NULL,
  kind text NOT NULL,                       -- coluna comum, como já existe em produção
  content jsonb NOT NULL,
  origin text GENERATED ALWAYS AS (content->>'origin') STORED,
  knowledge_state text GENERATED ALWAYS AS (content->'knowledge'->>'state') STORED,
  conclusion_class text GENERATED ALWAYS AS (content->>'conclusion_class') STORED,
  applicability_reason text GENERATED ALWAYS AS (content->>'applicability_reason') STORED,
  consulta_object_id text GENERATED ALWAYS AS (content->'knowledge'->'verification'->'source'->>'id') STORED,
  consulta_version int GENERATED ALWAYS AS ((content->'knowledge'->'verification'->'source'->>'version')::int) STORED,
  finalidade text GENERATED ALWAYS AS (content->>'finalidade') STORED,
  rota_passo_id int GENERATED ALWAYS AS ((content->>'rota_passo_id')::int) STORED,
  UNIQUE (tenant_id, process_id, object_id, version),
  CONSTRAINT kind_valido CHECK (kind IN ('fonte_primaria', 'observacao', 'derivacao', 'conclusao')),
  CONSTRAINT kind_igual_conteudo CHECK (kind = content->>'kind'),
  CONSTRAINT ausencia_exige_consulta CHECK (
    knowledge_state IS DISTINCT FROM 'ausencia_verificada_no_escopo' OR consulta_object_id IS NOT NULL),
  CONSTRAINT risco_exige_justificativa CHECK (
    conclusion_class IS DISTINCT FROM 'risco' OR nullif(btrim(applicability_reason), '') IS NOT NULL),
  CONSTRAINT escopo_exige_finalidade_e_passo CHECK (
    conclusion_class IS DISTINCT FROM 'escopo_proposto'
    OR (nullif(btrim(finalidade), '') IS NOT NULL AND rota_passo_id IS NOT NULL)),
  -- FK composta sobre colunas GERADAS: mesma consultoria e mesmo caso
  CONSTRAINT consulta_mesmo_caso FOREIGN KEY (tenant_id, process_id, consulta_object_id, consulta_version)
    REFERENCES evidence_versions (tenant_id, process_id, object_id, version) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT passo_mesmo_tenant FOREIGN KEY (tenant_id, rota_passo_id)
    REFERENCES rota_passos (tenant_id, id)
);

CREATE TABLE evidence_premissa (
  tenant_id int NOT NULL, process_id int NOT NULL,
  dependente_id bigint NOT NULL REFERENCES evidence_versions(id),
  premissa_object_id text NOT NULL, premissa_version int NOT NULL,
  PRIMARY KEY (dependente_id, premissa_object_id, premissa_version),
  FOREIGN KEY (tenant_id, process_id, premissa_object_id, premissa_version)
    REFERENCES evidence_versions (tenant_id, process_id, object_id, version) DEFERRABLE INITIALLY DEFERRED
);

CREATE FUNCTION rejeitar_mutacao() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'append-only: % em %', TG_OP, TG_TABLE_NAME USING ERRCODE = 'P0001'; END $$;
CREATE TRIGGER ev_imutavel BEFORE UPDATE OR DELETE ON evidence_versions
  FOR EACH ROW EXECUTE FUNCTION rejeitar_mutacao();
CREATE TRIGGER premissa_imutavel BEFORE UPDATE OR DELETE ON evidence_premissa
  FOR EACH ROW EXECUTE FUNCTION rejeitar_mutacao();

-- Aresta materializada a partir do conteúdo: uma escrita canônica.
CREATE FUNCTION materializar_premissas() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO evidence_premissa
  SELECT NEW.tenant_id, NEW.process_id, NEW.id, p->>'id', (p->>'version')::int
  FROM jsonb_array_elements(coalesce(NEW.content->'premises', '[]'::jsonb)) AS p;
  RETURN NULL;
END $$;
CREATE TRIGGER ev_premissas AFTER INSERT ON evidence_versions
  FOR EACH ROW EXECUTE FUNCTION materializar_premissas();

-- Invariante 1, parte que a FK não alcança: a referida é consulta primária.
CREATE FUNCTION exigir_consulta_primaria() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM evidence_versions e
   WHERE e.tenant_id = NEW.tenant_id AND e.process_id = NEW.process_id
     AND e.object_id = NEW.consulta_object_id AND e.version = NEW.consulta_version
     AND e.kind = 'fonte_primaria' AND e.origin = 'consulta';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'ausência verificada exige consulta primária preservada' USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER ausencia_consulta_primaria AFTER INSERT ON evidence_versions
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
  WHEN (NEW.consulta_object_id IS NOT NULL) EXECUTE FUNCTION exigir_consulta_primaria();

-- Invariante 2, parte agregada. Dois caminhos (decisão do André, 17/09):
-- conclusão fato_documental OU observação. Aprovação/aceite é gate de consumo.
CREATE FUNCTION exigir_premissa_de_fato() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM evidence_premissa p
    JOIN evidence_versions e ON e.tenant_id = p.tenant_id AND e.process_id = p.process_id
     AND e.object_id = p.premissa_object_id AND e.version = p.premissa_version
    WHERE p.dependente_id = NEW.id
      AND (e.conclusion_class = 'fato_documental' OR e.kind = 'observacao')) THEN
    RAISE EXCEPTION 'risco exige premissa fato_documental ou observação' USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER risco_exige_premissa_de_fato AFTER INSERT ON evidence_versions
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
  WHEN (NEW.conclusion_class = 'risco') EXECUTE FUNCTION exigir_premissa_de_fato();

-- Invariante 3, parte mutável: passo validado, não removido, mesmo caso — no insert.
-- AFTER, não BEFORE: trigger BEFORE não enxerga coluna gerada (achado desta prova).
CREATE FUNCTION exigir_passo_validado() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM rota_passos r
   WHERE r.id = NEW.rota_passo_id AND r.tenant_id = NEW.tenant_id AND r.process_id = NEW.process_id
     AND r.status = 'validado' AND r.deleted_at IS NULL;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'escopo proposto exige passo de rota validado no mesmo caso' USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER escopo_passo_validado AFTER INSERT ON evidence_versions
  NOT DEFERRABLE FOR EACH ROW
  WHEN (NEW.rota_passo_id IS NOT NULL) EXECUTE FUNCTION exigir_passo_validado();

INSERT INTO rota_passos VALUES (1, 1, 10, 'validado', NULL), (2, 1, 10, 'proposto', NULL),
                               (3, 2, 20, 'validado', NULL), (4, 1, 10, 'validado', now());

-- Harness: executa, força checagens adiadas, desfaz sempre; devolve 'aceito' ou o SQLSTATE.
CREATE FUNCTION caso(stmts text) RETURNS text LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE stmts;
    SET CONSTRAINTS ALL IMMEDIATE;
    RAISE EXCEPTION USING ERRCODE = 'ZZ999', MESSAGE = 'sentinela';
  EXCEPTION WHEN OTHERS THEN
    SET CONSTRAINTS ALL DEFERRED;
    IF SQLSTATE = 'ZZ999' THEN RETURN 'aceito'; END IF;
    RETURN 'rejeitado ' || SQLSTATE;
  END;
END $$;

CREATE FUNCTION ev(t int, p int, oid text, content text) RETURNS text LANGUAGE sql AS $$
  SELECT format('INSERT INTO evidence_versions (tenant_id, process_id, object_id, version, kind, content) '
                'VALUES (%s, %s, %L, 1, %L, %L::jsonb);', t, p, oid, (content::jsonb)->>'kind', content)
$$;

CREATE TABLE resultado (n int, caso text, esperado text, obtido text);

-- Blocos de conteúdo reutilizados
\set consulta  '{"kind":"fonte_primaria","origin":"consulta"}'
\set documento '{"kind":"fonte_primaria","origin":"documento"}'
\set ausencia  '{"kind":"observacao","origin":"extrator","knowledge":{"state":"ausencia_verificada_no_escopo","verification":{"source":{"id":"consulta:1","version":1}}}}'

INSERT INTO resultado VALUES
 (1, 'ausência com consulta primária no mesmo caso', 'aceito',
    caso(ev(1,10,'consulta:1',:'consulta') || ev(1,10,'obs:1',:'ausencia'))),
 (2, 'ausência sem consulta_ref', 'rejeitado 23514',
    caso(ev(1,10,'obs:2','{"kind":"observacao","origin":"extrator","knowledge":{"state":"ausencia_verificada_no_escopo"}}'))),
 (3, 'ausência apontando consulta inexistente', 'rejeitado 23503',
    caso(ev(1,10,'obs:3',:'ausencia'))),
 (4, 'ausência apontando consulta de OUTRA consultoria', 'rejeitado 23503',
    caso(ev(2,10,'consulta:1',:'consulta') || ev(1,10,'obs:4',:'ausencia'))),
 (5, 'ausência apontando fonte que não é consulta', 'rejeitado 23514',
    caso(ev(1,10,'consulta:1',:'documento') || ev(1,10,'obs:5',:'ausencia'))),
 (6, 'risco com conclusão fato_documental e justificativa', 'aceito',
    caso(ev(1,10,'fato:1','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"fato_documental"}')
      || ev(1,10,'risco:1','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"risco","applicability_reason":"art. X aplica","premises":[{"id":"fato:1","version":1}]}'))),
 (7, 'risco com observação como premissa (2º caminho)', 'aceito',
    caso(ev(1,10,'obs:7','{"kind":"observacao","origin":"extrator"}')
      || ev(1,10,'risco:7','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"risco","applicability_reason":"art. X aplica","premises":[{"id":"obs:7","version":1}]}'))),
 (8, 'risco sem justificativa de aplicabilidade', 'rejeitado 23514',
    caso(ev(1,10,'obs:8','{"kind":"observacao","origin":"extrator"}')
      || ev(1,10,'risco:8','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"risco","applicability_reason":" ","premises":[{"id":"obs:8","version":1}]}'))),
 (9, 'risco só com derivação como premissa', 'rejeitado 23514',
    caso(ev(1,10,'der:9','{"kind":"derivacao","origin":"matriz"}')
      || ev(1,10,'risco:9','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"risco","applicability_reason":"art. X aplica","premises":[{"id":"der:9","version":1}]}'))),
 -- 10: o trigger de risco dispara antes da FK da aresta; qualquer dos dois rejeita. O 22 isola a FK.
 (10, 'risco com premissa inexistente', 'rejeitado',
    caso(ev(1,10,'risco:10','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"risco","applicability_reason":"art. X aplica","premises":[{"id":"fantasma","version":1}]}'))),
 (11, 'UPDATE em versão gravada', 'rejeitado P0001',
    caso(ev(1,10,'obs:11','{"kind":"observacao","origin":"extrator"}')
      || 'UPDATE evidence_versions SET content = content || ''{"x":1}'' WHERE object_id = ''obs:11'';')),
 (12, 'DELETE em versão gravada', 'rejeitado P0001',
    caso(ev(1,10,'obs:12','{"kind":"observacao","origin":"extrator"}')
      || 'DELETE FROM evidence_versions WHERE object_id = ''obs:12'';')),
 (13, 'escopo com finalidade e passo validado', 'aceito',
    caso(ev(1,10,'esc:13','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"escopo_proposto","finalidade":"retificar CAR","rota_passo_id":1}'))),
 (14, 'escopo sem finalidade', 'rejeitado 23514',
    caso(ev(1,10,'esc:14','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"escopo_proposto","rota_passo_id":1}'))),
 (15, 'escopo com passo apenas proposto', 'rejeitado 23514',
    caso(ev(1,10,'esc:15','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"escopo_proposto","finalidade":"retificar CAR","rota_passo_id":2}'))),
 (16, 'escopo com passo de OUTRA consultoria', 'rejeitado 23503',
    caso(ev(1,10,'esc:16','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"escopo_proposto","finalidade":"retificar CAR","rota_passo_id":3}'))),
 (17, 'escopo com passo removido (soft-delete)', 'rejeitado 23514',
    caso(ev(1,10,'esc:17','{"kind":"conclusao","origin":"diagnostico","conclusion_class":"escopo_proposto","finalidade":"retificar CAR","rota_passo_id":4}'))),
 (18, 'kind da coluna diferente do conteúdo', 'rejeitado 23514',
    caso('INSERT INTO evidence_versions (tenant_id, process_id, object_id, version, kind, content) '
         'VALUES (1, 10, ''x:18'', 1, ''conclusao'', ''{"kind":"observacao","origin":"extrator"}'');')),
 (19, 'FK com ON UPDATE CASCADE sobre coluna gerada (restrição documentada)', 'rejeitado',
    caso('CREATE TABLE t19 (a int PRIMARY KEY); CREATE TABLE t19b (j jsonb, g int GENERATED ALWAYS AS ((j->>''a'')::int) STORED '
         'REFERENCES t19(a) ON UPDATE CASCADE);')),
 (21, 'trigger BEFORE com WHEN sobre coluna gerada (restrição do PostgreSQL)', 'rejeitado',
    caso('CREATE TRIGGER t21 BEFORE INSERT ON evidence_versions FOR EACH ROW '
         'WHEN (NEW.rota_passo_id IS NOT NULL) EXECUTE FUNCTION exigir_passo_validado();')),
 (22, 'observação com premissa inexistente (FK da aresta isolada)', 'rejeitado 23503',
    caso(ev(1,10,'obs:22','{"kind":"observacao","origin":"extrator","premises":[{"id":"fantasma","version":1}]}'))),
 (23, 'observação com premissa de OUTRO caso', 'rejeitado 23503',
    caso(ev(1,99,'obs:23a','{"kind":"observacao","origin":"extrator"}')
      || ev(1,10,'obs:23','{"kind":"observacao","origin":"extrator","premises":[{"id":"obs:23a","version":1}]}'))),
 (20, 'ADD COLUMN gerada STORED em tabela com linhas', 'aceito',
    caso(ev(1,10,'obs:20','{"kind":"observacao","origin":"extrator","predicate":"area"}')
      || 'SET CONSTRAINTS ALL IMMEDIATE; ALTER TABLE evidence_versions ADD COLUMN predicate text GENERATED ALWAYS AS (content->>''predicate'') STORED;'));

SELECT n, caso, esperado, obtido,
       CASE WHEN obtido = esperado OR (esperado = 'rejeitado' AND obtido LIKE 'rejeitado%') THEN 'PASS' ELSE 'FAIL' END AS veredito
FROM resultado ORDER BY n;
SELECT current_setting('server_version') AS servidor,
       count(*) FILTER (WHERE obtido = esperado OR (esperado = 'rejeitado' AND obtido LIKE 'rejeitado%')) AS pass,
       count(*) AS total
FROM resultado;
DROP SCHEMA prova_adr070 CASCADE;
