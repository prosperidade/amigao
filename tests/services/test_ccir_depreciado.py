"""Fase 1 (N1 item 5) — Property.ccir DEPRECIADO: não-gravável, campo-chave
único vira Matricula.codigo_incra_sncr. Sem migração automática de dados
legados (só o caminho de escrita muda).
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
from app.services.intake_enrichment import _PROPERTY_KEY_MAP


def test_property_key_map_nao_grava_mais_ccir():
    """O mapa de auto-fill do intake não escreve mais em Property.ccir."""
    assert "ccir" not in _PROPERTY_KEY_MAP


def _seed(db_session, *, with_matricula_sncr: bool):
    tenant = Tenant(name="CCIR Depreciado Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(email="ccirdep@example.com", full_name="Consultor",
                hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email="ccirdep.c@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda", ccir=None)
    db_session.add(prop)
    db_session.flush()
    if with_matricula_sncr:
        db_session.add(Matricula(
            tenant_id=tenant.id, property_id=prop.id, numero_matricula="4698",
            codigo_incra_sncr="000.051.123.390-9",
        ))
    process = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                       title="Caso", process_type="car", status=ProcessStatus.triagem,
                       demand_type=DemandType.car)
    db_session.add(process)
    db_session.commit()
    return process, prop


class TestMissingCcirLacunaViaMatricula:
    def test_sem_sncr_em_nenhuma_matricula_gera_lacuna(self, db_session):
        process, prop = _seed(db_session, with_matricula_sncr=False)
        issues = validate_technical_consistency(process, prop, [], None)
        codigos = {i.code for i in issues}
        assert "MISSING_CCIR" in codigos
        missing = next(i for i in issues if i.code == "MISSING_CCIR")
        assert missing.field == "matricula.codigo_incra_sncr"

    def test_com_sncr_em_matricula_nao_gera_lacuna_mesmo_sem_property_ccir(self, db_session):
        """O sinal real agora é a Matricula, não mais Property.ccir (que fica
        None/congelado — sem migração automática)."""
        process, prop = _seed(db_session, with_matricula_sncr=True)
        assert prop.ccir is None  # confirma que não veio de lugar nenhum
        issues = validate_technical_consistency(process, prop, [], None)
        codigos = {i.code for i in issues}
        assert "MISSING_CCIR" not in codigos
