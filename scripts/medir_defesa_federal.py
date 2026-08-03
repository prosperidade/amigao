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

CONTEXTOS = {"defesa": CONTEXTO_CASO, "car": CONTEXTO_CAR}

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
        chunks = search(
            session,
            consulta,
            limit=top_k,
            source_type="legislation",
            jurisdiction=("federal", "nacional"),
            uf="GO",
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
            "escopo": "jurisdiction IN ('federal','nacional') + uf=GO (ADR-034)",
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
            resp = complete(
                user,
                system=SYSTEM,
                model=modelo,
                temperature=0.0,
                max_tokens=settings.CLAUDE_LEGAL_MAX_TOKENS,
                max_cost_override_usd=settings.AI_MAX_COST_PER_JOB_USD_LEGISLACAO,
                agent_name="legislacao",
            )
            resultado["resposta"] = resp.content
            resultado["custo_usd"] = getattr(resp, "cost_usd", None)
            resultado["tokens"] = {
                "in": getattr(resp, "tokens_in", None),
                "out": getattr(resp, "tokens_out", None),
            }

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
