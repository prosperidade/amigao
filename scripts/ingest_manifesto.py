"""
scripts/ingest_manifesto.py — ingestor dirigido por curadoria (ADR-038).

Substitui a lista fixa escrita à mão de `ingest_federais_canonicos.py`. A fonte
de verdade passa a ser um manifesto CSV versionado (`data/corpus_manifesto/`),
extraído da curadoria da Isis.

Cada garantia abaixo nasceu de um bug que já pagamos:

 (a) IDEMPOTÊNCIA — mesmo `content_hash` e já indexado ⇒ `skip`, reportado.
 (b) ENCODING — charset real detectado (`_decodificar`) e canário que RECUSA
     acima de 0,05% de U+FFFD. O Planalto responde sem charset e o httpx assumia
     utf-8 sobre ISO-8859-1: mojibake por três meses, calado.
 (c) NORMALIZAÇÃO — U+00A0/U+200B/U+FEFF viram espaço em `sanitize_text`, na
     ingestão; o `content_hash` sai do texto já normalizado.
 (d) VALIDATION_KEYWORD — obrigatória por linha ingerível, conferida no texto
     baixado. É a guarda que pegou o LegisWeb servindo uma resolução da SEFAZ-AM
     no lugar da IN IBAMA 10/2012.
 (e) PROVENIÊNCIA — `fonte_origem`, `fonte_oficial`, `fonte_conferida_em`.
 (f) VIGÊNCIA — norma histórica entra marcada, e o rótulo viaja NO DADO
     (ADR-037): quem receber o trecho recebe o aviso.
 (g) RELATÓRIO POR LINHA — ok / skip / falhou-com-motivo. **Falha de uma linha
     nunca aborta o lote**; ao final, sumário com custo real de embedding.
 (h) DRY-RUN por padrão. `--execute` exige confirmação.

Uso:
    python scripts/ingest_manifesto.py data/corpus_manifesto/nucleo_06.csv
    python scripts/ingest_manifesto.py data/corpus_manifesto/nucleo_06.csv --execute
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("ingest_manifesto")

LIMIAR_MOJIBAKE = 0.0005
MIN_CHARS = 500

# text-embedding-3-small (app/services/embeddings.py)
USD_POR_MILHAO_TOKENS = 0.02


@dataclass
class Resultado:
    identifier: str
    acao: str = ""           # ok | skip | ignorado | falhou
    motivo: str | None = None
    chars: int = 0
    chunks: int = 0
    chunk_tokens: int = 0
    doc_id: int | None = None
    historica: bool = False
    fonte_origem: str | None = None
    observacao_curadoria: str | None = None


@dataclass
class Sumario:
    resultados: list[Resultado] = field(default_factory=list)

    def por_acao(self, acao: str) -> list[Resultado]:
        return [r for r in self.resultados if r.acao == acao]

    @property
    def chunk_tokens(self) -> int:
        return sum(r.chunk_tokens for r in self.resultados)

    @property
    def custo_usd(self) -> float:
        return self.chunk_tokens / 1_000_000 * USD_POR_MILHAO_TOKENS


def processar_linha(session, linha, *, executar: bool) -> Resultado:
    """Uma linha do manifesto. NUNCA levanta — devolve o motivo no resultado.

    É o requisito (g): um portal fora do ar não pode derrubar o lote inteiro.
    """
    from scripts.ingest_legislation import (
        estimate_tokens,
        load_from_url,
        sanitize_text,
        verificar_mojibake,
    )

    from app.services.chunking import chunk_text
    from app.services.proveniencia import classificar_fonte

    res = Resultado(
        identifier=linha.identifier,
        historica=linha.historica,
        observacao_curadoria=linha.observacao_curadoria,
    )

    if not linha.ingerivel:
        res.acao = "ignorado"
        res.motivo = linha.motivo_nao_ingerivel
        return res

    # (b) download com charset real
    try:
        _ctype, bruto = load_from_url(linha.url)
    except Exception as exc:  # noqa: BLE001 — qualquer falha de rede/HTTP
        res.acao = "falhou"
        res.motivo = f"download: {type(exc).__name__}: {str(exc)[:110]}"
        return res

    # (c) normalização acontece dentro de sanitize_text
    texto = sanitize_text(bruto)

    if len(texto) < MIN_CHARS:
        res.acao = "falhou"
        res.motivo = f"texto curto demais ({len(texto)} chars) — página de erro?"
        return res

    # (d) a fonte é MESMO a que se pediu?
    if linha.validation_keyword.lower() not in texto.lower():
        res.acao = "falhou"
        res.motivo = (
            f"validation_keyword {linha.validation_keyword!r} ausente no texto — "
            "fonte trocada ou incompleta"
        )
        res.chars = len(texto)
        return res

    # (b) canário
    sujeira = verificar_mojibake(texto)
    if sujeira > LIMIAR_MOJIBAKE:
        res.acao = "falhou"
        res.motivo = f"{sujeira:.2%} de U+FFFD — charset mal detectado"
        res.chars = len(texto)
        return res

    res.chars = len(texto)
    conteudo_hash = hashlib.sha256(texto.encode("utf-8")).hexdigest()

    from app.models.legislation import LegislationDocument

    existente = (
        session.query(LegislationDocument)
        .filter(LegislationDocument.identifier == linha.identifier)
        .order_by(LegislationDocument.id.desc())
        .first()
    )

    # (a) idempotência
    if existente is not None and existente.content_hash == conteudo_hash \
            and existente.status == "indexed":
        res.acao = "skip"
        res.motivo = "já indexado, conteúdo idêntico"
        res.doc_id = existente.id
        return res

    pedacos = chunk_text(texto)
    res.chunks = len(pedacos)
    res.chunk_tokens = sum(c.tokens for c in pedacos)

    proveniencia = classificar_fonte(url=linha.url)
    res.fonte_origem = proveniencia.origem

    if not executar:
        res.acao = "ok"
        res.motivo = "dry-run"
        return res

    try:
        if existente is not None:
            # UPDATE no MESMO id: preserva quem aponta para ele por
            # `sucessora_id` e não deixa chunk órfão apontando para doc superado.
            from sqlalchemy import text as _sql

            alvo = existente
            session.execute(
                _sql("DELETE FROM knowledge_catalog WHERE source_ref = :ref"),
                {"ref": f"legislation_documents:{existente.id}"},
            )
        else:
            alvo = LegislationDocument(identifier=linha.identifier)
            session.add(alvo)

        alvo.title = linha.titulo
        alvo.scope = linha.esfera
        alvo.uf = linha.uf
        alvo.agency = linha.orgao
        alvo.source_type = "lei"
        alvo.url = linha.url
        alvo.full_text = texto
        alvo.token_count = estimate_tokens(texto)
        alvo.content_hash = conteudo_hash
        alvo.status = "indexed"
        alvo.demand_types = linha.demand_types or ["defesa"]
        # (f) vigência
        alvo.vigencia_inicio = linha.vigencia_inicio
        alvo.vigencia_fim = linha.vigencia_fim
        alvo.sucessora_ref = linha.sucessora_ref
        if linha.vigencia_inicio:
            alvo.effective_date = datetime(
                linha.vigencia_inicio.year, linha.vigencia_inicio.month,
                linha.vigencia_inicio.day, tzinfo=UTC,
            )
        # (e) proveniência
        alvo.fonte_origem = proveniencia.origem
        alvo.fonte_oficial = proveniencia.oficial or linha.fonte_oficial
        alvo.fonte_conferida_em = proveniencia.conferida_em
        alvo.extra_metadata = {
            "bloco": linha.bloco,
            "fonte_origem": proveniencia.origem,
            "fonte_oficial": proveniencia.oficial or linha.fonte_oficial,
            "fonte_url": linha.url,
            "observacao_curadoria": linha.observacao_curadoria,
        }
        session.flush()

        # Sucessora que ESTÁ no corpus vira FK; a que não está fica nomeada.
        if linha.sucessora_ref:
            suc = (
                session.query(LegislationDocument)
                .filter(
                    LegislationDocument.identifier == linha.sucessora_ref,
                    LegislationDocument.status == "indexed",
                )
                .first()
            )
            if suc is not None and suc.id != alvo.id:
                alvo.sucessora_id = suc.id
        session.commit()

        from app.services.knowledge_catalog import index_legislation_document

        res.chunks = index_legislation_document(session, alvo.id)
        session.commit()
        res.doc_id = alvo.id
        res.acao = "ok"
        return res
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        res.acao = "falhou"
        res.motivo = f"persistência: {type(exc).__name__}: {str(exc)[:110]}"
        return res


def executar_manifesto(session, linhas, *, executar: bool) -> Sumario:
    sumario = Sumario()
    for linha in linhas:
        res = processar_linha(session, linha, executar=executar)
        sumario.resultados.append(res)
        logger.info(
            "%-28s %-9s %s", res.identifier, res.acao, res.motivo or f"chunks={res.chunks}"
        )
    return sumario


def imprimir(sumario: Sumario, *, executar: bool) -> None:
    print(f"\n=== MANIFESTO — {'EXECUÇÃO' if executar else 'DRY-RUN (nada gravado)'} ===\n")
    print(f"{'identifier':<30} {'ação':<9} {'chars':>8} {'chunks':>7}  detalhe")
    for r in sumario.resultados:
        marca = "H" if r.historica else " "
        print(
            f"{r.identifier:<30} {r.acao:<9} {r.chars:>8,} {r.chunks:>7} {marca} "
            f"{r.motivo or ''}"
        )

    for rotulo, acao in (("INGERIDAS/PRONTAS", "ok"), ("JÁ NO CORPUS", "skip"),
                         ("FORA DO CORPUS", "ignorado"), ("FALHARAM", "falhou")):
        grupo = sumario.por_acao(acao)
        if grupo:
            print(f"\n{rotulo} ({len(grupo)}):")
            for r in grupo:
                print(f"  · {r.identifier:<30} {r.motivo or ''}")

    pendencias = [r for r in sumario.resultados if r.acao == "falhou" or r.observacao_curadoria]
    if pendencias:
        print("\nPENDÊNCIAS DE CURADORIA (devolver à Isis):")
        for r in pendencias:
            nota = r.observacao_curadoria or r.motivo
            print(f"  · {r.identifier:<30} {nota}")

    print(f"\n  chunks: {sum(r.chunks for r in sumario.resultados):,}")
    print(f"  tokens a embedar: {sumario.chunk_tokens:,}")
    print(f"  custo de embedding: US$ {sumario.custo_usd:.4f}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("manifesto", type=Path)
    p.add_argument("--execute", action="store_true", help="grava (padrão: dry-run)")
    p.add_argument("--sim", action="store_true", help="confirma o --execute sem perguntar")
    p.add_argument("--only", help="substring do identifier")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from app.services.manifesto_corpus import carregar_manifesto

    linhas = carregar_manifesto(args.manifesto)
    if args.only:
        linhas = [linha for linha in linhas if args.only.lower() in linha.identifier.lower()]
    print(f"manifesto: {args.manifesto}  ({len(linhas)} linhas)")

    if args.execute and not args.sim:
        alvo = [linha for linha in linhas if linha.ingerivel]
        resposta = input(f"Gravar {len(alvo)} normas no corpus? [digite: sim] ")
        if resposta.strip().lower() != "sim":
            print("abortado.")
            return 1

    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        sumario = executar_manifesto(session, linhas, executar=args.execute)
        imprimir(sumario, executar=args.execute)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
