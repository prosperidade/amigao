"""
Classificador heuristico do corpus SEMAD por NOME do arquivo (sem LLM).

Pre-classificacao para o relatorio de inventario preliminar. A classificacao
definitiva exige ler o conteudo das primeiras 2 paginas com um LLM — o que
fica para a sessao de ingestao em batch.

Sinais por tipo (taxonomia A/B/C/D):

  A. Matriz IPE        — codigo numerico ou alfanumerico no inicio do nome
                         (ex: "89 - ...", "7841 - ...", "A1.1.1 - ...")
                         ou palavras-chave do fluxo IPE
                         ("REQUERIMENTO", "VIABILIDADE LOCACIONAL", "QUESTIONARIO")

  B. Norma procedural  — sem codigo no inicio, sem padroes de laudo/manual.
                         Geralmente nomes descritivos do tema
                         (ex: "Compensacao Florestal e Compensacao Por Danos",
                         "ON_01_2021_SEMAD", "Guia DAI").

  C. Gabarito de laudo — "LAUDO", "TERMO DE REFERENCIA", "ROTEIRO",
                         "RELATORIO TECNICO", prefixos "TR " ou "TR  ".

  D. Manual IPE        — "Manual " (capitalizado) ou "MANUAL DE" no nome.

Output: TSV (path/tipo/justificativa) em stdout.

Uso:
    python scripts/classify_semad_heuristic.py \\
        --root "C:/Users/Administrador/Desktop/Amigao_do_Meio_Ambiente" \\
        > /tmp/semad_preclass.tsv
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Classification:
    path: Path
    tipo: str  # "A" | "B" | "C" | "D" | "indefinido"
    reason: str


# Regex compilados
# Codigos IPE no inicio do nome: "89 - ", "2.2 - ", "A1.1.1 - ", e "A1.1.3" (sem traco).
RE_CODIGO_NUM       = re.compile(r"^\d+(\.\d+)*\s*[-–]\s*", re.IGNORECASE)
RE_CODIGO_ALFANUM   = re.compile(r"^[A-Z]\d+(\.\d+)*(\s*[-–]\s*|\.pdf$)", re.IGNORECASE)
RE_REQUERIMENTO     = re.compile(r"\bREQUERIMENTO\b", re.IGNORECASE)
RE_VIABILIDADE      = re.compile(r"\bVIABILIDADE\s+LOCACIONAL\b", re.IGNORECASE)
RE_QUESTIONARIO     = re.compile(r"\bQUESTION[AÁ]RIO\b", re.IGNORECASE)

RE_LAUDO            = re.compile(r"\bLAUDO\b", re.IGNORECASE)
# TERMO DE REFERENCIA aceita espacos OU underscores (alguns arquivos tem TERMO_DE_REFERENCIA)
RE_TR               = re.compile(r"(\bTERMO[\s_]+DE[\s_]+REFER[EÊ]NCIA|\bTERMO\s+DE\s+DIAGN[OÓ]STICO|^TR\s)", re.IGNORECASE)
RE_ROTEIRO          = re.compile(r"\bROTEIRO\b", re.IGNORECASE)
RE_RELATORIO_TEC    = re.compile(r"\bRELAT[ÓO]RIO\s+T[EÉ]CNICO\b", re.IGNORECASE)

# Manual: aceita "Manual <Maiuscula>", "Manual -", "MANUAL DE", "Portal de" (portal IPE)
RE_MANUAL           = re.compile(r"(\bMANUAL\s+DE\b|\bManual\s+[A-Z\-]|\bPortal\s+de\s+Licenciamento\b)", re.IGNORECASE)
RE_GUIA             = re.compile(r"\bGUIA\s+", re.IGNORECASE)
RE_ON_SEMAD         = re.compile(r"^ON_\d+", re.IGNORECASE)


def classify(filename: str) -> tuple[str, str]:
    """Retorna (tipo, motivo) para um filename. Ordem importa — mais especifico primeiro."""
    name = filename.strip()

    # C. Gabarito (mais especifico — TR/LAUDO/ROTEIRO sao palavras fortes)
    if RE_LAUDO.search(name):
        return "C", "match_laudo"
    if RE_TR.search(name):
        return "C", "match_termo_referencia"
    if RE_ROTEIRO.search(name):
        return "C", "match_roteiro"
    if RE_RELATORIO_TEC.search(name):
        return "C", "match_relatorio_tecnico"

    # D. Manual IPE
    if RE_MANUAL.search(name):
        return "D", "match_manual"

    # A. Matriz IPE (codigos numericos/alfanum no inicio ou palavras-chave do fluxo)
    if RE_CODIGO_NUM.match(name):
        return "A", "match_codigo_numerico_inicio"
    if RE_CODIGO_ALFANUM.match(name):
        return "A", "match_codigo_alfanum_inicio"
    if RE_REQUERIMENTO.search(name):
        return "A", "match_requerimento"
    if RE_VIABILIDADE.search(name):
        return "A", "match_viabilidade_locacional"
    if RE_QUESTIONARIO.search(name):
        return "A", "match_questionario"

    # B. Norma procedural (heuristicas mais fracas — Guia, ON_, ou keywords de tema)
    if RE_GUIA.search(name) or RE_ON_SEMAD.search(name):
        return "B", "match_guia_ou_on_semad"
    if re.search(r"\bcompensa[cç][aã]o\b", name, re.IGNORECASE):
        return "B", "match_compensacao"
    if re.search(r"\binexigibilidade\b", name, re.IGNORECASE):
        return "B", "match_inexigibilidade"

    return "indefinido", "no_pattern_matched"


def walk_pdfs(root: Path) -> list[Path]:
    """Encontra todos os PDFs em 'Licenciamento (SEMAD)' e 'Manuais (SEMAD)'."""
    targets = ["Licenciamento (SEMAD)", "Manuais (SEMAD)"]
    found: list[Path] = []
    for sub in targets:
        d = root / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.pdf")):
            found.append(p)
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    args = ap.parse_args()

    pdfs = walk_pdfs(args.root)
    print("path\ttipo\tmotivo")
    for p in pdfs:
        tipo, reason = classify(p.name)
        # Relativo ao root pra output legivel
        rel = p.relative_to(args.root)
        print(f"{rel}\t{tipo}\t{reason}")


if __name__ == "__main__":
    main()
