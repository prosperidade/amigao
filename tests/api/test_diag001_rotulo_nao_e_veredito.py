"""
DIAG-001 — rótulo de demanda não é veredito sobre o caso (spec Isis v0.1 §6).

Gate desta frente: **com `process_type=misto` e zero documentos, nenhuma
superfície afirma passivo.** Não basta olhar a caixa da aba Diagnóstico — o
rótulo do tipo vira o TÍTULO do processo (`intake.py`:
`f"{demand_label} — {client.full_name}"`), então "Múltiplos Passivos" reaparecia
em lista, sidebar, dossiê e proposta. Por isso o teste varre as três cargas que
alimentam tela: classificação, criação do caso e leitura do processo.

O que a spec permite e o que não permite:
  · pode descrever a DEMANDA (declarada pelo consultor ou inferida do relato);
  · pode orientar o próximo passo;
  · NÃO pode afirmar fato do caso que só evidência estabeleceria — sem base, o
    estado permitido é hipótese, nunca fato afirmado.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.services.intake_classifier import (
    _DEMAND_RULES,
    CONFIANCA_DECLARADA,
    classify_demand,
    dispensa_inferencia,
)

# "passivo"/"passivos" em qualquer caixa, com ou sem acento no plural.
PASSIVO = re.compile(r"passivos?\b", re.IGNORECASE)


def _cenario(db, email: str) -> Tenant:
    t = Tenant(name=f"T-{email}")
    db.add(t)
    db.flush()
    db.add(User(email=email, full_name="Consultora",
                hashed_password=get_password_hash("x12345"),
                tenant_id=t.id, is_active=True, is_superuser=True))
    db.flush()
    return t


def _login(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login",
                    data={"username": email, "password": "x12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _textos(valor) -> list[str]:
    """Todas as strings de uma carga JSON, recursivamente."""
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [s for v in valor.values() for s in _textos(v)]
    if isinstance(valor, list):
        return [s for v in valor for s in _textos(v)]
    return []


# ---------------------------------------------------------------------------
# O GATE
# ---------------------------------------------------------------------------

def test_gate_misto_sem_documentos_nao_afirma_passivo(client: TestClient, db_session):
    """`process_type=misto`, zero documentos: nenhuma das três cargas que
    alimentam a tela pode falar em passivo."""
    _cenario(db_session, "diag@ex.com")
    db_session.commit()
    h = _login(client, "diag@ex.com")

    # 1. Classificação (o que o painel do intake mostra)
    # Relato neutro: o gate é sobre zero DOCUMENTOS, e o endpoint exige um
    # relato mínimo. O texto não menciona passivo — se a saída mencionar, veio
    # do sistema, que é exatamente o que se está medindo.
    relato = "Cliente procurou a consultoria para tratar da situacao do imovel."
    classificacao = client.post("/api/v1/intake/classify", headers=h, json={
        "description": relato, "process_type": "misto"})
    assert classificacao.status_code == 200, classificacao.text
    achados = [s for s in _textos(classificacao.json()) if PASSIVO.search(s)]
    assert not achados, f"classificação ainda fala em passivo: {achados}"

    # 2. Criação do caso (o título nasce aqui)
    criado = client.post("/api/v1/intake/create-case", headers=h, json={
        "new_client": {"full_name": "ELODI", "email": "elodi@ex.com",
                       "cpf_cnpj": "29.091.958/0001-17", "client_type": "pj"},
        "new_property": {"name": "Fazenda Retiro"},
        "description": relato,
        "process_type": "misto",
    })
    assert criado.status_code == 201, criado.text
    corpo = criado.json()
    achados = [s for s in _textos(corpo) if PASSIVO.search(s)]
    assert not achados, f"criação do caso ainda fala em passivo: {achados}"

    # 3. Leitura do processo (o que a aba Diagnóstico e a sidebar consomem)
    proc = client.get(f"/api/v1/processes/{corpo['process_id']}", headers=h)
    assert proc.status_code == 200, proc.text
    detalhe = proc.json()
    achados = [s for s in _textos(detalhe) if PASSIVO.search(s)]
    assert not achados, f"processo ainda fala em passivo: {achados}"

    # E o título do caso — que é onde o rótulo se enterra mais fundo.
    assert not PASSIVO.search(detalhe["title"] or ""), \
        f"o título do caso afirma passivo: {detalhe['title']!r}"

    # Zero documentos, de fato: o gate não vale se algo tiver sido anexado.
    docs = client.get("/api/v1/documents/",
                      params={"process_id": corpo["process_id"]}, headers=h)
    if docs.status_code == 200:
        assert docs.json() == [] or docs.json().get("items", []) == [], \
            "o cenário do gate exige zero documentos"


# ---------------------------------------------------------------------------
# Confiança: escolha do consultor não é acerto da máquina
# ---------------------------------------------------------------------------

def test_tipo_informado_pelo_consultor_nao_vira_confianca_alta():
    """`confidence="high"` forçado por `process_type` manual era mentira: o
    sistema não inferiu nada, só obedeceu."""
    r = classify_demand("", process_type="misto")
    assert r.confidence == CONFIANCA_DECLARADA
    assert r.confidence != "high", "escolha manual não pode se disfarçar de acerto"


def test_inferencia_por_palavra_chave_continua_graduada():
    """O conserto não pode achatar a confiança de quem realmente inferiu."""
    r = classify_demand("Preciso fazer o CAR do imóvel, cadastro ambiental rural pendente")
    assert r.confidence in ("high", "medium"), r.confidence
    assert r.confidence != CONFIANCA_DECLARADA, "não houve declaração — houve inferência"

    vazio = classify_demand("bom dia, tudo bem?")
    assert vazio.demand_type == "nao_identificado"
    assert vazio.confidence == "low"


def test_tipo_declarado_dispensa_o_llm():
    """Guard de acoplamento: `llm_classifier` só pulava o LLM quando a confiança
    era a string "high". Com a confiança declarada deixando de se disfarçar de
    alta, a comparação antiga passaria a chamar o LLM justamente no caso em que
    não há nada a inferir — gastando token para adivinhar o que o consultor já
    disse. A pergunta agora tem porta única."""
    assert dispensa_inferencia(classify_demand("", process_type="misto").confidence)
    assert dispensa_inferencia("high")
    assert not dispensa_inferencia("medium")
    assert not dispensa_inferencia("low")


# ---------------------------------------------------------------------------
# O texto pré-escrito não pode afirmar fato do caso
# ---------------------------------------------------------------------------

def test_misto_descreve_a_demanda_sem_afirmar_pendencia():
    """"O caso apresenta múltiplos passivos" afirmava fato sobre um imóvel do
    qual o sistema não tinha lido uma linha. O texto agora diz o que é sabido
    (a demanda tem mais de uma frente) e o que não é (quantas e quais)."""
    regra = _DEMAND_RULES["misto"]
    assert not PASSIVO.search(regra["label"]), regra["label"]
    assert not PASSIVO.search(regra["diagnosis"]), regra["diagnosis"]
    assert not any(PASSIVO.search(p) for p in regra["next_steps"]), regra["next_steps"]
    # A incerteza fica explícita, não implícita.
    assert "não foram apurados" in regra["diagnosis"]


def test_nenhum_tipo_afirma_passivo_existente():
    """Varredura da CLASSE, não só do caso relatado: nenhum dos 16 tipos pode
    afirmar que o caso TEM passivo. Mencionar passivo como algo a verificar é
    legítimo — afirmar que existe, não."""
    afirmacoes = [
        "apresenta múltiplos passivos",
        "apresenta passivo",
        "possui passivo",
        "tem passivo",
        "há passivos",
    ]
    ofensores = [
        (chave, frase)
        for chave, regra in _DEMAND_RULES.items()
        for frase in afirmacoes
        if frase in regra["diagnosis"].lower()
    ]
    assert not ofensores, f"tipos afirmando passivo sem evidência: {ofensores}"
