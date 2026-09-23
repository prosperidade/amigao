"""Contrato do motor jurídico (ADR-073): fatos, seis estados, fundamento por ID, ciclo de
vida e integração com a Rota — positivo, negativo, desconhecido, não aplicável e norma
ausente, com as regras reais do gate (`regras/gate_4b.yaml`) sobre catálogo sintético.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from tests.recuperacao import catalogo_sintetico as cs

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document
from app.models.entrada_semantica import ClassificacaoDocumento
from app.models.evidence import EvidenceVersion
from app.models.motor_juridico import AvaliacaoRegra, RegraVersao
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.regulatory import RegulatoryDiagnosis
from app.models.rota import RotaPassoOrigem
from app.services.motor_juridico import ciclo, importador
from app.services.motor_juridico.avaliador import SemConjuntoAtivo, avaliar_regra, executar
from app.services.motor_juridico.fatos import montar_fatos
from app.services.motor_juridico.rota import gerar_rota_pelo_motor
from app.services.zona_normativa.curadoria import CuradoriaNegada, TransicaoInvalida, conceder_papel

HOJE = date(2026, 9, 23)
SENHA = "x"  # catalogo_sintetico.usuario usa a senha "x"


# ---------------------------------------------------------------------------
# Cenário
# ---------------------------------------------------------------------------

def _catalogo(db, status: str = "proposto") -> dict[str, int]:
    """As três fontes do gate que existem no catálogo; Código Civil e IN SEMAD 22/2025 ficam fora."""
    out = {}
    for ident, rotulo, artigo in (("lei|br||12651|2012", "Lei 12.651/2012", "29"),
                                  ("in|br|mma|2|2014", "IN MMA 2/2014", "2"),
                                  ("lei|br||5868|1972", "Lei 5.868/1972", "2")):
        f = cs.fonte(db, ident, rotulo=rotulo)
        v = cs.versao(db, f, status=status, vigencia_estado="nao_determinada")
        cs.dispositivo(db, v, artigo, rotulo_fonte=rotulo)
        out[ident] = v.id
    return out


def _motor_ativo(db, homologador) -> list[RegraVersao]:
    imp = importador.importar(db, importador.carregar())
    for rv in imp.criadas:
        ciclo.homologar(db, user=homologador, regra_versao_id=rv.id, nota="prova do contrato")
    c = ciclo.criar_conjunto(db, nome="gate 4b", regra_versao_ids=[rv.id for rv in imp.criadas])
    ciclo.publicar(db, user=homologador, conjunto_id=c.id)
    ciclo.ativar(db, user=homologador, conjunto_id=c.id)
    return imp.criadas


def _homologador(db, sufixo="h", *, tenant_id=None):
    su = cs.usuario(db, f"su-{sufixo}", superuser=True, tenant_id=tenant_id)
    h = cs.usuario(db, f"hom-{sufixo}", tenant_id=su.tenant_id)
    conceder_papel(db, concedente=su, user_id=h.id, papel="homologar_regra", area="*")
    return h


def _caso(db, tenant_id: int, *, uf: str | None = "GO", process_type: str = "car",
          especies: tuple[str, ...] = (), falecimento: bool = False) -> Process:
    cli = Client(tenant_id=tenant_id, full_name="Cliente", client_type=ClientType.pf, status=ClientStatus.active)
    db.add(cli)
    db.flush()
    prop = Property(tenant_id=tenant_id, client_id=cli.id, name="Imóvel", state=uf)
    db.add(prop)
    db.flush()
    p = Process(tenant_id=tenant_id, client_id=cli.id, property_id=prop.id, title="Caso",
                process_type=process_type, status=ProcessStatus.diagnostico)
    db.add(p)
    db.flush()
    for especie in especies:
        doc = Document(tenant_id=tenant_id, process_id=p.id, original_file_name=f"{especie}.pdf",
                       filename=f"{especie}.pdf", content_type="application/pdf",
                       storage_key=f"t/{uuid.uuid4().hex}", document_type=especie)
        db.add(doc)
        db.flush()
        db.add(ClassificacaoDocumento(tenant_id=tenant_id, documento_id=doc.id, versao=1,
                                      tipo_proposto=especie, motivo="teste"))
    if falecimento:
        content = {"attributes": {"predicate": "falecimento_declarado"}, "knowledge": {"state": "declarado"}}
        db.add(EvidenceVersion(tenant_id=tenant_id, process_id=p.id, object_id=f"obs-{uuid.uuid4().hex[:8]}",
                               version=1, kind="observacao", content=content,
                               content_hash=hashlib.sha256(str(content).encode()).hexdigest()))
    db.flush()
    return p


def _estados(execucao) -> dict[str, str]:
    return {execucao.rule_ids[a.regra_versao_id]: a.estado for a in execucao.avaliacoes}


def _por_regra(execucao, rule_id) -> AvaliacaoRegra:
    return next(a for a in execucao.avaliacoes if execucao.rule_ids[a.regra_versao_id] == rule_id)


# ---------------------------------------------------------------------------
# Fatos
# ---------------------------------------------------------------------------

def test_fatos_do_dossie_sao_determinados_e_falecimento_ausente_e_desconhecido(db_session):
    h = _homologador(db_session)
    p = _caso(db_session, h.tenant_id, especies=("car", "certidao_matricula", "certidao_matricula"))
    fatos = montar_fatos(db_session, process=p, tenant_id=h.tenant_id)
    assert fatos["caso.uf"]["valor"] == "GO"
    assert fatos["imovel.natureza"]["valor"] == "rural"
    assert fatos["car.no_dossie"]["valor"] is True
    assert fatos["dominio.matriculas_no_dossie"]["valor"] == 2
    assert fatos["ccir.no_dossie"] == {**fatos["ccir.no_dossie"], "valor": False, "estado": "determinado"}
    assert fatos["titular.falecimento_declarado"]["estado"] == "desconhecido"
    assert fatos["car.no_dossie"]["origem"]["documentos"]


def test_natureza_desconhecida_sem_demanda_de_car_nem_car_nos_autos(db_session):
    h = _homologador(db_session)
    p = _caso(db_session, h.tenant_id, process_type="misto", especies=("documento_pessoal",))
    fatos = montar_fatos(db_session, process=p, tenant_id=h.tenant_id)
    assert fatos["imovel.natureza"]["estado"] == "desconhecido"


def test_fatos_nao_leem_outro_tenant(db_session):
    h = _homologador(db_session)
    outro = cs.usuario(db_session, "outro")
    p = _caso(db_session, h.tenant_id, especies=("car",))
    assert montar_fatos(db_session, process=p, tenant_id=outro.tenant_id)["car.no_dossie"]["valor"] is False


# ---------------------------------------------------------------------------
# Ciclo de vida
# ---------------------------------------------------------------------------

def test_sem_conjunto_ativo_o_motor_nao_inventa_regra(db_session):
    h = _homologador(db_session)
    importador.importar(db_session, importador.carregar())
    p = _caso(db_session, h.tenant_id)
    with pytest.raises(SemConjuntoAtivo):
        executar(db_session, process=p, tenant_id=h.tenant_id, user_id=h.id)


def test_importacao_idempotente_e_conteudo_novo_vira_versao_nova(db_session):
    dados = importador.carregar()
    primeira = importador.importar(db_session, dados)
    assert len(primeira.criadas) == 6
    segunda = importador.importar(db_session, dados)
    assert segunda.criadas == [] and len(segunda.mantidas) == 6
    dados["regras"][0]["mensagem"] = "mensagem revista"
    terceira = importador.importar(db_session, dados)
    assert [rv.versao for rv in terceira.criadas] == [2]
    assert all(rv.estado == "rascunho" for rv in primeira.criadas)


def test_traducao_invalida_e_recusada_na_importacao(db_session):
    dados = importador.carregar()
    dados["regras"][0]["condicao"] = {"fato": "imovel.area_ha", "op": "gt", "valor": 4}
    with pytest.raises(importador.TraducaoInvalida, match="fora do vocabulário"):
        importador.importar(db_session, dados)


def test_superusuario_concede_mas_nao_homologa(db_session):
    su = cs.usuario(db_session, "su-only", superuser=True)
    rv = importador.importar(db_session, importador.carregar()).criadas[0]
    with pytest.raises(CuradoriaNegada):
        ciclo.homologar(db_session, user=su, regra_versao_id=rv.id, nota="x")


def test_homologar_regra_de_go_exige_papel_em_go(db_session):
    su = cs.usuario(db_session, "su-go", superuser=True)
    fed = cs.usuario(db_session, "fed", tenant_id=su.tenant_id)
    conceder_papel(db_session, concedente=su, user_id=fed.id, papel="homologar_regra", area="federal")
    criadas = {rv.origem["rule_id"]: rv for rv in importador.importar(db_session, importador.carregar()).criadas}
    ciclo.homologar(db_session, user=fed, regra_versao_id=criadas["REG-BR-CAR-001"].id, nota="ok")
    with pytest.raises(CuradoriaNegada, match="GO"):
        ciclo.homologar(db_session, user=fed, regra_versao_id=criadas["REG-GO-CAR-001"].id, nota="ok")


def test_publicar_recusa_regra_nao_homologada_e_ativar_troca_o_ativo(db_session):
    h = _homologador(db_session)
    criadas = importador.importar(db_session, importador.carregar()).criadas
    c1 = ciclo.criar_conjunto(db_session, nome="c1", regra_versao_ids=[rv.id for rv in criadas])
    with pytest.raises(TransicaoInvalida, match="publicação recusada"):
        ciclo.publicar(db_session, user=h, conjunto_id=c1.id)
    for rv in criadas:
        ciclo.homologar(db_session, user=h, regra_versao_id=rv.id, nota="ok")
    ciclo.publicar(db_session, user=h, conjunto_id=c1.id)
    ciclo.ativar(db_session, user=h, conjunto_id=c1.id)
    c2 = ciclo.criar_conjunto(db_session, nome="c2", regra_versao_ids=[criadas[0].id])
    ciclo.publicar(db_session, user=h, conjunto_id=c2.id)
    ciclo.ativar(db_session, user=h, conjunto_id=c2.id)
    assert (c1.estado, c2.estado) == ("inativo", "ativo")
    ciclo.ativar(db_session, user=h, conjunto_id=c1.id)  # rollback = reativar o anterior
    assert (c1.estado, c2.estado) == ("ativo", "inativo")


# ---------------------------------------------------------------------------
# Seis estados e fundamento
# ---------------------------------------------------------------------------

def test_caso_23_car_e_quatro_matriculas(db_session):
    """#23: CAR e 4 matrículas, sem CCIR, sem observação de falecimento."""
    h = _homologador(db_session)
    fontes = _catalogo(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, especies=("car",) + ("certidao_matricula",) * 4)
    ex = executar(db_session, process=p, tenant_id=h.tenant_id, user_id=h.id, data_referencia=HOJE)
    assert _estados(ex) == {
        "REG-BR-CAR-001": "aplicavel_nao_disparou",   # negativo: há CAR nos autos
        "REG-BR-CAR-002": "aplicavel_nao_disparou",
        "REG-BR-CAR-007": "aplicavel_disparou",       # positivo: 4 matrículas
        "REG-FUN-002": "aplicavel_disparou",
        "REG-FUN-012": "indeterminado",               # desconhecido: falecimento não observado
        "REG-GO-CAR-001": "aplicavel_disparou",
    }
    car7 = _por_regra(ex, "REG-BR-CAR-007")
    assert car7.fundamento_fonte_versao_id == fontes["in|br|mma|2|2014"]
    assert car7.fundamento_caminho == "IN MMA 2/2014, art. 2"
    fun12 = _por_regra(ex, "REG-FUN-012")
    assert fun12.faltantes == ["titular.falecimento_declarado"]
    assert fun12.consequencia["efeitos"][0]["tipo"] == "coleta"
    # Norma ausente: nunca substituta por semelhança.
    go = _por_regra(ex, "REG-GO-CAR-001")
    assert (go.fundamento_razao, go.fundamento_fonte_versao_id) == ("fonte_ausente", None)


def test_caso_25_falecimento_declarado_dispara_alerta(db_session):
    h = _homologador(db_session)
    _catalogo(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, especies=("escritura_publica", "comprovante_situacao_cadastral_cpf"),
              falecimento=True)
    ex = executar(db_session, process=p, tenant_id=h.tenant_id, user_id=h.id, data_referencia=HOJE)
    estados = _estados(ex)
    assert estados["REG-BR-CAR-001"] == "aplicavel_disparou"      # demanda CAR, sem CAR nos autos
    assert estados["REG-BR-CAR-007"] == "aplicavel_nao_disparou"  # escritura não é matrícula
    fun12 = _por_regra(ex, "REG-FUN-012")
    assert fun12.estado == "aplicavel_disparou"
    assert [e["tipo"] for e in fun12.consequencia["efeitos"]] == ["alerta_critico", "coleta"]
    assert fun12.fundamento_razao == "fonte_ausente"  # Código Civil fora do catálogo


def test_caso_22_sem_documento_do_imovel_vira_rota_de_coleta(db_session):
    h = _homologador(db_session)
    _catalogo(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, process_type="misto", especies=("documento_pessoal",))
    ex = executar(db_session, process=p, tenant_id=h.tenant_id, user_id=h.id, data_referencia=HOJE)
    estados = _estados(ex)
    for rid in ("REG-BR-CAR-001", "REG-FUN-002", "REG-GO-CAR-001", "REG-FUN-012"):
        assert estados[rid] == "indeterminado", rid
    assert estados["REG-BR-CAR-002"] == estados["REG-BR-CAR-007"] == "aplicavel_nao_disparou"
    assert _por_regra(ex, "REG-BR-CAR-001").faltantes == ["imovel.natureza"]


def test_regra_de_go_nao_se_aplica_a_imovel_de_mt(db_session):
    h = _homologador(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, uf="MT")
    ex = executar(db_session, process=p, tenant_id=h.tenant_id, user_id=h.id, data_referencia=HOJE)
    go = _por_regra(ex, "REG-GO-CAR-001")
    assert go.estado == "nao_aplicavel" and go.consequencia is None


def test_uf_desconhecida_torna_regra_estadual_indeterminada(db_session):
    h = _homologador(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, uf=None)
    go = _por_regra(executar(db_session, process=p, tenant_id=h.tenant_id, user_id=h.id), "REG-GO-CAR-001")
    assert go.estado == "indeterminado" and go.faltantes == ["caso.uf"]


def test_fonte_bruta_nao_fundamenta_e_dispositivo_ausente_e_nomeado(db_session):
    h = _homologador(db_session)
    _catalogo(db_session, status="bruto")
    rv = importador.importar(db_session, importador.carregar()).criadas[0]  # CAR-001
    fatos = {"imovel.natureza": {"valor": "rural", "estado": "determinado"},
             "car.no_dossie": {"valor": False, "estado": "determinado"}}
    campos = avaliar_regra(db_session, rv, "REG-BR-CAR-001", fatos, tenant_id=h.tenant_id, data_referencia=HOJE)
    assert campos["estado"] == "aplicavel_disparou"
    assert campos["fundamento_razao"] == "versao_nao_elegivel"

    f = cs.fonte(db_session, "lei|br||9999|2020", rotulo="Lei 9.999/2020")
    v = cs.versao(db_session, f, status="proposto", vigencia_estado="nao_determinada")
    cs.dispositivo(db_session, v, "1", rotulo_fonte="Lei 9.999/2020")
    from app.services.motor_juridico.fundamento import resolver  # noqa: PLC0415
    res = resolver(db_session, {"fonte": "lei|br||9999|2020", "artigo": "29"}, tenant_id=h.tenant_id,
                   data_referencia=HOJE)
    assert res.razao == "dispositivo_ausente"


def test_erro_de_execucao_e_estado_registrado_nunca_silencio(db_session):
    h = _homologador(db_session)
    rv = importador.importar(db_session, importador.carregar()).criadas[0]
    rv.condicao = {"fato": "caso.uf"}  # em memória: o banco recusaria (conteúdo imutável)
    campos = avaliar_regra(db_session, rv, "REG-BR-CAR-001", {"caso.uf": {"valor": "GO", "estado": "determinado"}},
                           tenant_id=h.tenant_id, data_referencia=HOJE)
    assert campos["estado"] == "erro_execucao" and "KeyError" in campos["detalhe_erro"]
    db_session.expire(rv)


# ---------------------------------------------------------------------------
# Rota
# ---------------------------------------------------------------------------

def test_rota_do_motor_idempotente_com_fundamento_por_id(db_session):
    h = _homologador(db_session)
    fontes = _catalogo(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, especies=("car",) + ("certidao_matricula",) * 4)
    res, _ = gerar_rota_pelo_motor(db_session, process=p, tenant_id=h.tenant_id, user_id=h.id,
                                   data_referencia=HOJE)
    passos = {x.titulo: x for x in res.rota.passos}
    assert res.created == len(passos) == 4  # CAR-007, FUN-002, GO-CAR-001 e a coleta do FUN-012
    assert all(x.origem == RotaPassoOrigem.motor for x in passos.values())
    ccir = passos["Emitir ou regularizar o CCIR do imóvel"]
    assert ccir.fundamento_fonte_versao_id == fontes["lei|br||5868|1972"] and ccir.fundamento_dispositivo_id
    assert ccir.orgao == "INCRA"
    sigcar = passos["Operar o CAR no SIGCAR (Portal Ambiental SEMAD-GO)"]
    assert sigcar.fundamento_fonte_versao_id is None and sigcar.sources[0]["sem_fonte"] is True

    de_novo, _ = gerar_rota_pelo_motor(db_session, process=p, tenant_id=h.tenant_id, user_id=h.id,
                                       data_referencia=HOJE)
    assert (de_novo.created, de_novo.matched, de_novo.is_diff) == (0, 4, False)
    assert de_novo.versao_preservada == 1


def _login(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": SENHA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_percurso_api_validar_remover_ciencia_fechar(client: TestClient, db_session):
    h = _homologador(db_session)
    _catalogo(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, especies=("escritura_publica",), falecimento=True)
    db_session.commit()
    hd = _login(client, h.email)

    r = client.post(f"/api/v1/processes/{p.id}/rota/gerar-motor", headers=hd)
    assert r.status_code == 201, r.text
    rota = r.json()["rota"]["rota"]
    execucao = r.json()["execucao"]
    assert execucao["disparadas"] >= 1 and execucao["alertas_sem_ciencia"]

    for passo in rota["passos"]:
        client.patch(f"/api/v1/rotas/{rota['id']}/passos/{passo['id']}", headers=hd,
                     json={"classificacao": "item_proposta"})
        url = f"/api/v1/rotas/{rota['id']}/passos/{passo['id']}"
        if passo["fundamento_fonte_versao_id"] is None:
            # Norma ausente: não valida; sai só com motivo.
            assert client.post(url + "/validar", headers=hd).status_code == 409
            assert client.delete(url, headers=hd).status_code == 400
            assert client.delete(url, headers=hd, params={"motivo": "norma fora do catálogo"}).status_code == 204
        else:
            assert client.post(url + "/validar", headers=hd).status_code == 200, passo["titulo"]

    r = client.post(f"/api/v1/rotas/{rota['id']}/fechar", headers=hd)
    assert r.status_code == 409 and "ciência" in r.json()["detail"]
    for av_id in execucao["alertas_sem_ciencia"]:
        r = client.post(f"/api/v1/processes/{p.id}/motor/alertas/{av_id}/ciencia", headers=hd,
                        json={"justificativa": "cliente informou o inventário em andamento"})
        assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/rotas/{rota['id']}/fechar", headers=hd)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "validada"
    assert all(x["fundamento_fonte_versao_id"] for x in r.json()["passos"])


def test_validacao_reverifica_fundamento_que_voltou_a_bruto(client: TestClient, db_session):
    h = _homologador(db_session)
    fontes = _catalogo(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, especies=("car",) + ("certidao_matricula",) * 2)
    db_session.commit()
    hd = _login(client, h.email)
    rota = client.post(f"/api/v1/processes/{p.id}/rota/gerar-motor", headers=hd).json()["rota"]["rota"]
    passo = next(x for x in rota["passos"] if x["fundamento_fonte_versao_id"] == fontes["in|br|mma|2|2014"])

    from app.models.zona_normativa import FonteNormativaVersao  # noqa: PLC0415
    db_session.get(FonteNormativaVersao, fontes["in|br|mma|2|2014"]).status_validacao = "bruto"
    db_session.commit()

    url = f"/api/v1/rotas/{rota['id']}/passos/{passo['id']}"
    client.patch(url, headers=hd, json={"classificacao": "direcao"})
    r = client.post(url + "/validar", headers=hd)
    assert r.status_code == 409 and "status_nao_serve_ao_destino" in r.json()["detail"]


def test_ciencia_de_outro_tenant_e_404(client: TestClient, db_session):
    h = _homologador(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id, falecimento=True)
    ex = executar(db_session, process=p, tenant_id=h.tenant_id, user_id=h.id, data_referencia=HOJE)
    alerta = _por_regra(ex, "REG-FUN-012")
    intruso = cs.usuario(db_session, "intruso")
    db_session.commit()
    r = client.post(f"/api/v1/processes/{p.id}/motor/alertas/{alerta.id}/ciencia",
                    headers=_login(client, intruso.email), json={"justificativa": "x"})
    assert r.status_code == 404


def test_rota_do_motor_dispensa_diagnostico_assinado(client: TestClient, db_session):
    """ADR-073 §8 [André]: o caminho do motor não passa pelo guarda do ADR-039."""
    h = _homologador(db_session)
    _motor_ativo(db_session, h)
    p = _caso(db_session, h.tenant_id)
    db_session.commit()
    r = client.post(f"/api/v1/processes/{p.id}/rota/gerar-motor", headers=_login(client, h.email))
    assert r.status_code == 201, r.text
    assert db_session.query(RegulatoryDiagnosis).filter_by(process_id=p.id).count() == 0
