"""
scripts/ingest_federais_canonicos.py — Sprint 0 / 2º round

Baixa e ingere os diplomas federais canônicos que faltam na pasta da sócia.
Usa httpx + BeautifulSoup do script `ingest_legislation.py`.

Lista curada (2026-04-23, confirmada):
  - Lei 12.651/2012 (Código Florestal)
  - Lei 9.605/1998 (Crimes Ambientais)
  - Lei 9.985/2000 (SNUC)
  - Lei 6.938/1981 (PNMA)
  - LC 140/2011 (competências)
  - Res. CONAMA 001/1986 (EIA/RIMA)
  - Res. CONAMA 237/1997 (Licenciamento)
  - Res. CONAMA 369/2006 (APP)
  - Decreto 7.830/2012 (SICAR)
  - Decreto 8.235/2014 (PRA)

PACOTE A (2026-07-31) — direito sancionador e processual federal. A medição do
corpus mostrou que a lista acima cobre bem o direito MATERIAL (o que é APP, o
que é reserva legal) e quase nada do rito de uma defesa de auto de infração.
Metade do pacote A são normas REVOGADAS, ingeridas de propósito e marcadas como
históricas: o auto do caso 15 é de 2007 e se defende com a norma da época
(tempus regit actum). Ver `app/services/vigencia.py` e ADR-037.

Uso:
    python scripts/ingest_federais_canonicos.py --dry-run
    python scripts/ingest_federais_canonicos.py --only 12.651
    python scripts/ingest_federais_canonicos.py

    python scripts/ingest_federais_canonicos.py --pacote a --dry-run
    python scripts/ingest_federais_canonicos.py --pacote a          # ingere + indexa
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ingest_legislation import (  # noqa: E402
    estimate_tokens,
    load_from_url,
    sanitize_text,
    save_preview,
    verificar_mojibake,
)

logger = logging.getLogger("ingest_federais")


CURATED_FEDERAIS: list[dict] = [
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12651.htm",
        "title": "Código Florestal (Lei 12.651/2012)",
        "identifier": "Lei 12.651/2012",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "2012-05-25",
        "demand_types": ["car", "retificacao_car", "compensacao", "regularizacao_fundiaria"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l9605.htm",
        "title": "Lei de Crimes Ambientais (Lei 9.605/1998)",
        "identifier": "Lei 9.605/1998",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "1998-02-12",
        "demand_types": ["defesa"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l9985.htm",
        "title": "Sistema Nacional de Unidades de Conservação — SNUC (Lei 9.985/2000)",
        "identifier": "Lei 9.985/2000",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "2000-07-18",
        "demand_types": ["licenciamento", "compensacao"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l6938.htm",
        "title": "Política Nacional do Meio Ambiente (Lei 6.938/1981)",
        "identifier": "Lei 6.938/1981",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "1981-08-31",
        "demand_types": ["licenciamento"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp140.htm",
        "title": "Competências comuns em meio ambiente (LC 140/2011)",
        "identifier": "LC 140/2011",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "2011-12-08",
        "demand_types": ["licenciamento"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/decreto/d7830.htm",
        "title": "Regulamento do SICAR (Decreto 7.830/2012)",
        "identifier": "Decreto 7.830/2012",
        "source_type": "decreto",
        "agency": "Presidência da República",
        "effective_date": "2012-10-17",
        "demand_types": ["car", "retificacao_car"],
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/decreto/d8235.htm",
        "title": "Programa de Regularização Ambiental — PRA (Decreto 8.235/2014)",
        "identifier": "Decreto 8.235/2014",
        "source_type": "decreto",
        "agency": "Presidência da República",
        "effective_date": "2014-05-05",
        "demand_types": ["car", "retificacao_car", "compensacao"],
    },
    # CONAMA — o portal Sisconama serve múltiplos IDs com conteúdo desalinhado.
    # Validação 2026-04-23: apenas id=23 retorna CONAMA 001/1986 corretamente;
    # id=745 retornou texto da 001 (não 237); id=489 retornou texto da 372 (não 369).
    # 2026-04-24: 237 via SUDEMA-PB e 369 via CETESB (mirrors oficiais que serviram).
    {
        "url": "https://conama.mma.gov.br/?option=com_sisconama&task=arquivo.download&id=23",
        "title": "Resolução CONAMA 001/1986 — EIA/RIMA",
        "identifier": "Res. CONAMA 001/1986",
        "source_type": "resolucao",
        "agency": "CONAMA",
        "effective_date": "1986-01-23",
        "demand_types": ["licenciamento"],
        # Palavra-chave que precisa aparecer no texto para confirmar que bateu com o diploma certo
        "validation_keyword": "Resolução CONAMA nº 1",
    },
    {
        # Testadas em 2026-04-24: IBAMA sophia (403), egov.df.gov.br (SSL quebrado),
        # conama.mma.gov.br/sisconama (timeout). SUDEMA-PB (Plone @@download) funciona.
        "url": "https://sudema.pb.gov.br/servicos/servicos-ao-publico/legislacao-ambienta/projur/resolucao-no-237-conama-licenciamento-ambiental.pdf/@@download/file",
        "title": "Resolução CONAMA 237/1997 — Licenciamento Ambiental",
        "identifier": "Res. CONAMA 237/1997",
        "source_type": "resolucao",
        "agency": "CONAMA",
        "effective_date": "1997-12-19",
        "demand_types": ["licenciamento"],
        "validation_keyword": "19 de dezembro de 1997",
    },
    {
        # CETESB (mirror oficial do órgão ambiental paulista).
        "url": "https://licenciamento.cetesb.sp.gov.br/legislacao/federal/resolucoes/2006_res_conama_369.pdf",
        "title": "Resolução CONAMA 369/2006 — Intervenção/Supressão em APP",
        "identifier": "Res. CONAMA 369/2006",
        "source_type": "resolucao",
        "agency": "CONAMA",
        "effective_date": "2006-03-28",
        "demand_types": ["licenciamento", "compensacao"],
        "validation_keyword": "28 de março de 2006",
    },
]


# ---------------------------------------------------------------------------
# PACOTE A — direito sancionador e processual federal (2026-07-31)
# ---------------------------------------------------------------------------
# Campos novos, todos opcionais (entrada sem eles se comporta exatamente como
# a lista curada de 2026-04-23):
#   vigencia_inicio / vigencia_fim  — vigência da NORMA (fim=None → vigente)
#   sucessora_ref                   — quem a substituiu, mesmo fora do corpus
#   nota                            — por que ela está aqui
#   fonte_origem / fonte_oficial    — DE ONDE VEIO O TEXTO. O sistema cita norma
#                                     em peça que a consultora assina; "de onde
#                                     veio esse texto" precisa ter resposta.
#                                     Gravado em `extra_metadata`.
CURADORIA_PACOTE_A: list[dict] = [
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2008/decreto/d6514.htm",
        "title": "Infrações e sanções administrativas ao meio ambiente (Decreto 6.514/2008)",
        "identifier": "Decreto 6.514/2008",
        "source_type": "decreto",
        "agency": "Presidência da República",
        "effective_date": "2008-07-22",
        "vigencia_inicio": "2008-07-22",
        "demand_types": ["defesa", "licenciamento"],
        "validation_keyword": "6.514",
        "nota": (
            "A norma do art. 18, §1º que fundamenta a certidão de embargo do caso 15. "
            "Estava citada em 102 chunks do corpus e em nenhum deles com texto próprio."
        ),
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/decreto/d3179.htm",
        "title": "Sanções administrativas ao meio ambiente (Decreto 3.179/1999)",
        "identifier": "Decreto 3.179/1999",
        "source_type": "decreto",
        "agency": "Presidência da República",
        "effective_date": "1999-09-21",
        "vigencia_inicio": "1999-09-21",
        "vigencia_fim": "2008-07-22",
        "sucessora_ref": "Decreto 6.514/2008",
        "demand_types": ["defesa"],
        "validation_keyword": "3.179",
        "nota": (
            "REVOGADA. É o enquadramento literal do auto 484341/D (2007): "
            "'Art. 25 c/c Art. 2º, II, VII e XI do Decreto 3.179'. Sem ela não há "
            "como discutir a autuação nos termos em que ela foi feita."
        ),
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l4771.htm",
        "title": "Código Florestal de 1965 (Lei 4.771/1965)",
        "identifier": "Lei 4.771/1965",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "1965-09-15",
        "vigencia_inicio": "1965-09-15",
        "vigencia_fim": "2012-05-25",
        "sucessora_ref": "Lei 12.651/2012",
        "demand_types": ["defesa", "car"],
        "validation_keyword": "4.771",
        "nota": (
            "REVOGADA pelo Código Florestal de 2012. O auto invoca o 'Art. 2º, c da "
            "Lei 4.771/65' — a definição de APP vigente em 2007."
        ),
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l9784.htm",
        "title": "Processo administrativo na Administração Pública Federal (Lei 9.784/1999)",
        "identifier": "Lei 9.784/1999",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "1999-01-29",
        "vigencia_inicio": "1999-01-29",
        "demand_types": ["defesa"],
        "validation_keyword": "9.784",
        "nota": (
            "Prazos, nulidade, recurso e prescrição intercorrente. É a régua "
            "processual de toda defesa federal e estava com 0 chunks próprios."
        ),
    },
    {
        "url": "https://www.legisweb.com.br/legislacao/?id=277984",
        "title": "Apuração de infrações ambientais no IBAMA (IN IBAMA 10/2012)",
        "identifier": "IN IBAMA 10/2012",
        "source_type": "instrucao_normativa",
        "agency": "IBAMA",
        "effective_date": "2012-12-07",
        "vigencia_inicio": "2012-12-07",
        "vigencia_fim": "2020-01-29",
        "sucessora_ref": "IN Conjunta MMA/IBAMA/ICMBio 02/2020 (rito atual: IN IBAMA 19/2023)",
        "demand_types": ["defesa"],
        # O portal do IBAMA responde 403 a cliente não-browser e o mirror óbvio
        # do LegisWeb (id=245167) serve OUTRA norma — uma resolução da SEFAZ-AM.
        # A keyword é o que impede essa troca silenciosa de virar corpus.
        "validation_keyword": "Instrução Normativa IBAMA Nº 10 DE 07/12/2012",
        # Moldura do agregador: menu antes, aviso de LGPD depois.
        "corte_inicio": "Instrução Normativa IBAMA Nº 10 DE 07/12/2012",
        "corte_fim": "Utilizamos cookies",
        "nota": (
            "REVOGADA. Regia o rito do processo administrativo do IBAMA entre 2012 "
            "e 2020 — inclusive o julgamento 067-2012 do caso 15."
        ),
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/mpv/mpv780.htm",
        "title": "Programa de Regularização de Débitos não tributários — PRD (MPV 780/2017)",
        "identifier": "MPV 780/2017",
        "source_type": "lei",
        "agency": "Presidência da República",
        "effective_date": "2017-05-19",
        "vigencia_inicio": "2017-05-19",
        "vigencia_fim": "2017-10-24",
        # Só o identifier, sem aposto: `sucessora_ref` é o que casa com a
        # sucessora no corpus para virar FK. "Lei 13.494/2017 (conversão)" não
        # casa com "Lei 13.494/2017" e o elo cai para texto — a norma está lá e
        # a ligação se perde em silêncio. O aposto vive na nota.
        "sucessora_ref": "Lei 13.494/2017",
        "demand_types": ["defesa"],
        "validation_keyword": "780",
        "nota": (
            "REVOGADA por CONVERSÃO em lei (Lei 13.494/2017). O requerimento de adesão ao REFIZ do "
            "caso 15 (2017) se funda no 'artigo 02 da MPV 780/2017' — é a norma "
            "sob a qual o pedido foi feito."
        ),
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/lei/l13494.htm",
        "title": "Programa de Regularização de Débitos não tributários (Lei 13.494/2017)",
        "identifier": "Lei 13.494/2017",
        "source_type": "lei",
        "agency": "Congresso Nacional",
        "effective_date": "2017-10-24",
        "vigencia_inicio": "2017-10-24",
        "demand_types": ["defesa"],
        "validation_keyword": "13.494",
        "nota": "Conversão da MPV 780/2017 — o que de fato vigora sobre a adesão.",
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/decreto/d11373.htm",
        "title": "Conciliação ambiental e alterações no Decreto 6.514 (Decreto 11.373/2023)",
        "identifier": "Decreto 11.373/2023",
        "source_type": "decreto",
        "agency": "Presidência da República",
        "effective_date": "2023-01-01",
        "vigencia_inicio": "2023-01-01",
        "demand_types": ["defesa"],
        "validation_keyword": "11.373",
        "nota": (
            "Caminho de saída atual para auto antigo ainda em curso — o do caso 15 "
            "corre desde 2007."
        ),
    },
    {
        # Decisão de 31/07: a defesa se protocola HOJE, sob o rito de hoje.
        # Ingerir só a IN 10/2012 entregaria meia verdade na peça assinada.
        "url": (
            "https://www.in.gov.br/en/web/dou/-/"
            "instrucao-normativa-n-19-de-2-de-junho-de-2023-488485031"
        ),
        "title": (
            "Processo administrativo de apuração de infrações ambientais no IBAMA "
            "(IN IBAMA 19/2023)"
        ),
        "identifier": "IN IBAMA 19/2023",
        "source_type": "instrucao_normativa",
        "agency": "IBAMA",
        "effective_date": "2023-06-07",
        "vigencia_inicio": "2023-06-07",
        "demand_types": ["defesa"],
        "validation_keyword": "INSTRUÇÃO NORMATIVA",
        "nota": (
            "Rito VIGENTE do processo administrativo do IBAMA — e a norma que traz "
            "prescrição quinquenal e intercorrente trienal, decisivas num auto que "
            "corre desde 2007. Sucede a IN 10/2012 (via IN Conjunta 02/2020 e 01/2021)."
        ),
    },
]


# Domínio → como chamar a fonte, e se ela é oficial. A proveniência é derivada
# da URL (e não digitada entrada a entrada) para que não exista documento novo
# sem origem declarada: fonte desconhecida cai no rótulo explícito de
# desconhecida, nunca em silêncio.
_PROVENIENCIA: list[tuple[str, str, bool]] = [
    ("planalto.gov.br", "Planalto — Presidência da República (oficial)", True),
    ("in.gov.br", "DOU — Imprensa Nacional (oficial)", True),
    ("conama.mma.gov.br", "CONAMA/MMA (oficial)", True),
    (".gov.br", "portal .gov.br (oficial)", True),
    ("legisweb.com.br", "LegisWeb — fonte não-oficial", False),
]


def _proveniencia(entry: dict) -> tuple[str, bool]:
    """De onde veio o texto, e se a fonte é oficial."""
    if entry.get("fonte_origem"):
        return entry["fonte_origem"], bool(entry.get("fonte_oficial", False))
    url = (entry.get("url") or "").lower()
    for agulha, rotulo, oficial in _PROVENIENCIA:
        if agulha in url:
            return rotulo, oficial
    return "origem não identificada — conferir antes de citar", False


def _data(valor: str | None):
    """'2008-07-22' → date. None passa reto."""
    from datetime import date as _date  # noqa: PLC0415

    if not valor:
        return None
    ano, mes, dia = (int(p) for p in valor.split("-"))
    return _date(ano, mes, dia)


def process_one(entry: dict, preview_dir: Path, dry_run: bool, indexar: bool = False) -> dict:
    import httpx

    info: dict = {
        "identifier": entry["identifier"],
        "url": entry["url"],
    }
    try:
        logger.info("Baixando %s ...", entry["identifier"])
        ctype, raw = load_from_url(entry["url"])
        info["content_type"] = ctype
    except httpx.HTTPError as exc:
        info["action"] = "failed_download"
        info["error"] = str(exc)
        return info

    text = sanitize_text(raw)
    if len(text) < 500:
        info["action"] = "failed_short"
        info["chars"] = len(text)
        return info

    # Corte de moldura do site (agregador serve o texto embrulhado em menu e
    # aviso de cookie). Sem isso, "Página Inicial / Legislações / Voltar" vira
    # chunk — e chegou a ser o trecho MAIS similar da busca de defesa federal.
    inicio = entry.get("corte_inicio")
    if inicio:
        pos = text.find(inicio)
        if pos > 0:
            text = text[pos:]
    fim = entry.get("corte_fim")
    if fim:
        pos = text.find(fim)
        if pos > 0:
            text = text[:pos]
    text = text.strip()

    # Canário de encoding: melhor não ingerir do que ingerir texto corrompido
    # que a consultora vai citar numa peça assinada.
    sujeira = verificar_mojibake(text)
    if sujeira > 0.0005:
        info["action"] = "failed_encoding"
        info["chars"] = len(text)
        info["error"] = (
            f"{sujeira:.2%} do texto é caractere de substituição (U+FFFD) — "
            "charset mal detectado; conferir a fonte antes de ingerir"
        )
        return info

    # Validação de conteúdo: se passou keyword, verificar que aparece no texto
    keyword = entry.get("validation_keyword")
    if keyword and keyword.lower() not in text.lower():
        info["action"] = "failed_validation"
        info["error"] = f"keyword {keyword!r} nao encontrada no texto baixado"
        info["chars"] = len(text)
        return info

    info["chars"] = len(text)
    info["tokens"] = estimate_tokens(text)
    preview_path = save_preview(entry["identifier"], text, preview_dir)
    info["preview"] = str(preview_path)

    if dry_run:
        # Chunking DE VERDADE (é local e grátis) — o dry-run informa quantos
        # chunks vão nascer e quanto custa embedá-los, em vez de estimar por
        # regra de três. Nada é gravado e nenhuma API é chamada.
        from app.services.chunking import chunk_text  # noqa: PLC0415

        pedacos = chunk_text(text)
        info["chunks"] = len(pedacos)
        info["chunk_tokens"] = sum(c.tokens for c in pedacos)
        info["fonte_origem"], info["fonte_oficial"] = _proveniencia(entry)
        info["action"] = "dry_run"
        return info

    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models.legislation import LegislationDocument  # noqa: PLC0415

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    effective = datetime.strptime(entry["effective_date"], "%Y-%m-%d").replace(tzinfo=UTC)
    fonte_origem, fonte_oficial = _proveniencia(entry)

    db = SessionLocal()
    try:
        existing = (
            db.query(LegislationDocument)
            .filter(LegislationDocument.identifier == entry["identifier"])
            .all()
        )
        for doc in existing:
            if doc.content_hash == content_hash and doc.status == "indexed":
                info["action"] = "skipped_duplicate"
                info["db_id"] = doc.id
                return info
        for doc in existing:
            if doc.status == "indexed":
                doc.status = "superseded"
                doc.revoked_at = datetime.now(UTC)

        new_doc = LegislationDocument(
            title=entry["title"],
            identifier=entry["identifier"],
            scope="federal",
            source_type=entry["source_type"],
            agency=entry.get("agency"),
            uf=None,
            municipality=None,
            effective_date=effective,
            url=entry["url"],
            file_path=None,
            full_text=text,
            token_count=info["tokens"],
            content_hash=content_hash,
            status="indexed",
            demand_types=entry["demand_types"],
            # ADR-037 — vigência da norma. Entrada da lista antiga não traz
            # estes campos e segue exatamente como antes (tudo NULL = vigente).
            vigencia_inicio=_data(entry.get("vigencia_inicio")),
            vigencia_fim=_data(entry.get("vigencia_fim")),
            sucessora_ref=entry.get("sucessora_ref"),
            # Proveniência (31/07): de onde veio este texto. Substituível — o dia
            # em que a fonte oficial da IN 10/2012 chegar, troca-se aqui.
            extra_metadata={
                "fonte_origem": fonte_origem,
                "fonte_oficial": fonte_oficial,
                "fonte_url": entry["url"],
                "nota_curadoria": entry.get("nota"),
            },
        )
        db.add(new_doc)
        db.flush()

        # Sucessora que ESTÁ no corpus vira FK; a que não está permanece só
        # nomeada em `sucessora_ref`. Nunca inventar o elo.
        ref = entry.get("sucessora_ref")
        if ref:
            sucessora = (
                db.query(LegislationDocument)
                .filter(
                    LegislationDocument.identifier == ref,
                    LegislationDocument.status == "indexed",
                )
                .first()
            )
            if sucessora is not None:
                new_doc.sucessora_id = sucessora.id
                info["sucessora_id"] = sucessora.id

        db.commit()
        info["action"] = "inserted"
        info["db_id"] = new_doc.id
        info["historica"] = bool(entry.get("vigencia_fim"))
        info["fonte_origem"] = fonte_origem
        info["fonte_oficial"] = fonte_oficial

        # Indexação no knowledge_catalog. O script original parava no documento
        # e o chunking vinha depois, por outro comando — foi assim que a Sprint 0
        # deixou documento e corpus desencontrados. Aqui é um passo só.
        if indexar:
            from app.services.knowledge_catalog import (  # noqa: PLC0415
                index_legislation_document,
            )

            info["chunks"] = index_legislation_document(db, new_doc.id)
            db.commit()
        return info
    finally:
        db.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--preview-dir", type=Path, default=Path("ops/legislation_preview"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", help="Substring do identifier (ex: 12.651)")
    p.add_argument(
        "--pacote",
        choices=["canonicos", "a"],
        default="canonicos",
        help="canonicos = lista de 2026-04-23 (padrão); a = direito sancionador/processual",
    )
    p.add_argument(
        "--sem-indexar",
        action="store_true",
        help="grava o documento e NÃO indexa no knowledge_catalog",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    entries = CURADORIA_PACOTE_A if args.pacote == "a" else CURATED_FEDERAIS
    if args.only:
        entries = [e for e in entries if args.only.lower() in e["identifier"].lower()]

    indexar = not args.sem_indexar and args.pacote == "a"
    results = []
    for entry in entries:
        try:
            r = process_one(entry, args.preview_dir, args.dry_run, indexar=indexar)
        except Exception as exc:
            logger.exception("Falha ao processar %s", entry["identifier"])
            r = {"identifier": entry["identifier"], "action": "failed_exception", "error": str(exc)}
        results.append(r)
        logger.info(
            "→ %s | action=%s chars=%s tokens=%s db_id=%s",
            r.get("identifier"), r.get("action"), r.get("chars"), r.get("tokens"), r.get("db_id"),
        )

    print(f"\n=== RESUMO — pacote {args.pacote} ===")
    print(
        f"{'identifier':<24} {'ação':<18} {'chars':>9} {'chunks':>7} "
        f"{'tok/chunk':>10}  vigência"
    )
    for r in results:
        vig = ""
        entrada = next((e for e in entries if e["identifier"] == r.get("identifier")), {})
        if entrada.get("vigencia_fim"):
            vig = f"HISTÓRICA (até {entrada['vigencia_fim']}) → {entrada.get('sucessora_ref', '?')}"
        elif entrada.get("vigencia_inicio"):
            vig = f"vigente (desde {entrada['vigencia_inicio']})"
        print(
            f"{str(r.get('identifier')):<24} {str(r.get('action')):<18} "
            f"{(r.get('chars') or 0):>9,} {(r.get('chunks') or 0):>7} "
            f"{(r.get('chunk_tokens') or 0):>10,}  {vig}"
        )
        selo = "oficial" if r.get("fonte_oficial") else "NÃO-OFICIAL"
        print(f"{'':<24} fonte: {r.get('fonte_origem')} [{selo}]")
        if r.get("error"):
            print(f"    ERRO: {r['error']}")

    summary: dict[str, int] = {}
    total_tokens = total_chars = total_chunks = total_chunk_tokens = 0
    for r in results:
        summary[r["action"]] = summary.get(r["action"], 0) + 1
        total_tokens += r.get("tokens") or 0
        total_chars += r.get("chars") or 0
        total_chunks += r.get("chunks") or 0
        total_chunk_tokens += r.get("chunk_tokens") or 0

    print("\n  " + " · ".join(f"{a}: {c}" for a, c in sorted(summary.items())))
    print(f"  chars: {total_chars:,} | tokens do texto: {total_tokens:,}")
    print(f"  chunks: {total_chunks:,} | tokens a embedar: {total_chunk_tokens:,}")
    # text-embedding-3-small: US$ 0,02 por 1M tokens (app/services/embeddings.py).
    print(f"  custo de embedding estimado: US$ {total_chunk_tokens / 1_000_000 * 0.02:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
