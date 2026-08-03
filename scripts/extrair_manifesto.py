"""
scripts/extrair_manifesto.py — planilha da curadoria → manifesto versionado.

A planilha da Isis é uma **matriz analítica**: a mesma norma aparece em várias
linhas, examinada por ângulos diferentes. No núcleo 06, 43 linhas apontam para
26 URLs distintas — o Decreto 6.514/2008 sozinho ocupa 7 linhas (embargo,
apreensão, suspensão, reincidência...).

Isso é ótimo para quem analisa e péssimo para quem ingere: ingerir por linha
baixaria o mesmo decreto sete vezes. Este script **agrupa por URL** e emite uma
linha de manifesto por documento, preservando os macrotemas de todas as linhas
que apontavam para ele.

A planilha fica FORA do repo (`curadoria_isis/`, no .gitignore). O manifesto
gerado É versionado — é ele a fonte de verdade do corpus (ADR-038). Rodar de
novo com a planilha atualizada e comparar o diff é a forma de auditar o que a
curadoria mudou.

Uso:
    python scripts/extrair_manifesto.py \
        --planilha curadoria_isis/regente_pesquisa_normativa_federal_v12_ativos_carbono.xlsx \
        --aba 06_Infracoes_Embargos \
        --bloco 06 \
        --saida data/corpus_manifesto/nucleo_06_infracoes_embargos.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# URL que é página de serviço/consulta, não texto de norma. Vira
# `referencia_operacional`: versionada e exibível, fora do corpus vetorial.
PADROES_REFERENCIA = (
    "perguntas-frequentes", "/servicos/", "dadosabertos", "areasembargadas",
    "informacoes-gerais", "solucao-legal", "administrativo-contencioso",
    "areas-embargadas", "atendimento-ao-manual", "/consultas/",
)

# Sinal MAIS FORTE que a URL: a própria curadoria classifica cada linha na coluna
# "Tipo normativo / sistema". Quando ela diz "Sistema", "Base geoespacial",
# "Portal" ou "Plano", está dizendo que aquilo não é texto de norma — e ela sabe
# melhor do que qualquer heurística nossa sobre o formato da URL.
#
# Calibrado no bloco 2: os núcleos 02/03 apontam para SIGEF, acervo fundiário do
# INCRA, malhas do IBGE, CNUC, WebAmbiente. Nenhum casava com os padrões de URL
# do núcleo 06 e todos são inequívocos na coluna de tipo.
TIPOS_REFERENCIA = (
    "sistema", "base geoespacial", "base geográfica", "base cartográfica",
    "base pública", "portal", "serviço", "plano federal", "dados abertos",
    "base temática",
)

# A espécie normativa nomeada no tipo desempata quando a URL não denuncia um
# portal: "Portaria / serviço" é uma PORTARIA (a IBAMA 15/2026) que por acaso
# também tem página de serviço.
ESPECIES_NORMATIVAS = (
    "lei", "decreto", "instrução normativa", "portaria", "resolução",
    "medida provisória", "constituição", "orientação jurídica",
)


def _classificar(url: str, tipo_curadoria: str) -> str:
    """`norma` ou `referencia_operacional`.

    Ordem de precedência, e ela importa — as duas primeiras versões desta função
    erraram por inverter:

    1. **A URL manda.** É ela que vai ser baixada; o que ela aponta é o que
       entraria no corpus. "Decreto federal / sistema" cuja URL é a consulta de
       áreas embargadas baixaria a página de consulta, não o decreto.
    2. **Espécie normativa no tipo desempata.** Sem sinal de portal na URL,
       "Portaria / serviço" é portaria.
    3. **Tipo de referência.** "Sistema", "Base geoespacial", "Portal".
    4. Na dúvida, norma — o dry-run e a `validation_keyword` pegam o engano, e
       errar para o lado de conferir é mais barato que errar para o lado de
       excluir em silêncio.
    """
    url_l, tipo_l = url.lower(), (tipo_curadoria or "").lower()
    if any(pat in url_l for pat in PADROES_REFERENCIA):
        return "referencia_operacional"
    if any(e in tipo_l for e in ESPECIES_NORMATIVAS):
        return "norma"
    if any(t in tipo_l for t in TIPOS_REFERENCIA):
        return "referencia_operacional"
    return "norma"

COLUNAS = [
    "identifier", "titulo", "url", "bloco", "orgao", "esfera", "uf", "tipo",
    "status_fonte", "fonte_oficial", "vigencia_inicio", "vigencia_fim",
    "sucessora_ref", "validation_keyword", "demand_types", "observacao_curadoria",
]

# Extrai "Lei nº 9.605/1998" → ("Lei", "9.605", "1998")
_RE_NORMA = re.compile(
    r"(Constitui[çc][ãa]o Federal|Lei Complementar|Lei|Decreto|"
    r"Instru[çc][ãa]o Normativa|Portaria|Resolu[çc][ãa]o|OJN)"
    r"[^\d]{0,30}?(\d[\d.]*)\s*(?:/|de\s+\d{1,2}\s+de\s+\w+\s+de\s+)?(\d{4})?",
    re.I,
)


def _identificador(ato: str, url: str) -> tuple[str, str]:
    """(identifier, validation_keyword) a partir do texto do ato.

    O `validation_keyword` sai do NÚMERO da norma: é o que prova que o texto
    baixado é o que se pediu. Sem número reconhecível, quem curou tem de
    preencher à mão — e o carregador do manifesto recusa a linha vazia.
    """
    m = _RE_NORMA.search(ato or "")
    if not m:
        return "", ""
    especie, numero, ano = m.group(1), m.group(2), m.group(3)
    especie = especie.strip().title()
    if especie.lower().startswith("constitui"):
        return "Constituição Federal de 1988", "art. 225"
    ident = f"{especie} {numero}" + (f"/{ano}" if ano else "")
    return ident, numero


def main() -> int:
    import openpyxl

    p = argparse.ArgumentParser()
    p.add_argument("--planilha", type=Path, required=True)
    p.add_argument("--aba", required=True)
    p.add_argument("--bloco", required=True)
    p.add_argument("--saida", type=Path, required=True)
    p.add_argument("--linha-cabecalho", type=int, default=2)
    args = p.parse_args()

    wb = openpyxl.load_workbook(args.planilha, data_only=True)
    rows = list(wb[args.aba].values)
    head = [str(h or "").strip() for h in rows[args.linha_cabecalho - 1]]
    dados = [dict(zip(head, r, strict=False)) for r in rows[args.linha_cabecalho:] if any(r)]

    col_ato = "Legislação federal / ato / sistema"
    col_url = "Fonte URL"
    col_status = "Status da fonte"
    col_orgao = "Ente federado / órgão normativo"
    col_tema = "Macrotema"
    col_tipo = "Tipo normativo / sistema"

    por_url: OrderedDict[str, dict] = OrderedDict()
    for d in dados:
        url = str(d.get(col_url) or "").strip()
        if not url:
            continue
        ato = str(d.get(col_ato) or "").strip()
        if url not in por_url:
            ident, keyword = _identificador(ato, url)
            tipo_linha = _classificar(url, str(d.get(col_tipo) or ""))
            eh_ref = tipo_linha == "referencia_operacional"
            por_url[url] = {
                "identifier": ident or ato[:60],
                "titulo": ato[:300],
                "url": url,
                "bloco": args.bloco,
                "orgao": str(d.get(col_orgao) or "").split("/")[0].strip(),
                "esfera": "federal",
                "uf": "",
                "tipo": "referencia_operacional" if eh_ref else "norma",
                "status_fonte": str(d.get(col_status) or "").strip(),
                "fonte_oficial": "",
                "vigencia_inicio": "",
                "vigencia_fim": "",
                "sucessora_ref": "",
                "validation_keyword": "" if eh_ref else keyword,
                "demand_types": "defesa",
                "observacao_curadoria": "",
                "_temas": [],
            }
        tema = str(d.get(col_tema) or "").strip()
        if tema and tema not in por_url[url]["_temas"]:
            por_url[url]["_temas"].append(tema)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    with args.saida.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS)
        w.writeheader()
        for item in por_url.values():
            temas = item.pop("_temas")
            if temas and not item["observacao_curadoria"]:
                item["observacao_curadoria"] = "macrotemas: " + "; ".join(temas[:4])
            w.writerow(item)

    normas = sum(1 for i in por_url.values() if i["tipo"] == "norma")
    print(f"linhas na planilha : {len(dados)}")
    print(f"URLs distintas     : {len(por_url)}")
    print(f"  normas           : {normas}")
    print(f"  refs operacionais: {len(por_url) - normas}")
    print(f"→ {args.saida}")
    print("\nATENÇÃO: o CSV é um RASCUNHO. Vigência, sucessora e as keywords que")
    print("o extrator não conseguiu inferir são CURADORIA HUMANA — revisar antes")
    print("de ingerir. O carregador recusa linha ingerível sem validation_keyword.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
