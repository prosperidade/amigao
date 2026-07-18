"""Forense caso Isis — requisito de matrícula reconhece a matrícula materializada.

"Matrícula do imóvel ausente" (MISSING_MATRICULA) checava só o escalar legado
`Property.registry_number`, cego às matrículas materializadas na consolidação
(`Matricula.numero_matricula`). Resultado: acusava "ausente" mesmo com o
documento de matrícula enviado e consolidado. O requisito agora reconhece a
matrícula pelo número.
"""

from __future__ import annotations

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.matricula import Matricula
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services.dossier import validate_technical_consistency


def _seed(db_session, *, com_matricula: bool, email="matdoc@example.com"):
    tenant = Tenant(name="MatriculaDoc Tenant")
    db_session.add(tenant)
    db_session.flush()
    db_session.add(User(email=email, full_name="Consultor",
                        hashed_password=get_password_hash("x12345"),
                        tenant_id=tenant.id, is_active=True))
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"c.{email}",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    # registry_number legado sempre None (a consolidação nunca o grava)
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda São Jorge",
                    registry_number=None)
    db_session.add(prop)
    db_session.flush()
    if com_matricula:
        db_session.add(Matricula(tenant_id=tenant.id, property_id=prop.id,
                                 numero_matricula="4698", area_ha=660.6561))
    process = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                      title="Caso", process_type="car", status=ProcessStatus.triagem,
                      demand_type=DemandType.car)
    db_session.add(process)
    db_session.commit()
    db_session.refresh(prop)
    return process, prop


def test_matricula_materializada_satisfaz_requisito(db_session):
    process, prop = _seed(db_session, com_matricula=True)
    codigos = {i.code for i in validate_technical_consistency(process, prop, [], None)}
    assert "MISSING_MATRICULA" not in codigos
    assert "CAR_NO_MATRICULA_DOC" not in codigos


def test_sem_matricula_e_sem_registry_number_acusa_ausente(db_session):
    process, prop = _seed(db_session, com_matricula=False, email="matdoc2@example.com")
    codigos = {i.code for i in validate_technical_consistency(process, prop, [], None)}
    assert "MISSING_MATRICULA" in codigos
