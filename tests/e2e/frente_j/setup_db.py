"""Gate E2E da Frente J — banco DESCARTÁVEL + seed mínimo (ELODI sintética).

Nunca toca `amigao_db` nem produção: o nome do banco tem de começar com
`amigao_e2e` (assert antes de qualquer DDL) e o schema é aplicado por
`Base.metadata.create_all` — mesmo caminho do `tests/conftest.py` — não por
`alembic upgrade` (CLAUDE.md reserva o comando ao banco de desenvolvimento).

Uso (PowerShell/Bash, na raiz do repo, com o Postgres do compose de pé):

    E2E_PG_HOST=127.0.0.1 E2E_PG_PORT=15432 E2E_PG_USER=postgres \
    E2E_PG_PASSWORD=... E2E_DB_NAME=amigao_e2e_frente_j \
    python tests/e2e/frente_j/setup_db.py

Imprime, em JSON, os ids e as credenciais que `gate_api.py` e o spec do
Playwright consomem. Idempotente: DROP + CREATE do banco a cada execução.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

HOST = os.environ.get("E2E_PG_HOST", "127.0.0.1")
PORT = os.environ.get("E2E_PG_PORT", "15432")
USER = os.environ.get("E2E_PG_USER", "postgres")
PASSWORD = os.environ.get("E2E_PG_PASSWORD", "")
DB_NAME = os.environ.get("E2E_DB_NAME", "amigao_e2e_frente_j")

E2E_EMAIL = os.environ.get("E2E_EMAIL", "e2e.frentej@example.com")
E2E_PASSWORD = os.environ.get("E2E_PASSWORD", "E2e-FrenteJ-2026!")

assert DB_NAME.startswith("amigao_e2e"), f"banco alvo inválido para o gate: {DB_NAME!r}"

# O `settings` é singleton lido do ambiente NA IMPORTAÇÃO — apontar antes.
os.environ["POSTGRES_SERVER"] = HOST
os.environ["POSTGRES_PORT"] = PORT
os.environ["POSTGRES_USER"] = USER
os.environ["POSTGRES_PASSWORD"] = PASSWORD
os.environ["POSTGRES_DB"] = DB_NAME
os.environ.setdefault("SECRET_KEY", "e2e-frente-j-secret-key-with-32-chars-min")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "Dy0Ny3uX57eV-TJv9ljrK0Vw0tzObWbI_aUekAHgMzQ=")

sys.path.insert(0, os.getcwd())

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models as _registry  # noqa: E402,F401 — registra todos os models
from app.core.security import get_password_hash  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.client import Client, ClientStatus, ClientType  # noqa: E402
from app.models.process import DemandType, Process, ProcessStatus  # noqa: E402
from app.models.property import Property  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User  # noqa: E402


def _admin_url(db: str) -> str:
    return f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{db}"


def main() -> None:
    print(f"[setup] alvo: host={HOST} port={PORT} user={USER} db={DB_NAME}", file=sys.stderr)
    admin = create_engine(_admin_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
    admin.dispose()

    engine = create_engine(_admin_url(DB_NAME), pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)

    # Seed do catálogo regulatório — em produção vem da migration; aqui, como
    # no conftest, é inserido à mão porque `create_all` não roda seed.
    from app.models.regulatory_catalog_seed import seed_rows_as_dicts  # noqa: PLC0415

    rows = seed_rows_as_dicts()
    if rows:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO regulatory_issue_catalog
                      (codigo_alerta, familia, descricao_curta, factibilidade,
                       severity_base, muda_rota_regulatoria, muda_escopo_preco_prazo,
                       documentos_cruzados_default)
                    VALUES
                      (:codigo_alerta, :familia, :descricao_curta, :factibilidade,
                       :severity_base, :muda_rota_regulatoria, :muda_escopo_preco_prazo,
                       CAST(:documentos_cruzados_default AS jsonb))
                    ON CONFLICT (codigo_alerta) DO NOTHING
                    """
                ),
                [{**r, "documentos_cruzados_default": json.dumps(r["documentos_cruzados_default"])} for r in rows],
            )

    # Templates de checklist documental — em produção vêm da migration
    # `a1b2c3d4e5f6_sprint1_intake` (INSERT no upgrade), que `create_all` não
    # roda. Sem eles, "Gerar Checklist" na tela produz um checklist VAZIO
    # ("0 de 0 documentos recebidos") e o gate mede uma tela que não é a de
    # produção. Só o `car` — é a demanda do caso da ELODI; a fonte de verdade
    # continua sendo a migration.
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO checklist_templates
                  (demand_type, name, description, items, is_active)
                VALUES ('car', 'Checklist CAR',
                        'Documentos necessários para regularização do CAR',
                        CAST(:items AS json), true)
                """
            ),
            {"items": json.dumps([
                {"id": "car_numero", "label": "Número do CAR", "doc_type": "car",
                 "category": "ambiental", "required": True},
                {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula",
                 "category": "fundiario", "required": True},
                {"id": "ccir", "label": "CCIR", "doc_type": "ccir",
                 "category": "fundiario", "required": True},
                {"id": "documento_proprietario", "label": "Documento do Proprietário (RG/CPF)",
                 "doc_type": "doc_pessoal", "category": "pessoal", "required": True},
                {"id": "caf", "label": "CAF (Cadastro Agricultor Familiar)", "doc_type": "caf",
                 "category": "fundiario", "required": False},
                {"id": "mapa_imovel", "label": "Mapa/Shapefile do Imóvel", "doc_type": "mapa",
                 "category": "geoespacial", "required": False},
                {"id": "laudo_anterior", "label": "Laudo Ambiental Anterior", "doc_type": "laudo",
                 "category": "ambiental", "required": False},
            ])},
        )

    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        tenant = Tenant(name="E2E Frente J — Regente")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id, email=E2E_EMAIL, full_name="Consultora E2E",
            hashed_password=get_password_hash(E2E_PASSWORD), is_active=True, is_superuser=True,
        )
        db.add(user)
        db.flush()
        cli = Client(
            tenant_id=tenant.id, full_name="ELODI AGROPECUÁRIA", email="elodi.e2e@example.com",
            client_type=ClientType.pj, status=ClientStatus.active, cpf_cnpj="29.091.958/0001-17",
        )
        db.add(cli)
        db.flush()
        prop = Property(
            tenant_id=tenant.id, client_id=cli.id,
            name="Fazenda Retiro dos Olhos d'Água, Posse ou Porcos e Novo Horizonte II",
            municipality="Alto Paraíso de Goiás", state="GO",
        )
        db.add(prop)
        db.flush()
        proc = Process(
            tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
            title="ELODI — regularização (gate E2E Frente J)", process_type="car",
            status=ProcessStatus.triagem, demand_type=DemandType.car,
            opened_at=datetime(2026, 9, 8, 0, 0, tzinfo=UTC),
        )
        db.add(proc)
        db.commit()
        saida = {
            "db_name": DB_NAME, "tenant_id": tenant.id, "user_id": user.id,
            "email": E2E_EMAIL, "password": E2E_PASSWORD,
            "client_id": cli.id, "property_id": prop.id, "process_id": proc.id,
        }
    finally:
        db.close()
        engine.dispose()
    print(json.dumps(saida, ensure_ascii=False))


if __name__ == "__main__":
    main()
