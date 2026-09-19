"""Recorte descartável de migrations; NÃO é gate autenticado nem prova de casos reais.

Usa exclusivamente o PostgreSQL temporário local na porta 25432. Tudo é rollback.
"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

ROOT = Path(__file__).resolve().parents[1]


def main():
    engine = sa.create_engine("postgresql+psycopg2://regente_test@127.0.0.1:25432/postgres")
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            assert conn.execute(sa.text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")).scalar() == 0
            for name in ("tenants", "processes", "users", "ai_jobs", "documents", "clients", "matriculas", "extracted_field_staging"):
                conn.execute(sa.text(f"CREATE TABLE {name}(id integer PRIMARY KEY, tenant_id integer, process_id integer)"))
                conn.execute(sa.text(f"INSERT INTO {name} VALUES (1,1,1),(2,2,2)"))
            context = MigrationContext.configure(conn)
            paths = [ROOT / "alembic/versions/069ce001_sprint_069_evidence_execution.py"]
            paths += sorted((ROOT / "alembic/versions").glob("071es*.py"))
            with Operations.context(context):
                for path in paths:
                    spec = importlib.util.spec_from_file_location(path.stem, path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.upgrade()
                    print(f"PASS upgrade {module.revision}")
            def rejected(sql):
                savepoint = conn.begin_nested()
                try:
                    conn.execute(sa.text(sql))
                    conn.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
                except sa.exc.DBAPIError:
                    savepoint.rollback()
                    return
                savepoint.rollback()
                raise AssertionError(f"invalid write accepted: {sql}")
            conn.execute(sa.text("""INSERT INTO evidence_versions
              (id,tenant_id,process_id,object_id,version,kind,content,content_hash,created_at)
              VALUES(1,1,1,'obs',1,'observacao','{"kind":"observacao","premises":[]}',repeat('a',64),now())"""))
            rejected("UPDATE evidence_versions SET agent_name='changed' WHERE id=1")
            rejected("DELETE FROM evidence_versions WHERE id=1")
            rejected("""INSERT INTO evidence_versions
              (id,tenant_id,process_id,object_id,version,kind,content,content_hash,created_at)
              VALUES(2,1,1,'bad',1,'conclusao','{"kind":"observacao"}',repeat('a',64),now())""")
            rejected("""INSERT INTO evidence_versions
              (id,tenant_id,process_id,object_id,version,kind,content,content_hash,created_at)
              VALUES(3,1,1,'risk',1,'conclusao',
              '{"kind":"conclusao","conclusion_class":"risco","applicability":"aplicavel","applicability_reason":"test","premises":[]}',
              repeat('a',64),now())""")
            rejected("""INSERT INTO evidence_versions
              (id,tenant_id,process_id,object_id,version,kind,content,content_hash,created_at)
              VALUES(4,1,1,'absence',1,'observacao',
              '{"kind":"observacao","knowledge":{"state":"ausencia_verificada_no_escopo"}}',repeat('a',64),now())""")
            rejected("INSERT INTO evidence_premissa VALUES (2,2,1,'obs',1,'premissa')")
            conn.execute(sa.text("""INSERT INTO documento_versao
              (id,tenant_id,documento_id,numero,sha256_original,texto,sha256_texto,metodo,parametros,origem)
              VALUES(1,1,1,1,repeat('a',64),'texto',repeat('b',64),'fixture','{}','teste')"""))
            rejected("UPDATE documento_versao SET texto='outro' WHERE id=1")
            rejected("""INSERT INTO fragmento(tenant_id,documento_versao_id,inicio,fim,trecho,sha256_texto)
              VALUES(2,1,0,1,'t',repeat('b',64))""")
            conn.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
            print("PASS 8 rejeições: versão/fragmento, tenant, premissa, risco, ausência e kind")
            for path in reversed(paths[1:]):
                spec = importlib.util.spec_from_file_location(path.stem, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                with Operations.context(context):
                    module.downgrade()
                print(f"PASS downgrade {module.revision}")
        finally:
            transaction.rollback()
            print("ROLLBACK: nenhuma tabela persistida")


if __name__ == "__main__":
    main()
