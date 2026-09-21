"""Prova de persistência com material SINTÉTICO; não é o gate dos textos reais.

Somente PostgreSQL descartável localhost:25432. Todas as alterações são rollback.
"""
import hashlib
import importlib.util
import os
from pathlib import Path

from cryptography.fernet import Fernet

os.environ.setdefault("SECRET_KEY", "incremento2-synthetic-local-validation-only")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.models.document import Document
from app.models.entrada_semantica import AtoRegistral, Espolio, Participacao, Pessoa
from app.models.evidence import EvidenceVersion
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.schemas.entrada_semantica import EntradaExtraida
from app.services.entrada_semantica import persistir_entrada

ROOT = Path(__file__).resolve().parents[1]


def main():
    engine = sa.create_engine("postgresql+psycopg2://regente_test@127.0.0.1:25432/postgres")
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            assert conn.execute(sa.text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")).scalar() == 0
            for name in ("tenants", "processes", "users", "ai_jobs", "clients", "properties", "intake_drafts", "matriculas"):
                conn.execute(sa.text(f"CREATE TABLE {name}(id integer PRIMARY KEY, tenant_id integer, process_id integer)"))
                conn.execute(sa.text(f"INSERT INTO {name} VALUES(1,1,1),(2,2,2)"))
            Document.__table__.create(conn)
            context = MigrationContext.configure(conn)
            paths = [ROOT / "alembic/versions/069ce001_sprint_069_evidence_execution.py"]
            paths += sorted((ROOT / "alembic/versions").glob("071es*.py"))
            with Operations.context(context):
                for index, path in enumerate(paths):
                    spec = importlib.util.spec_from_file_location(path.stem, path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.upgrade()
                    if index == 0:
                        ExtractedFieldStaging.__table__.create(conn)
                        conn.execute(sa.text("ALTER TABLE extracted_field_staging DROP COLUMN observacao_ref"))
            db = Session(bind=conn)

            def documento(identifier, texto, tipo):
                row = Document(id=identifier, tenant_id=1, process_id=1, original_file_name=f"sintetico-{identifier}.txt",
                    filename=f"sintetico-{identifier}.txt", content_type="text/plain", storage_key=f"sintetico/{identifier}",
                    document_type=tipo, extracted_text=texto, checksum_sha256=hashlib.sha256(texto.encode()).hexdigest())
                db.add(row)
                db.flush()
                return row

            for identifier, numero in ((547, "3.181"), (548, "3.313"), (549, "3.673"), (550, "4.387")):
                texto = f"CERTIDÃO DE INTEIRO TEOR\nCartório sintético CNS TESTE\nMatrícula {numero}\nR.1 compra e venda de teste"
                doc = documento(identifier, texto, "matricula")
                entrada = EntradaExtraida.model_validate({"atos": [{"rotulo": "R.1", "matricula": numero,
                    "serventia": "Cartório sintético", "cns": "TESTE", "especie": "registro",
                    "natureza": "compra_venda", "ordem": 1, "trecho": "R.1 compra e venda de teste"}]})
                persistir_entrada(db, doc, entrada)
                persistir_entrada(db, doc, entrada)
            assert db.query(AtoRegistral).count() == 4
            assert db.query(EvidenceVersion).filter_by(kind="observacao").count() == 4
            print("PASS quatro matrículas; duas execuções não duplicam atos/observações")

            texto = ("CONTRATO DE SERVIÇOS\nPessoa Sintética — TITULAR FALECIDO\n"
                "ESPÓLIO de Pessoa Sintética, inventário controle-sintetico\n"
                "Representante Sintético, inventariante, OAB/GO TESTE")
            entrada = EntradaExtraida.model_validate({"partes": [
                {"chave": "falecido", "nome": "Pessoa Sintética", "natureza": "pf",
                 "trecho": "Pessoa Sintética — TITULAR FALECIDO"},
                {"chave": "espolio", "nome": "Espólio de Pessoa Sintética", "natureza": "espolio",
                 "falecido_chave": "falecido", "inventario": "controle-sintetico",
                 "trecho": "ESPÓLIO de Pessoa Sintética, inventário controle-sintetico"},
                {"chave": "representante", "nome": "Representante Sintético", "natureza": "pf",
                 "tipo_identificador": "oab", "identificador": "OAB/GO TESTE",
                 "trecho": "Representante Sintético, inventariante, OAB/GO TESTE"}],
                "participacoes": [{"parte_chave": "representante", "papel": "inventariante",
                    "representado_chave": "espolio", "trecho": "Representante Sintético, inventariante, OAB/GO TESTE"}]})
            for identifier in (700, 701):
                doc = documento(identifier, texto, "contrato")
                persistir_entrada(db, doc, entrada)
                persistir_entrada(db, doc, entrada)
            assert db.query(Espolio).count() == 2
            assert db.query(Pessoa).count() == 4
            assert db.query(Participacao).count() == 2
            assert all(row.estado_confirmacao == "declarado" for row in db.query(Participacao))
            assert all(row.inventario == "controle-sintetico" for row in db.query(Espolio))
            assert db.query(EvidenceVersion).filter_by(kind="observacao").count() == 12
            db.flush()
            conn.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
            print("PASS espólio/óbito/inventariante declarado persistidos; duas fontes idênticas preservadas")
            db.close()
        finally:
            transaction.rollback()
            print("ROLLBACK: nenhuma tabela persistida")


if __name__ == "__main__":
    main()
