"""Cascata + lineage dentro da consolidação real (caso 15).

Prova, contra o BD, que os dois buracos do caso 15 fecharam no fluxo de verdade:

* o NIRF do ITR (que chega SEM `matricula_hint`, porque o ITR não declara número
  de matrícula) encontra dono pela cascata e é gravado;
* a matrícula materializada nasce com certidão de nascimento (`lineage`).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.matricula import Matricula
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.staging_consolidation import consolidate_process

_SEQ = {"n": 0}


def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Integr {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"int{n}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Sao Jorge")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, prop, cli


def _doc(db_session, tenant, proc, doc_type):
    _SEQ["n"] += 1
    d = Document(tenant_id=tenant.id, process_id=proc.id,
                 original_file_name="d.pdf", filename="d.pdf",
                 content_type="application/pdf",
                 storage_key=f"int/{tenant.id}/{_SEQ['n']}",
                 document_type=doc_type, ocr_status=OcrStatus.done)
    db_session.add(d)
    db_session.flush()
    return d


def _aceito(db_session, tenant, proc, doc, campo, valor, alvo, *, hint=None, tipo=None):
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name=campo, field_value={"value": valor},
        status=ExtractedFieldStatus.aceito, decided_value={"value": valor},
        decided_at=datetime.now(UTC),
        target_entity="matricula", target_field=alvo,
        matricula_hint=hint, source_doc_type=tipo or doc.document_type,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_nirf_do_itr_encontra_dono_pela_cascata(db_session):
    """O buraco do caso 15: ITR sem hint → aceite sem destino.

    Agora a cascata ancora pelo INCRA (degrau 2) e o NIRF é gravado.
    """
    tenant, proc, prop, cli = _seed(db_session)

    # A matrícula já existe (veio da certidão), com o INCRA preenchido.
    cert = _doc(db_session, tenant, proc, "matricula")
    _aceito(db_session, tenant, proc, cert, "numero_matricula", "6776",
            "numero_matricula", hint="6776")
    _aceito(db_session, tenant, proc, cert, "codigo_sncr_incra", "951.048.549.371-0",
            "codigo_incra_sncr", hint="6776")

    # O ITR chega SEM hint — como no caso real.
    itr = _doc(db_session, tenant, proc, "itr")
    _aceito(db_session, tenant, proc, itr, "codigo_incra", "951048.549371-0",
            "codigo_incra_sncr", hint=None)
    _aceito(db_session, tenant, proc, itr, "nirf_cib", "9.153.765-7",
            "nirf_cib", hint=None)
    db_session.commit()

    consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id, user_id=None)

    db_session.expire_all()
    mat = (
        db_session.query(Matricula)
        .filter(Matricula.property_id == prop.id, Matricula.numero_matricula == "6776")
        .first()
    )
    assert mat is not None
    assert mat.nirf_cib == "9.153.765-7", "o NIRF do ITR chegou à matrícula"


def test_matricula_nasce_com_lineage(db_session):
    """Certidão de nascimento: de qual staging/decisão o registro veio."""
    tenant, proc, prop, cli = _seed(db_session)
    cert = _doc(db_session, tenant, proc, "matricula")
    _aceito(db_session, tenant, proc, cert, "numero_matricula", "4698",
            "numero_matricula", hint="4698")
    db_session.commit()

    consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id, user_id=None)

    db_session.expire_all()
    mat = (
        db_session.query(Matricula)
        .filter(Matricula.property_id == prop.id, Matricula.numero_matricula == "4698")
        .first()
    )
    assert mat is not None
    assert mat.lineage["criada_por"]["numero_matricula"] == "4698"
    assert mat.lineage["criada_por"]["staging_id"] is not None


def test_aceito_sem_ancora_vira_pendencia_visivel(db_session):
    """Sem sinal nenhum para ancorar, o aceite não some: entra em `ignorados`.

    Antes a mensagem era técnica ("matricula sem matricula_hint"); agora diz o
    que o consultor precisa fazer.
    """
    tenant, proc, prop, cli = _seed(db_session)
    itr = _doc(db_session, tenant, proc, "itr")
    _aceito(db_session, tenant, proc, itr, "nirf_cib", "9.153.765-7",
            "nirf_cib", hint=None)
    db_session.commit()

    r = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id,
                            user_id=None)

    assert any("aguardando vínculo" in i for i in r["ignorados"])


def test_vtn_aceito_sem_coluna_aparece_em_ignorados(db_session):
    """A outra classe: `matriculas.vtn` não existe."""
    tenant, proc, prop, cli = _seed(db_session)
    itr = _doc(db_session, tenant, proc, "itr")
    _aceito(db_session, tenant, proc, itr, "vtn", "4.199.942,38", "vtn", hint="6776")
    db_session.commit()

    r = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id,
                            user_id=None)

    assert r["ignorados"], "o aceite sem coluna não pode sumir calado"
    # #200 — não basta aparecer: tem que DIZER por quê. Identificador nu manda a
    # consultora adivinhar entre "foi recusado", "falta coluna" e "esqueceram de
    # mapear" — três coisas com saídas diferentes.
    linha = next(i for i in r["ignorados"] if "vtn" in i)
    assert ":" in linha and len(linha.split(":", 1)[1].strip()) > 20, (
        f"linha de ignorados sem motivo legível: {linha!r}"
    )


def test_lote_do_caso_16_todo_ignorado_tem_motivo(db_session):
    """Reproduz o lote real que a leitura de produção de 03/08 expôs.

    No processo 16, às 15:19, a consultora aceitou e a consolidação devolveu
    ``["imovel.rat_protocolo", "imovel.modulos_fiscais", "imovel.regulatory_issues"]``
    — sem uma palavra de motivo. Dos três, um estava sendo jogado fora e dois
    eram recusa por decisão, e a tela mostrava a mesma coisa para todos.
    """
    tenant, proc, prop, cli = _seed(db_session)
    rat = _doc(db_session, tenant, proc, "rat")

    def _aceito_imovel(campo, valor, alvo):
        row = ExtractedFieldStaging(
            tenant_id=tenant.id, process_id=proc.id, document_id=rat.id,
            field_name=campo, field_value={"value": valor},
            status=ExtractedFieldStatus.aceito, decided_value={"value": valor},
            decided_at=datetime.now(UTC),
            target_entity="imovel", target_field=alvo,
            source_doc_type="rat",
        )
        db_session.add(row)
        db_session.flush()
        return row

    _aceito_imovel("protocolo", "GO-1234567/2024", "rat_protocolo")
    _aceito_imovel("data_emissao", "24/11/2024", "rat_data_emissao")
    _aceito_imovel("modulos_fiscais", "3,7", "modulos_fiscais")
    db_session.commit()

    r = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id,
                            user_id=None)

    # Módulos fiscais ganhou destino: POUSA (era o que estava sendo descartado).
    db_session.refresh(prop)
    assert prop.modulos_fiscais == 3.7
    assert any(w["field"] == "modulos_fiscais" for w in r["writes"])

    # Protocolo e data do RAT continuam fora — mas agora DIZEM por quê.
    ignorados = r["ignorados"]
    protocolo = next(i for i in ignorados if "rat_protocolo" in i)
    data = next(i for i in ignorados if "rat_data_emissao" in i)
    assert "identifica o RAT" in protocolo
    assert "identifica o RAT" in data

    # Nenhuma linha pode ser identificador nu.
    for linha in ignorados:
        corpo = linha.split(":", 1)[1].strip() if ":" in linha else ""
        assert len(corpo) > 20, f"ignorado sem motivo na tela: {linha!r}"


def test_flag_sem_casa_pendencia_duravel(db_session):
    """Item 6 (pós-teste Isis): aceite que não vai pousar na base é flagado a
    CADA leitura — durável, não só na caixa efêmera do pós-consolidação.

    - hint de doc NÃO-criador (sigef) e sem matrícula na base → sem casa;
    - hint de doc criador (ccir) → terá casa (será criada) → não flaga;
    - hint que já existe na base → tem casa → não flaga.
    """
    from app.services.staging_consolidation import flag_sem_casa

    tenant, proc, prop, cli = _seed(db_session)

    # Matrícula 6776 já existe na base.
    m = Matricula(tenant_id=tenant.id, property_id=prop.id, numero_matricula="6776")
    db_session.add(m)
    db_session.flush()

    # Aceite para 4698 vindo de SIGEF (guard fantasma — não cria) e sem 4698 na
    # base → órfão.
    sigef = _doc(db_session, tenant, proc, "sigef")
    orfao = _aceito(db_session, tenant, proc, sigef, "codigo_certificacao", "GEO-1",
                    "geo_certificacao_codigo", hint="4698", tipo="sigef")
    # Aceite para 8001 vindo de CCIR (criador) → será criada.
    ccir = _doc(db_session, tenant, proc, "ccir")
    criavel = _aceito(db_session, tenant, proc, ccir, "codigo_sncr_incra", "111.222.333.444-5",
                      "codigo_incra_sncr", hint="8001", tipo="ccir")
    # Aceite para 6776 (já existe) → tem casa.
    existente = _aceito(db_session, tenant, proc, ccir, "cartorio", "Cartório X",
                        "cartorio", hint="6776", tipo="ccir")
    db_session.commit()

    motivos = flag_sem_casa(db_session, tenant.id, proc.id, prop)

    assert orfao.id in motivos
    assert "4698" in motivos[orfao.id]
    assert criavel.id not in motivos
    assert existente.id not in motivos
