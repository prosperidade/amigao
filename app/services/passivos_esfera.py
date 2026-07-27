"""Passivos do caso com a ESFERA de cada um (ADR-034).

Um caso real tem mais de um passivo, e eles não são todos da mesma esfera. O
processo 15 é o exemplo canônico: autos e ofícios do **IBAMA** (federal) sobre a
mesma fazenda que tem uma notificação da **SEMAD/GO** (estadual). Tratar o caso
como "é em Goiás, então é estadual" produz fundamentação plausível e errada.

Este módulo varre o que o caso tem — documentos de fiscalização e o relato do
intake — e devolve cada passivo com o órgão que o emitiu, a esfera derivada dele
(`esfera.esfera_do_orgao`) e a FONTE de onde isso foi lido. Sem fonte não entra:
é o Princípio 11 aplicado a um metadado que muda a resposta jurídica inteira.

O que este módulo NÃO faz: decidir rota, prazo ou norma aplicável. Ele responde
"de quem é cada exigência deste caso" e entrega isso a quem decide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.esfera import Esfera, esfera_do_orgao

__all__ = ["PassivoEsfera", "passivos_do_processo", "esferas_do_processo"]

# Tipos de documento que constituem passivo (exigência de um órgão sobre o caso).
_DOC_TYPES_PASSIVO = ("auto_infracao", "certidao_embargo")

# Quantos caracteres do início do documento olhar para achar o órgão. O órgão vem
# no CABEÇALHO (papel timbrado); ler o documento inteiro só aumentaria a chance de
# pegar uma menção de passagem a outro órgão no corpo.
_CABECALHO_CHARS = 1200

# Referências de peça administrativa no relato ("Notificação GO-NOT-2024-001985",
# "Auto de Infração 484341/D"). Serve para NOMEAR o passivo, não para validá-lo.
_RE_PECA = re.compile(
    r"\b(notifica[çc][ãa]o|auto\s+de\s+infra[çc][ãa]o|auto|of[íi]cio|embargo|"
    r"termo\s+de\s+embargo)\b[^.;\n]{0,60}?"
    r"([A-Z]{2,}[-\w./]*\d[-\w./]*|\d[\d.\-/]{2,})",
    re.IGNORECASE,
)


@dataclass
class PassivoEsfera:
    """Um passivo do caso com o órgão que o emitiu e a esfera derivada dele."""

    origem: str                      # "documento" | "relato"
    orgao: Optional[str]             # como aparece na fonte
    esfera: Optional[Esfera]         # None = não dá para afirmar (nunca chutar)
    referencia: Optional[str] = None # nº da peça, quando identificável
    fontes: list[dict[str, Any]] = field(default_factory=list)  # SourceRef-like

    def to_dict(self) -> dict[str, Any]:
        return {
            "origem": self.origem,
            "orgao": self.orgao,
            "esfera": self.esfera,
            "referencia": self.referencia,
            "fontes": self.fontes,
        }


def _orgao_no_texto(texto: str) -> Optional[str]:
    """Primeiro órgão RECONHECÍVEL no trecho — devolve o termo como veio.

    Varre linha a linha porque o cabeçalho de papel timbrado põe o órgão em uma
    linha própria; devolver a linha inteira dá contexto legível na tela
    ("Superintendência do IBAMA em Goiás" vale mais que "IBAMA").
    """
    for linha in texto.splitlines():
        limpa = linha.strip()
        if not limpa or len(limpa) > 160:
            continue
        if esfera_do_orgao(limpa) is not None:
            return limpa
    return None


def passivos_do_processo(
    db: Session, tenant_id: int, process_id: int
) -> list[PassivoEsfera]:
    """Passivos do caso, cada um com sua esfera e sua fonte.

    Duas origens, deliberadamente:

    * **documento** — auto de infração / certidão de embargo anexados. O órgão sai
      do cabeçalho do próprio documento (fonte forte, verificável).
    * **relato** — o que a consultora escreveu na entrada do caso. Fonte FRACA e
      marcada como tal: no caso 15 a notificação GO-NOT-2024-001985 existe apenas
      aí, e a Análise Legal a citou como se fosse documento. Ela é um passivo
      real e precisa entrar na conta — com o rótulo honesto de que veio do relato,
      não dos autos.
    """
    from app.models.document import Document  # noqa: PLC0415
    from app.models.process import Process  # noqa: PLC0415

    out: list[PassivoEsfera] = []

    docs = (
        db.query(Document)
        .filter(
            Document.tenant_id == tenant_id,
            Document.process_id == process_id,
            Document.deleted_at.is_(None),
            Document.document_type.in_(_DOC_TYPES_PASSIVO),
        )
        .all()
    )
    for doc in docs:
        texto = (doc.extracted_text or "")[:_CABECALHO_CHARS]
        orgao = _orgao_no_texto(texto)
        if orgao is None:
            continue
        nome_doc = doc.original_file_name or doc.filename or f"documento #{doc.id}"
        m = _RE_PECA.search(texto)
        out.append(
            PassivoEsfera(
                origem="documento",
                orgao=orgao,
                esfera=esfera_do_orgao(orgao),
                referencia=m.group(0).strip() if m else None,
                fontes=[{
                    "tipo": "documento",
                    "ref": str(doc.id),
                    "descricao": nome_doc,
                    "confianca": "alta",
                }],
            )
        )

    process = (
        db.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    relato = (process.description or "") if process else ""
    if relato:
        vistos: set[str] = {(p.orgao or "").lower() for p in out}
        for linha in re.split(r"[;\n]", relato):
            limpa = linha.strip()
            if not limpa:
                continue
            esf = esfera_do_orgao(limpa)
            if esf is None:
                continue
            orgao_bruto = _sigla_do_trecho(limpa)
            if orgao_bruto and orgao_bruto.lower() in vistos:
                continue
            m = _RE_PECA.search(limpa)
            vistos.add((orgao_bruto or "").lower())
            out.append(
                PassivoEsfera(
                    origem="relato",
                    orgao=orgao_bruto,
                    esfera=esf,
                    referencia=m.group(0).strip() if m else None,
                    fontes=[{
                        "tipo": "atendimento",
                        "ref": f"process:{process_id}",
                        "descricao": "relato do cliente na entrada do caso",
                        # Fraca de propósito: relato não é documento. Foi o que
                        # faltou dizer sobre a GO-NOT-2024-001985 no caso 15.
                        "confianca": "baixa",
                    }],
                )
            )
    return out


_RE_SIGLA = re.compile(r"\b([A-ZÇÃÕÁÉÍÓÚ]{3,10})\b")


def _sigla_do_trecho(trecho: str) -> Optional[str]:
    """Sigla do órgão citado no relato (SEMAD, IBAMA…), quando houver."""
    for candidato in _RE_SIGLA.findall(trecho):
        if esfera_do_orgao(candidato) is not None:
            return candidato
    return None


def esferas_do_processo(
    db: Session, tenant_id: int, process_id: int
) -> list[Esfera]:
    """Esferas presentes no caso, sem repetição e em ordem estável.

    É o que a busca de fundamentação consome: um caso com passivo federal E
    estadual precisa de DUAS varreduras de corpus, não de uma escolhida por UF.
    """
    ordem: list[Esfera] = ["federal", "estadual", "municipal"]
    presentes = {p.esfera for p in passivos_do_processo(db, tenant_id, process_id)}
    return [e for e in ordem if e in presentes]
