"""Gate OCR-003 — o OCR contra o ARQUIVO ORIGINAL, não contra o texto dele.

Por que existe
--------------
OCR-001 e OCR-002 foram fechados sobre `extracted_text` (o texto que já estava
no banco) ou sobre PDF reconstruído a partir dele. Os dois provam que o
pipeline lê um PDF *sintético* — nunca que lê o PDF que a consultora anexou.
A lição já está registrada em `reference_gemini_ocr_multipage`: "síntese
pequena não reproduz scan real". Este script fecha a lacuna: baixa o original
do storage, roda a cascata REAL (pypdf → Gemini Vision → OpenAI Vision) e
compara com o que a produção gravou.

Ele responde as TRÊS perguntas com veredito, não com tabela para alguém julgar
depois (auditoria de 12/09 — a primeira versão só media):

1. o texto do OCR bate com o `extracted_text` de produção?
   → similaridade normalizada contra `LIMIAR_SIMILARIDADE`, APROVADO/REPROVADO.
2. as áreas saem iguais?
   → comparação NUMÉRICA (via `parse_area_ha`, a porta única do projeto) das
     quatro matrículas do #23 e do total. Notação registral `926,36.54`
     (926 ha, 36 a, 54 ca) é o MESMO número que `926,3654` e a comparação por
     string não via isso — foi exatamente o defeito que a auditoria apontou.
3. o doc 551 continua ilegível?
   → procura nome do representante e marcas de CNH no texto do OCR. Se o
     Vision ler, o gate DIZ que leu: é achado, não escopo.

E antes de tudo: confere o SHA-256 dos bytes baixados contra o
`checksum_sha256` do registro de produção. Sem isso, todo o resto pode estar
comparando outro arquivo.

O que NÃO faz
-------------
Não toca banco nenhum — nem o de produção nem um descartável. `extract_text_
from_pdf` é função pura sobre bytes; o lado "produção" da comparação entra por
arquivo (`--producao`), exportado antes. Assim o gate não tem como escrever
onde não deve.

Credencial: NADA precisa ir para disco
--------------------------------------
Medido (12/09): `Settings` é pydantic-settings com `env_file=".env"`, e nessa
biblioteca **variável de ambiente vence arquivo**. Com o `.env` de dev dizendo
`MINIO_SERVER=localhost:9000`, rodar com a variável exportada dá o endpoint da
variável. É a mesma ergonomia do `PGPASSWORD` do `pg_dump`: a credencial vive
no comando, não no disco, e o `.env` de dev fica intocado.

    # PowerShell — a credencial existe só enquanto o processo roda
    $env:MINIO_SERVER="<acct>.r2.cloudflarestorage.com"
    $env:MINIO_ACCESS_KEY="..."; $env:MINIO_SECRET_KEY="..."
    $env:MINIO_SECURE="True"   # S3_REGION já tem default "auto" (R2 exige)
    python scripts/gate_ocr_originais.py --producao docs23_prod.json

`--env-file` existe para quem prefere não colar segredo no terminal (o
histórico do shell guarda). Ele carrega o arquivo APONTADO, com `override`,
antes de o `app.core.config` ser importado — nunca o `.env` padrão.

Qualquer `.env.*` já está bloqueado pelo `.gitignore` (linha 34), com allowlist
só para os `.example` — conferido com `git check-ignore`, não presumido.

Leitura é leitura
-----------------
`StorageService.download_bytes` NÃO chama `_ensure_bucket_exists` (só
`upload_file`/`upload_bytes` chamam, e é lá que mora o `create_bucket`).
Credencial de leitura pura basta, e este gate não tem como criar bucket.

O lado de produção
------------------
`--producao` é um JSON exportado do banco:
`[{"id": 546, "storage_key": "...", "original_file_name": "...",
   "checksum_sha256": "...", "extracted_text": "...", "ocr_status": "done"}, ...]`

Saída: veredito por documento + veredito final, e um JSON com tudo para
conferência linha a linha.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Abaixo disto, o texto do OCR não é "o mesmo documento com outro espaçamento".
# 0,90 depois de normalizar espaço e caixa: pypdf e Vision quebram linha de
# formas diferentes, e isso sozinho já come alguns pontos.
LIMIAR_SIMILARIDADE = 0.90

# As quatro matrículas do caso #23 e suas áreas, como a Frente K as mediu na
# base depois da consolidação (soma = 2180,3923 = `area_total_matriculas`).
MATRICULAS_23 = {
    "3181": 926.3654,
    "3313": 725.4663,
    "3673": 212.3553,
    "4387": 316.2053,
}
TOTAL_23 = 2180.3923

# Tolerância de comparação: MEIO centiare (1 ca = 0,0001 ha). Serve para
# absorver ruído de float, não para aceitar diferença real — com 0,0001 cheio,
# `926,3655` passava como `926,3654`, e um centiare a mais é outra área.
TOLERANCIA_HA = 0.00005

# Doc 551 — CNH-e do representante (dívida #223: OCR devolveu 444 chars de
# boilerplate de assinatura digital, zero nome/CPF). Se o Vision ler o
# conteúdo, isto aparece.
DOC_REPRESENTANTE = 551
MARCAS_REPRESENTANTE = ("joel", "carteira nacional de habilitação", "cpf", "doc. identidade")

# Qualquer coisa que se pareça com número decimal brasileiro, inclusive a
# notação registral com ares/centiares depois do ponto ("926,36.54").
_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})*,\d+(?:\.\d+)?|\b\d+,\d+(?:\.\d+)?")


def _normalizar(texto: str) -> str:
    """Espaço e caixa fora — o que resta é o conteúdo.

    Sem isto a comparação mede formatação de quebra de linha, que muda entre
    pypdf e Vision sem que uma palavra sequer tenha mudado.
    """
    return re.sub(r"\s+", " ", (texto or "")).strip().lower()


def _similaridade(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def _numeros_em_hectares(texto: str) -> list[float]:
    """Todo número do texto, lido como área pela porta única do projeto.

    `parse_area_ha` já entende `926,3654`, `926,36.54` (registral antiga) e
    `2.180,3923`. Comparar STRING era o defeito da primeira versão deste gate:
    `926,36.54` e `926,3654` são o mesmo número e saíam como "não encontrado".
    """
    from app.services.inconsistency_matrix import parse_area_ha

    valores = []
    for bruto in _NUMERO.findall(texto or ""):
        try:
            v = parse_area_ha(bruto)
        except Exception:  # noqa: BLE001 — token que não é área não interessa
            v = None
        if v is not None:
            valores.append(float(v))
    return valores


def _areas_presentes(texto: str, esperadas: dict[str, float]) -> dict[str, bool]:
    """Para cada área esperada, ela aparece no texto (numericamente)?"""
    achados = _numeros_em_hectares(texto)
    return {
        rotulo: any(abs(v - alvo) <= TOLERANCIA_HA for v in achados)
        for rotulo, alvo in esperadas.items()
    }


def _matriculas_presentes(texto: str) -> dict[str, bool]:
    """Os quatro números de matrícula aparecem? (com e sem separador de milhar)"""
    t = _normalizar(texto)
    return {
        n: (n in t.replace(".", "")) or (f"{n[:-3]}.{n[-3:]}" in t)
        for n in MATRICULAS_23
    }


def _le_o_representante(texto: str) -> list[str]:
    t = _normalizar(texto)
    return [m for m in MARCAS_REPRESENTANTE if m in t]


def _diferencas(prod: str, ocr: str, limite: int = 3) -> list[str]:
    """As maiores diferenças, para quem for conferir à mão."""
    a, b = _normalizar(prod), _normalizar(ocr)
    saida = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        saida.append(f"{tag}: prod[{i1}:{i2}]={a[i1:i2][:60]!r} ocr[{j1}:{j2}]={b[j1:j2][:60]!r}")
        if len(saida) >= limite:
            break
    return saida


def _esperadas_para(doc_id: int, documentos: list[dict]) -> dict[str, float]:
    """Quais áreas cobrar deste documento.

    Um documento só pode conter a área que ele declara. Cobrar as quatro de
    todos produziria "reprovado" em documento que nunca falou daquela
    matrícula — reprovação por pergunta errada.
    """
    prod = next((d for d in documentos if d["id"] == doc_id), None)
    texto = (prod or {}).get("extracted_text") or ""
    presentes = _areas_presentes(texto, {**MATRICULAS_23, "total": TOTAL_23})
    return {
        rotulo: (TOTAL_23 if rotulo == "total" else MATRICULAS_23[rotulo])
        for rotulo, tem in presentes.items() if tem
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate OCR-003 — OCR sobre o arquivo original")
    ap.add_argument("--producao", required=True, type=pathlib.Path,
                    help="JSON com id/storage_key/checksum/extracted_text de produção")
    ap.add_argument("--saida", type=pathlib.Path, default=pathlib.Path("."),
                    help="diretório onde gravar o resultado")
    ap.add_argument("--apenas", type=int, nargs="*", default=None,
                    help="rodar só estes ids de documento")
    ap.add_argument("--env-file", type=pathlib.Path, default=None,
                    help="arquivo de credenciais a carregar (NUNCA o .env padrão)")
    args = ap.parse_args()

    # A carga acontece ANTES de qualquer import de `app.*`: `Settings` é
    # instanciada no import de `app.core.config` e lê o ambiente uma vez só.
    # `override=True` porque o ponto do arquivo é justamente sobrepor o `.env`
    # de dev — sem isso o gate falaria com o MinIO local achando que fala com
    # o R2.
    if args.env_file:
        if not args.env_file.is_file():
            print(f"--env-file: {args.env_file} não existe.", file=sys.stderr)
            return 2
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=True)

    from app.core.config import settings
    from app.services.ocr_pdf import extract_text_from_pdf
    from app.services.storage import BUCKET_NAME, StorageDownloadError, get_storage_service

    documentos = json.loads(args.producao.read_text(encoding="utf-8"))
    alvo = [d for d in documentos if not args.apenas or d["id"] in args.apenas]

    storage = get_storage_service()
    endpoint = settings.minio_internal_endpoint

    # Pré-voo. `download_bytes` devolve b"" tanto para NoSuchKey quanto para
    # NoSuchBucket — então, sem esta checagem, um nome de bucket errado sairia
    # na tabela como "arquivo ausente no storage": conclusão errada vestida de
    # achado. O gate pergunta pelo BUCKET primeiro e para se não o alcança.
    # (A conflação dentro de `download_bytes` é a dívida #228.)
    print(f"endpoint : {endpoint}")
    print(f"bucket   : {BUCKET_NAME}")
    provedores = {d.get("storage_provider") for d in alvo if d.get("storage_provider")}
    if provedores and "localhost" in endpoint and provedores != {"minio"}:
        print(
            f"PARADO: os documentos dizem storage_provider={sorted(provedores)} e o "
            f"endpoint efetivo é {endpoint}. Passe a credencial de produção "
            "(variáveis de ambiente ou --env-file) — ler o storage errado daria "
            "uma tabela de ausências falsas.",
            file=sys.stderr,
        )
        return 2
    try:
        storage.s3_client.head_bucket(Bucket=BUCKET_NAME)
    except Exception as exc:  # noqa: BLE001 — o pré-voo relata qualquer causa
        print(
            f"PARADO: não foi possível alcançar o bucket {BUCKET_NAME} em {endpoint}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    args.saida.mkdir(parents=True, exist_ok=True)
    resultados = []
    print(f"\n{len(alvo)} documento(s)\n" + "=" * 78)

    for d in alvo:
        linha: dict = {
            "id": d["id"],
            "arquivo": d.get("original_file_name"),
            "storage_key": d.get("storage_key"),
            "prod_chars": len(d.get("extracted_text") or ""),
            "prod_ocr_status": d.get("ocr_status"),
        }
        print(f"\ndoc {d['id']} — {d.get('original_file_name')}")

        try:
            bytes_originais = storage.download_bytes(d["storage_key"])
        except StorageDownloadError as exc:
            linha.update(veredito="INCONCLUSIVO", motivo=f"download falhou: {exc.code}")
            resultados.append(linha)
            print(f"  INCONCLUSIVO — download falhou ({exc.code})")
            continue

        if not bytes_originais:
            linha.update(veredito="INCONCLUSIVO", motivo="objeto não existe no storage")
            resultados.append(linha)
            print("  INCONCLUSIVO — arquivo ausente no storage")
            continue

        # (0) É o mesmo arquivo que a produção registrou?
        sha = hashlib.sha256(bytes_originais).hexdigest()
        sha_prod = d.get("checksum_sha256")
        linha.update(bytes=len(bytes_originais), sha256_baixado=sha, sha256_producao=sha_prod)
        if sha_prod and sha_prod != sha:
            linha.update(
                veredito="INCONCLUSIVO",
                motivo="checksum do objeto ≠ checksum registrado em produção — "
                       "a comparação seria sobre OUTRO arquivo",
            )
            resultados.append(linha)
            print(f"  INCONCLUSIVO — checksum diverge (prod={sha_prod[:12]}… baixado={sha[:12]}…)")
            continue
        linha["checksum"] = "confere" if sha_prod else "produção não registrou checksum"

        resultado = extract_text_from_pdf(
            bytes_originais, d.get("mime_type") or "application/pdf"
        )
        texto_prod = d.get("extracted_text") or ""
        sim = _similaridade(texto_prod, resultado.text)
        esperadas = _esperadas_para(d["id"], documentos)
        areas_prod = _areas_presentes(texto_prod, esperadas)
        areas_ocr = _areas_presentes(resultado.text, esperadas)
        matr_prod = _matriculas_presentes(texto_prod)
        matr_ocr = _matriculas_presentes(resultado.text)

        areas_iguais = areas_prod == areas_ocr
        matriculas_iguais = matr_prod == matr_ocr
        texto_bate = sim >= LIMIAR_SIMILARIDADE

        linha.update(
            ocr_metodo=resultado.method, ocr_modelo=resultado.model_used,
            ocr_chars=resultado.chars, ocr_custo_usd=resultado.cost_usd,
            ocr_erro=resultado.error,
            similaridade=round(sim, 4), limiar=LIMIAR_SIMILARIDADE,
            areas_esperadas=esperadas,
            areas_producao=areas_prod, areas_ocr=areas_ocr,
            matriculas_producao=matr_prod, matriculas_ocr=matr_ocr,
        )

        if d["id"] == DOC_REPRESENTANTE:
            marcas_prod = _le_o_representante(texto_prod)
            marcas_ocr = _le_o_representante(resultado.text)
            linha.update(representante_producao=marcas_prod, representante_ocr=marcas_ocr)
            if marcas_ocr and not marcas_prod:
                linha["achado"] = (
                    "O OCR sobre o ARQUIVO leu o representante que produção não tem "
                    f"(marcas: {marcas_ocr}). Dívida #223 muda de causa: não era "
                    "PDF ilegível, era a leitura anterior. ENTRA COMO ACHADO."
                )
                print(f"  ACHADO: {linha['achado']}")
            elif not marcas_ocr:
                linha["achado"] = (
                    "doc 551 segue ilegível também sobre o arquivo original — "
                    "confirma o limite; a dívida #223 é do documento, não do pipeline."
                )
                print(f"  {linha['achado']}")

        if texto_bate and areas_iguais and matriculas_iguais:
            linha["veredito"] = "APROVADO"
        else:
            linha["veredito"] = "REPROVADO"
            linha["motivo"] = "; ".join(filter(None, [
                None if texto_bate else f"similaridade {sim:.2%} < {LIMIAR_SIMILARIDADE:.0%}",
                None if areas_iguais else f"áreas divergem (prod={areas_prod} ocr={areas_ocr})",
                None if matriculas_iguais else
                    f"matrículas divergem (prod={matr_prod} ocr={matr_ocr})",
            ]))
            linha["diferencas"] = _diferencas(texto_prod, resultado.text)

        (args.saida / f"doc_{d['id']}_ocr_real.txt").write_text(
            resultado.text or "", encoding="utf-8"
        )
        resultados.append(linha)
        print(
            f"  {linha['veredito']}  [{resultado.method}/{resultado.model_used or '-'}]  "
            f"prod={linha['prod_chars']}ch ocr={resultado.chars}ch  sim={sim:.2%}  "
            f"checksum={linha['checksum']}"
        )
        if linha["veredito"] == "REPROVADO":
            print(f"      motivo: {linha['motivo']}")

    aprovados = [r for r in resultados if r.get("veredito") == "APROVADO"]
    reprovados = [r for r in resultados if r.get("veredito") == "REPROVADO"]
    inconclusivos = [r for r in resultados if r.get("veredito") == "INCONCLUSIVO"]
    final = "APROVADO" if not reprovados and not inconclusivos else "REPROVADO"

    print("\n" + "=" * 78)
    print(f"VEREDITO FINAL: {final}   "
          f"({len(aprovados)} aprovado(s), {len(reprovados)} reprovado(s), "
          f"{len(inconclusivos)} inconclusivo(s))")

    destino = args.saida / "gate_ocr_originais.json"
    destino.write_text(
        json.dumps({"veredito_final": final, "documentos": resultados},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"-> {destino}")
    return 0 if final == "APROVADO" else 1


if __name__ == "__main__":
    sys.exit(main())
