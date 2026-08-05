"""
scripts/medir_defesa_federal.py — medição A/B do corpus federal (condição 2).

Roda a MESMA pergunta antes e depois da ingestão do pacote A, com o MESMO
modelo, isolando o corpus como única variável. Reproduz o caminho de
recuperação do `LegislacaoAgent` para a esfera FEDERAL (ADR-034):

    jurisdiction IN ('federal', 'nacional')   +   uf = GO (federal tem uf NULL)

Não é o agente inteiro — é o trecho dele que o corpus afeta: recuperação RAG
+ fundamentação. Fora isso, nada muda entre as duas rodadas.

Métricas reportadas (o que o André pediu):
  - normas citadas na resposta COM texto próprio no corpus
  - normas citadas apenas por MENÇÃO DE TERCEIROS (outra norma que as cita)
  - normas citadas SEM lastro nenhum no corpus
  - o Decreto 6.514/2008, art. 18, §1º aparece com texto literal recuperado?

Uso:
    python scripts/medir_defesa_federal.py --rotulo antes
    python scripts/medir_defesa_federal.py --rotulo depois
    python scripts/medir_defesa_federal.py --rotulo antes --sem-llm   # só RAG
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("medir_defesa")

# As perguntas. Literais e idênticas entre rodadas — são o controle do
# experimento. Cada bloco de corpus acrescenta a sua medição à série.
#
# `defesa` é a pergunta histórica (desde o pacote A); `car` entrou no bloco 2,
# que ingeriu o núcleo territorial/florestal — é nela que esse bloco deveria
# aparecer, se o ganho for real.
PERGUNTAS = {
    "defesa": (
        "Fundamente a defesa administrativa do auto de infração 484341/D "
        "(IBAMA, 2007, Fazenda São Jorge)"
    ),
    "car": (
        "Quais são os requisitos e o procedimento para retificação do "
        "Cadastro Ambiental Rural (CAR) de um imóvel rural em Goiás?"
    ),
    # --- baseline do chunking (04/08) ------------------------------------
    # Três perguntas novas, escolhidas pelo ESTADO ATUAL do alvo no índice:
    # duas devem melhorar e uma NÃO PODE piorar. Experimento só com casos que
    # devem melhorar não detecta regressão.
    "art61a": (
        "Quais são as condições, os prazos e as faixas de recomposição para "
        "regularização de Área de Preservação Permanente consolidada em imóvel "
        "rural, conforme o art. 61-A do Código Florestal?"
    ),
    "art71": (
        "Qual é o rito e quais são os prazos do processo administrativo "
        "federal para apuração de infração ambiental?"
    ),
    "compensacao_rl_go": (
        "Quais são os requisitos e o procedimento para compensação de Reserva "
        "Legal em Goiás?"
    ),
}
PERGUNTA = PERGUNTAS["defesa"]  # compat com as medições já gravadas

# Contexto factual do caso 15, extraído dos documentos reais (docs 331 e 338 em
# produção). Fixo nas duas rodadas — o corpus é a única variável.
CONTEXTO_CASO = """\
Auto de infração IBAMA nº 484341/D, lavrado em 2007, Fazenda São Jorge,
São João d'Aliança/GO. Órgão autuante: IBAMA (esfera federal).
Enquadramento constante do Julgamento 067-2012: "Art. 70 c/c 72 da Lei 9.605/98;
Art. 25 c/c Art. 2º, II, VII e XI do Decreto 3.179; Art. 2º, c da Lei 4.771/65".
Certidão de embargo lavrada com base no "art. 18, §1º do Decreto 6.514,
de 22 de julho de 2008".
Houve requerimento de adesão ao REFIZ com base no artigo 02 da MPV 780/2017.
Objeto: supressão de vegetação em Área de Preservação Permanente; PRAD
apresentado e sucessivas prorrogações de prazo entre 2008 e 2017."""

CONTEXTO_CAR = """Imóvel rural em Goiás com CAR já inscrito e necessidade de RETIFICAÇÃO do
cadastro: área declarada divergente da matrícula, perímetro a corrigir e
Reserva Legal a reposicionar. Interessa o rito: quem analisa, que documentos
instruem o pedido, qual a base normativa federal do SICAR e da retificação, e
como isso se relaciona com o georreferenciamento e a certificação do imóvel."""

CONTEXTO_ART61A = """Imóvel rural com ocupação anterior a 22/07/2008 em Área de Preservação
Permanente ao longo de curso d'água. Interessa a regra de transição: largura da
faixa a recompor conforme o tamanho do imóvel em módulos fiscais, prazos e
condições para a continuidade da atividade."""

CONTEXTO_ART71 = """Auto de infração ambiental lavrado por órgão federal. Interessa o rito do
processo administrativo: prazos para defesa, para julgamento e para recurso,
contados a partir de que marco."""

CONTEXTO_COMPENSACAO_GO = """Imóvel rural em Goiás com déficit de Reserva Legal e intenção de compensar em
vez de recompor. Interessa o rito estadual: modalidades admitidas, requisitos de
equivalência ecológica e localização, documentos e quem analisa."""

CONTEXTOS = {
    "defesa": CONTEXTO_CASO,
    "car": CONTEXTO_CAR,
    "art61a": CONTEXTO_ART61A,
    "art71": CONTEXTO_ART71,
    "compensacao_rl_go": CONTEXTO_COMPENSACAO_GO,
}

# O escopo era CRAVADO no script: federal + uf=GO, sempre. A quinta pergunta é
# ESTADUAL de Goiás — rodada no escopo federal ela mediria o corpus errado e
# devolveria um número com cara de resposta. Escopo é atributo da pergunta.
ESCOPO_FEDERAL = {"jurisdiction": ("federal", "nacional"), "uf": "GO"}
ESCOPO_GO = {"jurisdiction": ("estadual",), "uf": "GO"}

ESCOPOS = {
    "defesa": ESCOPO_FEDERAL,
    "car": ESCOPO_FEDERAL,
    "art61a": ESCOPO_FEDERAL,
    "art71": ESCOPO_FEDERAL,
    "compensacao_rl_go": ESCOPO_GO,
}

# Alvo-CONJUNTO da pergunta estadual (adendo de 04/08).
#
# A compensação de Reserva Legal em GO não tem "a norma": está espalhada. O alvo
# é o CONJUNTO, e cada item vem do identificador REAL gravado no catálogo —
# nenhum inventado.
#
# O levantamento devolveu 8 linhas; entram 7. A oitava foi EXCLUÍDA e a razão
# fica registrada: é `identifier IS NULL` (chunk 25771, "TERMO DE REFERÊNCIA —
# COMPENSAÇÃO AMBIENTAL POR DOAÇÃO DE IMÓVEL EM UNIDADE DE CONSERVAÇÃO"), e
# trata de **compensação ambiental do SNUC** — outro instituto, que só casou por
# compartilhar a palavra "compensação". Mantê-la afrouxaria o aceite: a busca
# poderia "passar" devolvendo documento de tema diferente.
CONJUNTO_GO_COMPENSACAO_RL = [
    "Coletânea Regularização Ambiental GO 2024",
    "IN SEMAD 3/2025",
    "Coletânea Licenciamento GO 2020+",
    "Lei GO 21.231/2022",
    "IN SEMAD-GO 01/2024",
    "Portaria SEMAD-GO 501/2024",
    "7841 - Y1.2",
]


def _pg_para_python(regex: str) -> str:
    """`\\m`/`\\M` (fronteira de palavra do Postgres) → `\\b` do Python.

    Converter só um dos lados deixa o outro estourar `bad escape \\M` na
    compilação — foi o que aconteceu no primeiro dry-run.
    """
    return regex.replace(r"\m", r"\b").replace(r"\M", r"\b")


def _regex_uniao(identificadores: list[str]) -> str:
    """União ancorada dos identificadores literais.

    Escapa cada um: "Coletânea Licenciamento GO 2020+" tem `+`, que sem escape
    vira quantificador e muda o que casa. O dry-run confere que a união casa em
    ≥1 chunk — é a guarda contra escape errado passar despercebido.
    """
    return "^(?:" + "|".join(re.escape(i) for i in identificadores) + ")$"


# Alvo = o dispositivo (ou o conjunto de normas) que a resposta PRECISA conter.
ALVOS: dict[str, dict[str, object] | None] = {
    "defesa": {
        "nome": "Decreto 6.514/2008, art. 18",
        "identifier": r"\m6\.?514\M",
        "dispositivo": r"art\.?\s*18\M",
    },
    # Sem alvo, COM a razão registrada: a norma procedural do CAR (IN MMA
    # 2/2014) está no pacote federal ainda NÃO ingerido. Um alvo aqui mediria
    # ausência de corpus e a debitaria do chunking — atribuiria a causa errada.
    "car": {
        "sem_alvo": True,
        "motivo": (
            "a norma procedural do CAR (IN MMA 2/2014) não está ingerida; alvo "
            "hoje mediria ausência de corpus, não qualidade de chunking"
        ),
        "reavaliar_apos": "ingestao_normativas_federais",
    },
    # Hoje partido em 3+ pedaços (`Art. 61-A. (parte N)`): deve virar íntegro.
    "art61a": {
        "nome": "Lei 12.651/2012, art. 61-A",
        "identifier": r"\m12\.?651\M",
        "dispositivo": r"art\.?\s*61-A\M",
    },
    # CONTROLE NEGATIVO: hoje já está íntegro (180 tokens). Não pode piorar.
    "art71": {
        "nome": "Lei 9.605/1998, art. 71",
        "identifier": r"\m9\.?605\M",
        "dispositivo": r"art\.?\s*71\M",
    },
    # Alvo-conjunto: aceite = ≥1 chunk de QUALQUER norma do conjunto no top-k.
    "compensacao_rl_go": {
        "nome": "compensação de Reserva Legal em GO (conjunto de 7 normas)",
        "conjunto": CONJUNTO_GO_COMPENSACAO_RL,
        "identifier": _regex_uniao(CONJUNTO_GO_COMPENSACAO_RL),
        "dispositivo": None,
        "excluidos": [
            {
                "chunk_id": 25771,
                "identifier": None,
                "titulo": (
                    "TERMO DE REFERÊNCIA — COMPENSAÇÃO AMBIENTAL POR DOAÇÃO DE "
                    "IMÓVEL EM UNIDADE DE CONSERVAÇÃO"
                ),
                "razao": (
                    "trata de compensação ambiental do SNUC — instituto diferente "
                    "de compensação de Reserva Legal; casou apenas por compartilhar "
                    "a palavra 'compensação'. Mantê-lo afrouxaria o aceite, que "
                    "poderia passar devolvendo documento de outro tema"
                ),
            }
        ],
    },
}

# Marca que o chunker deixa quando parte um dispositivo ao meio.
RE_FRAGMENTO = re.compile(r"\(parte\s*\d+\)", re.I)


# --------------------------------------------------------------------------
# Fingerprint do corpus — asserido, não só gravado
# --------------------------------------------------------------------------
# Hoje (04/08) o Docker caiu no meio da rodada. Medição sobre banco parcial não
# falha: produz json plausível e mentiroso, com números menores que passariam
# por "resultado". Daí duas travas: um PISO absoluto, e a igualdade do
# fingerprint entre o início e o fim da rodada.
#
# O critério é IGUALDADE, não piso.
#
# Piso protege contra banco parcial (menos do que devia). Não protege contra
# corpus POLUÍDO — mais do que devia. Foi o caso em 04/08: outro agente ingeriu
# 11 documentos federais (+420 chunks) e o estado foi revertido. Um piso teria
# deixado a medição correr sobre 31.718 e produzido um baseline que não se
# compara com nada depois. Baseline e pós-remediação só se comparam sobre
# fingerprints IGUAIS; portanto o portão é igualdade exata.
ESTADO_ESPERADO = {
    "total_chunks": 30_165,
    "legislation_documents": 102,
}
ESTADO_FONTE = (
    "PREVISÃO declarada ANTES da reindexação da Fase 4 (05/08), a partir do "
    "dry-run: 28.971 chunks de legislação + 1.194 de outras fontes "
    "(norma_procedural 953, matriz_ipe 175, manual_ipe 48, gabarito_laudo 15, "
    "other 3) = 30.165. Estado anterior, do baseline 2e78917: 31.298/102."
)

# O portão é PREVISÃO, não espelho.
#
# O valor acima foi escrito e commitado ANTES de executar a reindexação, a
# partir do dry-run. Preenchê-lo com o número observado DEPOIS faria o portão
# confirmar qualquer resultado, inclusive um errado — ele deixaria de medir e
# passaria a refletir.
#
# Bater = previsão confirmada. Não bater = ACHADO: reportar e parar, nunca
# ajustar a constante para caber no observado.


class CorpusInvalido(RuntimeError):
    """Banco não está no estado que a medição exige. Nenhum json é produzido."""


def _fingerprint(session) -> dict:
    from sqlalchemy import text as _sql

    from app.core.config import settings as _s
    from app.services import embeddings as _emb

    total = int(session.execute(_sql("SELECT count(*) FROM knowledge_catalog")).scalar() or 0)
    docs = int(
        session.execute(_sql("SELECT count(*) FROM legislation_documents")).scalar() or 0
    )
    por_jur = {
        r.j: int(r.n)
        for r in session.execute(
            _sql(
                "SELECT coalesce(jurisdiction,'?') j, count(*) n "
                "FROM knowledge_catalog GROUP BY 1 ORDER BY 1"
            )
        ).all()
    }
    espacos = [
        {"modelo": r.m, "dim": r.d, "chunks": int(r.n)}
        for r in session.execute(
            _sql(
                "SELECT coalesce(embedding_model,'?') m, embedding_dim d, count(*) n "
                "FROM knowledge_catalog GROUP BY 1,2 ORDER BY 1,2"
            )
        ).all()
    ]
    return {
        "total_chunks": total,
        "legislation_documents": docs,
        "por_jurisdicao": por_jur,
        # provider/modelo efetivos vêm da trava do ADR-040 (#135) — não de
        # suposição sobre qual chave está no ambiente.
        "embedding_provider": _emb._select_provider(),
        "embedding_model": _emb.current_model(),
        "espacos_no_indice": espacos,
        "banco": f"{_s.POSTGRES_SERVER}:{_s.POSTGRES_PORT}/{_s.POSTGRES_DB}",
        "ivfflat_probes": getattr(_s, "RAG_IVFFLAT_PROBES", None),
    }


def _conferir_estado(fp: dict) -> list[str]:
    """Divergências entre o corpus medido e o estado esperado (lista vazia = ok)."""
    return [
        f"{campo}: encontrado {fp.get(campo)}, esperado {esperado}"
        for campo, esperado in ESTADO_ESPERADO.items()
        if fp.get(campo) != esperado
    ]


def _exigir_estado(fp: dict, *, somente_leitura: bool) -> None:
    """Portão de igualdade.

    Dry-run (`--sem-llm`) é só leitura e não produz baseline: avisa e segue,
    porque é justamente a rodada usada para inspecionar um corpus fora do
    estado. Medição completa RECUSA — um baseline medido sobre corpus poluído
    não é comparável com nada, e o defeito só apareceria meses depois, na
    comparação que deveria provar o ganho.
    """
    divergencias = _conferir_estado(fp)
    if not divergencias:
        return
    detalhe = "; ".join(divergencias)
    if somente_leitura:
        logger.warning(
            "corpus FORA do estado esperado (%s) — %s. Rodada é só leitura; "
            "nenhum baseline será produzido.",
            ESTADO_FONTE,
            detalhe,
        )
        return
    raise CorpusInvalido(
        f"corpus fora do estado esperado ({ESTADO_FONTE}): {detalhe}. "
        "Medição completa recusada — nenhum json foi gravado."
    )


def _exigir_estabilidade(inicio: dict, fim: dict) -> None:
    if inicio != fim:
        divergentes = sorted(
            k for k in set(inicio) | set(fim) if inicio.get(k) != fim.get(k)
        )
        raise CorpusInvalido(
            "o corpus MUDOU durante a rodada — medição inválida, json descartado. "
            f"Campos divergentes: {divergentes}. "
            f"início={inicio} fim={fim}"
        )

SYSTEM = """\
Você é um consultor ambiental sênior. Fundamente juridicamente a defesa
administrativa solicitada, citando as normas aplicáveis.

REGRAS:
- Cite APENAS normas cujo texto você tenha em mãos nos TRECHOS abaixo, ou que
  você identifique explicitamente como não tendo o texto disponível.
- Para cada norma citada, indique o dispositivo (artigo/parágrafo).
- Se um trecho estiver rotulado como NORMA HISTÓRICA/REVOGADA, diga isso
  expressamente ao citá-la e informe a norma sucessora.
- Se faltar base normativa para algum ponto, DIGA QUE FALTA. Não preencha
  lacuna com norma de esfera ou de tema aproximado."""

# Normas que a defesa deste auto precisa tocar (item 3 da medição de 31/07).
#
# O casamento é por REGEX ANCORADA, não por substring de dígitos. A primeira
# versão desta medição usava `identifier LIKE '%10%'` para a IN IBAMA 10/2012 e
# contou 1.544 chunks "com texto próprio" — casava "LC 140/2011" e "Lei 18.104".
# Métrica frouxa aqui inverteria a conclusão do A/B, que é justamente o que este
# script existe para evitar.
NORMAS_ESPERADAS: dict[str, str] = {
    # nome exibido           regex (Postgres, case-insensitive)
    "Decreto 6.514/2008": r"\m6\.?514\M",
    "Decreto 3.179/1999": r"\m3\.?179\M",
    "Lei 4.771/1965": r"\m4\.?771\M",
    "Lei 9.784/1999": r"\m9\.?784\M",
    "Lei 9.605/1998": r"\m9\.?605\M",
    "Lei 12.651/2012": r"\m12\.?651\M",
    # Sem o prefixo, "10" casaria com meio corpus.
    "IN IBAMA 10/2012": r"(instru[çc][ãa]o normativa|\mIN)\s*(IBAMA\s*)?n?[ºo°]?\s*10\M",
    "Lei 13.494/2017": r"\m13\.?494\M",
    # Idem: "780" solto casa dentro de "1.780".
    "MPV 780/2017": r"(\mMPV?\M|medida provis[óo]ria)[^0-9]{0,15}780\M",
    "Decreto 11.373/2023": r"\m11\.?373\M",
}


def _digitos(valor: str) -> str:
    """'9.605' e '9605' são a mesma lei (mesma regra do ADR-036)."""
    return re.sub(r"\D", "", valor or "")


def _tem_texto_proprio(session, regex: str) -> int:
    """Chunks cuja IDENTIDADE é essa norma (não que apenas a citam)."""
    from sqlalchemy import text as _sql

    row = session.execute(
        _sql(
            "SELECT count(*) FROM knowledge_catalog WHERE coalesce(identifier,'') ~* :re"
        ),
        {"re": regex},
    ).scalar()
    return int(row or 0)


def _mencoes_de_terceiros(session, regex: str) -> int:
    """Chunks que CITAM a norma sem serem ela."""
    from sqlalchemy import text as _sql

    row = session.execute(
        _sql(
            """
            SELECT count(*) FROM knowledge_catalog
            WHERE chunk_text ~* :re AND coalesce(identifier,'') !~* :re
            """
        ),
        {"re": regex},
    ).scalar()
    return int(row or 0)


def _rastrear_alvo(session, consulta, escopo, ident_py, disp_py, top_k, limite=200):
    """Onde o alvo ficou no ranking, quando não entrou no top-k.

    Alvo que EXISTE no corpus e não é recuperado é falha de RECUPERAÇÃO — não
    ausência de corpus. As duas se parecem no resultado final (o agente não cita
    a norma) e têm causas opostas: uma se resolve ingerindo, a outra mexendo em
    chunking/índice. Sem esta medição, a primeira leva a culpa da segunda.

    Reusa `search()` com limite maior em vez de refazer a consulta em SQL: mesmo
    caminho de código, mesmos filtros, números comparáveis com o top-k por
    construção.
    """
    from app.services.knowledge_catalog import search as _search

    amplo = _search(
        session,
        consulta,
        limit=limite,
        source_type="legislation",
        jurisdiction=escopo["jurisdiction"],
        uf=escopo["uf"],
        tenant_id=None,
        min_similarity=0.0,
    )
    achados = [
        {
            "id": c.id,
            "identifier": c.identifier,
            "section": c.section,
            "posicao_no_ranking": i,
            "similarity": round(c.similarity, 4),
            "entrou_no_top_k": i <= top_k,
        }
        for i, c in enumerate(amplo, 1)
        if ident_py.search(c.identifier or "") and disp_py.search(c.chunk_text or "")
    ]
    return {
        "limite_rastreado": limite,
        "posicoes": achados,
        "fora_do_ranking_rastreado": not achados,
    }


class _EscutaGateway(logging.Handler):
    """Captura os avisos do `ai_gateway` durante a chamada.

    `AIResponse` expõe `model_used`, `provider`, `duration_ms` e `finish_reason`
    — **não** expõe número de tentativas nem motivo do fallback. Em vez de
    inventar campo que não existe (ou pior, deduzir), escuto quem tem o dado: o
    próprio gateway, que já loga cada tentativa transitória e cada fallback.

    Timeout recorrente num modelo é sinal OPERACIONAL. Sem isto ele morre no
    terminal e o baseline registra só o resultado, como se tivesse saído liso.
    """

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.transientes: list[str] = []
        self.fallbacks: list[str] = []

    def emit(self, record):
        msg = record.getMessage()
        if "transient error" in msg:
            self.transientes.append(msg)
        elif "fallback" in msg:
            self.fallbacks.append(msg)

    def resumo(self) -> dict:
        return {
            "tentativas_transitorias": len(self.transientes),
            "fallbacks_acionados": len(self.fallbacks),
            "avisos": self.transientes + self.fallbacks,
        }


def _formatar_trechos(chunks: list) -> str:
    """Mesma formatação do `LegislacaoAgent._format_rag_context`."""
    if not chunks:
        return ""
    linhas = []
    for i, c in enumerate(chunks, 1):
        cabecalho = [c.title or c.source_ref]
        if c.section:
            cabecalho.append(c.section)
        if c.identifier:
            cabecalho.append(c.identifier)
        linhas.append(f"[{i}] {' — '.join(str(b) for b in cabecalho if b)}")
        linhas.append(c.chunk_text.strip())
        linhas.append("")
    return "\n".join(linhas)


def main() -> int:
    p = argparse.ArgumentParser()
    # Rótulo livre: cada rodada de corpus deixa a sua medição ao lado das
    # anteriores (antes → depois → depois_nucleo06 → ...). Lista fechada
    # obrigaria a editar o script a cada bloco novo.
    p.add_argument("--rotulo", required=True)
    p.add_argument("--pergunta", default="defesa", choices=sorted(PERGUNTAS),
                   help="qual pergunta do experimento (defesa = a série histórica)")
    p.add_argument("--out-dir", type=Path, default=Path("ops/medicao_corpus_federal"))
    p.add_argument("--top-k", type=int, default=None, help="default: LEGISLATION_RAG_TOP_K")
    p.add_argument("--sem-llm", action="store_true", help="só recuperação, sem chamar o modelo")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.services.knowledge_catalog import search

    pergunta = PERGUNTAS[args.pergunta]
    contexto = CONTEXTOS[args.pergunta]
    top_k = args.top_k or getattr(settings, "LEGISLATION_RAG_TOP_K", 8)
    modelo = settings.GEMINI_LEGAL_MODEL

    session = SessionLocal()
    try:
        # --- fingerprint de ABERTURA (piso obrigatório) ----------------------
        fp_inicio = _fingerprint(session)
        _exigir_estado(fp_inicio, somente_leitura=args.sem_llm)

        # --- estado do corpus (o que muda entre as rodadas) -------------------
        from sqlalchemy import text as _sql

        corpus = session.execute(
            _sql(
                """
                SELECT coalesce(jurisdiction,'?') j, count(*) n
                FROM knowledge_catalog GROUP BY 1 ORDER BY 2 DESC
                """
            )
        ).all()
        estado_corpus = {r.j: int(r.n) for r in corpus}

        # --- recuperação: esfera FEDERAL, exatamente como o ADR-034 escopa ----
        consulta = f"{pergunta}\n\n{contexto}"
        escopo = ESCOPOS[args.pergunta]
        chunks = search(
            session,
            consulta,
            limit=top_k,
            source_type="legislation",
            jurisdiction=escopo["jurisdiction"],
            uf=escopo["uf"],
            tenant_id=None,
            min_similarity=0.0,
        )

        recuperados = [
            {
                "id": c.id,
                "identifier": c.identifier,
                "title": c.title,
                "section": c.section,
                "jurisdiction": c.jurisdiction,
                "similarity": round(c.similarity, 4),
                "chars": len(c.chunk_text),
            }
            for c in chunks
        ]

        # --- cobertura nominal do corpus, norma a norma -----------------------
        cobertura = {}
        for nome, regex in NORMAS_ESPERADAS.items():
            proprio = _tem_texto_proprio(session, regex)
            terceiros = _mencoes_de_terceiros(session, regex)
            cobertura[nome] = {
                "chunks_com_texto_proprio": proprio,
                "chunks_por_mencao_de_terceiros": terceiros,
                "situacao": (
                    "texto_proprio" if proprio
                    else ("apenas_mencao_de_terceiros" if terceiros else "sem_lastro")
                ),
            }

        # --- fragmentação: a métrica ESTRUTURAL do chunking -------------------
        # Universal (vale para as 5 perguntas): dos trechos que voltaram, quantos
        # são pedaço de um dispositivo partido ao meio? É o número que a
        # remediação do chunking (#117/#118/#119) precisa derrubar.
        fragmentos_no_topo = sum(1 for c in chunks if RE_FRAGMENTO.search(c.section or ""))
        fragmentacao = {
            "trechos_recuperados": len(chunks),
            "sao_pedaco_de_dispositivo": fragmentos_no_topo,
            "identificadores_distintos": len({c.identifier for c in chunks if c.identifier}),
        }

        # Alvo: o dispositivo que a resposta precisa conter, quando há um.
        alvo_spec = ALVOS.get(args.pergunta)
        alvo = None
        if alvo_spec and alvo_spec.get("sem_alvo"):
            alvo = dict(alvo_spec)
        elif alvo_spec and alvo_spec.get("conjunto"):
            # Alvo-CONJUNTO: aceite = ≥1 chunk de qualquer norma do conjunto.
            uniao = alvo_spec["identifier"]
            no_corpus = session.execute(
                _sql(
                    "SELECT count(*) FROM knowledge_catalog "
                    "WHERE coalesce(identifier,'') ~ :re"
                ),
                {"re": uniao},
            ).scalar()
            membros = set(alvo_spec["conjunto"])
            presentes = [
                {
                    "identifier": c.identifier,
                    "posicao": i,
                    "similarity": round(c.similarity, 4),
                    "section": c.section,
                    "fragmento": bool(RE_FRAGMENTO.search(c.section or "")),
                }
                for i, c in enumerate(chunks, 1)
                if (c.identifier or "") in membros
            ]
            alvo = {
                "nome": alvo_spec["nome"],
                "conjunto": alvo_spec["conjunto"],
                "regex_uniao": uniao,
                "excluidos": alvo_spec.get("excluidos", []),
                "chunks_no_corpus": int(no_corpus or 0),
                "membros_recuperados": presentes,
                "aceite_atendido": bool(presentes),
            }
        elif alvo_spec:
            no_corpus = session.execute(
                _sql(
                    """
                    SELECT count(*) FROM knowledge_catalog
                    WHERE coalesce(identifier,'') ~* :ident AND chunk_text ~* :disp
                    """
                ),
                {"ident": alvo_spec["identifier"], "disp": alvo_spec["dispositivo"]},
            ).scalar()
            # Em quantos pedaços o alvo está partido HOJE (section com "(parte N)").
            partido_em = session.execute(
                _sql(
                    """
                    SELECT count(*) FROM knowledge_catalog
                    WHERE coalesce(identifier,'') ~* :ident
                      AND coalesce(section,'') ~* :disp
                      AND coalesce(section,'') ~* '\\(parte'
                    """
                ),
                {"ident": alvo_spec["identifier"], "disp": alvo_spec["dispositivo"]},
            ).scalar()
            _ident_py = re.compile(_pg_para_python(alvo_spec["identifier"]), re.I)
            _disp_py = re.compile(_pg_para_python(alvo_spec["dispositivo"]), re.I)
            recuperados_do_alvo = [
                c for c in chunks
                if _ident_py.search(c.identifier or "") and _disp_py.search(c.chunk_text or "")
            ]
            existe = int(no_corpus or 0) > 0
            recuperado = bool(recuperados_do_alvo)
            # A classificação separa duas causas opostas que produzem o mesmo
            # sintoma (o agente não cita a norma).
            if recuperado:
                classificacao = "recuperado"
            elif existe:
                classificacao = "falha_de_recuperacao"
            else:
                classificacao = "ausencia_de_corpus"
            alvo = {
                "nome": alvo_spec["nome"],
                "chunks_no_corpus": int(no_corpus or 0),
                "partido_em_pedacos": int(partido_em or 0),
                "recuperado_nesta_busca": recuperado,
                "recuperado_como_fragmento": any(
                    RE_FRAGMENTO.search(c.section or "") for c in recuperados_do_alvo
                ),
                "classificacao": classificacao,
            }
            if classificacao == "falha_de_recuperacao":
                # Existe no corpus e ficou de fora: onde ficou, e com que
                # similaridade. É a evidência que a remediação precisa reverter.
                alvo["rastreamento"] = _rastrear_alvo(
                    session, consulta, escopo, _ident_py, _disp_py, top_k
                )

        # --- o teste específico do art. 18, §1º do 6.514 ----------------------
        # Identidade 6.514 + o dispositivo (art. 18) — não "art" solto perto de "18".
        _RE_6514 = r"\m6\.?514\M"
        _RE_ART18 = r"art\.?\s*18\M"
        art18 = session.execute(
            _sql(
                """
                SELECT count(*) FROM knowledge_catalog
                WHERE coalesce(identifier,'') ~* :ident AND chunk_text ~* :disp
                """
            ),
            {"ident": _RE_6514, "disp": _RE_ART18},
        ).scalar()
        art18_recuperado = any(
            re.search(r"\b6\.?514\b", c.identifier or "")
            and re.search(r"art\.?\s*18\b", c.chunk_text, re.I)
            for c in chunks
        )

        resultado = {
            "rotulo": args.rotulo,
            "pergunta": pergunta,
            "perfil_pergunta": args.pergunta,
            "modelo": modelo,
            "top_k": top_k,
            "escopo": (
                f"jurisdiction IN {escopo['jurisdiction']} + uf={escopo['uf']} (ADR-034)"
            ),
            "fragmentacao": fragmentacao,
            "alvo": alvo,
            "fingerprint_inicio": fp_inicio,
            # Marcação explícita: rodada de validação do instrumento NÃO é
            # baseline e nenhum número dela entra na comparação antes/depois.
            "baseline": not args.sem_llm and not _conferir_estado(fp_inicio),
            "corpus_estado": "esperado" if not _conferir_estado(fp_inicio) else "poluido",
            "estado_esperado": {
                "exigido": ESTADO_ESPERADO,
                "fonte": ESTADO_FONTE,
                "divergencias": _conferir_estado(fp_inicio),
            },
            "estado_corpus": estado_corpus,
            "chunks_recuperados": recuperados,
            "cobertura_nominal": cobertura,
            "art18_par1_6514": {
                "chunks_no_corpus": int(art18 or 0),
                "recuperado_nesta_busca": bool(art18_recuperado),
            },
        }

        # --- fundamentação (LLM) ---------------------------------------------
        if not args.sem_llm:
            from app.core.ai_gateway import complete

            trechos = _formatar_trechos(chunks) or "(nenhum trecho recuperado)"
            user = (
                f"{contexto}\n\n"
                f"PERGUNTA: {pergunta}\n\n"
                f"TRECHOS LEGISLATIVOS RECUPERADOS DO CORPUS:\n{trechos}"
            )
            escuta = _EscutaGateway()
            log_gateway = logging.getLogger("app.core.ai_gateway")
            log_gateway.addHandler(escuta)
            try:
                resp = complete(
                    user,
                    system=SYSTEM,
                    model=modelo,
                    temperature=0.0,
                    max_tokens=settings.CLAUDE_LEGAL_MAX_TOKENS,
                    max_cost_override_usd=settings.AI_MAX_COST_PER_JOB_USD_LEGISLACAO,
                    agent_name="legislacao",
                )
            finally:
                log_gateway.removeHandler(escuta)
            resultado["gateway"] = escuta.resumo()
            resultado["provider_efetivo"] = getattr(resp, "provider", None)
            resultado["duracao_ms"] = getattr(resp, "duration_ms", None)
            # "length" = resposta TRUNCADA por teto de saída. Sem este campo, uma
            # fundamentação cortada no meio passa por resposta completa.
            resultado["finish_reason"] = getattr(resp, "finish_reason", None)
            # Resposta cortada não entra no baseline como resposta completa —
            # já custou uma investigação inteira de truncamento (tokens_out
            # travado abaixo do teto). O rótulo fica no dado, não no report.
            resultado["fundamentacao_truncada"] = (
                getattr(resp, "finish_reason", "") == "length"
            )
            if resultado["fundamentacao_truncada"]:
                logger.error(
                    "fundamentação TRUNCADA em %s (finish_reason=length) — "
                    "resposta incompleta, não usar como baseline",
                    args.pergunta,
                )
            # O modelo PEDIDO não é necessariamente o que respondeu: o gateway
            # tem cadeia de fallback e, num timeout, outro modelo assume. Gravar
            # só o pedido produz artefato que AFIRMA um modelo que não rodou —
            # e o A/B "com o mesmo modelo" passa a ser falso sem avisar.
            # Aconteceu na 1ª rodada deste baseline (a `defesa` caiu em fallback).
            resultado["modelo_efetivo"] = getattr(resp, "model_used", None)
            resultado["modelo_efetivo_igual_ao_pedido"] = (
                getattr(resp, "model_used", None) == modelo
            )
            resultado["resposta"] = resp.content
            resultado["custo_usd"] = getattr(resp, "cost_usd", None)
            resultado["tokens"] = {
                "in": getattr(resp, "tokens_in", None),
                "out": getattr(resp, "tokens_out", None),
            }

        # --- fingerprint de FECHAMENTO ---------------------------------------
        # Só agora o json pode ser escrito: se o banco mudou no meio (caiu,
        # subiu parcial, alguém ingeriu), a rodada é inválida e não vira arquivo.
        fp_fim = _fingerprint(session)
        _exigir_estabilidade(fp_inicio, fp_fim)
        resultado["fingerprint_fim"] = fp_fim

        args.out_dir.mkdir(parents=True, exist_ok=True)
        # Rodada sem LLM grava em arquivo PRÓPRIO: ela não tem `resposta` e
        # sobrescrever a medição boa com ela destrói o lado do A/B — que, uma vez
        # que o corpus mudou, não se reconstrói sem desfazer a ingestão.
        sufixo = "_sem_llm" if args.sem_llm else ""
        destino = args.out_dir / f"{args.rotulo}{sufixo}.json"
        destino.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # --- resumo legível ---------------------------------------------------
        print(f"\n=== MEDIÇÃO [{args.rotulo}] ===")
        print(f"corpus: {estado_corpus}")
        print(f"modelo: {modelo} | top_k: {top_k}")
        print(f"\ntrechos recuperados ({len(recuperados)}):")
        for r in recuperados:
            print(f"  [{r['similarity']:.4f}] {r['identifier']} — {r['section'] or '-'}")
        print("\ncobertura nominal:")
        for nome, dados in cobertura.items():
            print(
                f"  {nome:<26} {dados['situacao']:<28} "
                f"proprio={dados['chunks_com_texto_proprio']:<5} "
                f"terceiros={dados['chunks_por_mencao_de_terceiros']}"
            )
        print(
            f"\nart. 18 §1º do 6.514: {art18} chunks no corpus | "
            f"recuperado nesta busca: {art18_recuperado}"
        )
        if not args.sem_llm:
            print(f"\ncusto: {resultado.get('custo_usd')} | tokens: {resultado.get('tokens')}")
        print(f"\n→ {destino}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
