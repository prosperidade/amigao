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
antes de o `app.core.config` ser importado — nunca o `.env` padrão:

    python scripts/gate_ocr_originais.py --env-file .env.prod-readonly
           --producao docs23_prod.json --saida docs/trabalhos/ocr_originais/

Qualquer `.env.*` já está bloqueado pelo `.gitignore` (linha 34), com allowlist
só para os `.example` — conferido, não presumido.

Leitura é leitura
-----------------
`StorageService.download_bytes` NÃO chama `_ensure_bucket_exists` (só
`upload_file`/`upload_bytes` chamam, e é lá que mora o `create_bucket`).
Credencial de leitura pura basta, e este gate não tem como criar bucket.

O lado de produção
------------------
`--producao` é um JSON exportado do banco:
`[{"id": 546, "storage_key": "...", "original_file_name": "...",
   "extracted_text": "...", "ocr_status": "done"}, ...]`

Saída: uma tabela por documento (produção × OCR real) e um JSON com o texto
que saiu de cada leitura, para conferência linha a linha.
"""

from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import sys

# Mesma convenção dos outros scripts do diretório (`backfill_document_type.py`
# et al.): a raiz do repositório entra no path para que `import app.*` funcione
# quando o script é chamado por caminho, e não com `python -m`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Áreas do caso #23 que o gate da Frente K registrou. Aparecem no texto de
# produção; a pergunta deste gate é se aparecem IGUAIS quando o OCR lê o
# arquivo original.
AREAS_ESPERADAS = ("926,3654", "725,4663")


def _normalizar(texto: str) -> str:
    """Espaço e caixa fora — o que resta é o conteúdo.

    Sem isto a comparação mede formatação de quebra de linha, que muda entre
    pypdf e Vision sem que uma palavra sequer tenha mudado.
    """
    return re.sub(r"\s+", " ", (texto or "")).strip().lower()


def _similaridade(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def _areas(texto: str) -> list[str]:
    achadas = []
    for a in AREAS_ESPERADAS:
        if a in (texto or ""):
            achadas.append(a)
            continue
        # O mesmo número com outra pontuação ainda é o mesmo número — e a
        # diferença é exatamente o tipo de achado que este gate procura
        # ("926,36.54" no enunciado da frente), então é reportada, não
        # normalizada em silêncio.
        flexivel = re.sub(r"[.,]", "[.,]?", a)
        if re.search(flexivel, texto or ""):
            achadas.append(f"{a} (com outra pontuação)")
    return achadas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--producao", required=True, type=pathlib.Path,
                    help="JSON com id/storage_key/extracted_text de produção")
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
    if args.apenas:
        documentos = [d for d in documentos if d["id"] in args.apenas]

    storage = get_storage_service()
    endpoint = settings.minio_internal_endpoint

    # Pré-voo. `download_bytes` devolve b"" tanto para NoSuchKey quanto para
    # NoSuchBucket — então, sem esta checagem, um nome de bucket errado sairia
    # na tabela como "arquivo ausente no storage": conclusão errada vestida de
    # achado. O gate pergunta pelo BUCKET primeiro e para se não o alcança.
    # (A conflação dentro de `download_bytes` é a dívida #228.)
    print(f"endpoint : {endpoint}")
    print(f"bucket   : {BUCKET_NAME}")
    provedores = {d.get("storage_provider") for d in documentos if d.get("storage_provider")}
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

    print(f"{len(documentos)} documento(s) — storage: {storage.__class__.__name__}\n")
    for d in documentos:
        linha = {
            "id": d["id"],
            "arquivo": d.get("original_file_name"),
            "storage_key": d.get("storage_key"),
            "prod_chars": len(d.get("extracted_text") or ""),
            "prod_ocr_status": d.get("ocr_status"),
            "prod_areas": _areas(d.get("extracted_text") or ""),
        }
        try:
            bytes_originais = storage.download_bytes(d["storage_key"])
        except StorageDownloadError as exc:
            linha.update(erro=f"download falhou: {exc.code}", ocr_chars=0)
            resultados.append(linha)
            print(f"doc {d['id']:>4}  ERRO NO DOWNLOAD: {exc.code}")
            continue

        if not bytes_originais:
            linha.update(erro="objeto não existe no storage (NoSuchKey)", ocr_chars=0)
            resultados.append(linha)
            print(f"doc {d['id']:>4}  ARQUIVO AUSENTE no storage")
            continue

        linha["bytes"] = len(bytes_originais)
        resultado = extract_text_from_pdf(bytes_originais, d.get("mime_type") or "application/pdf")
        linha.update(
            ocr_metodo=resultado.method,
            ocr_modelo=resultado.model_used,
            ocr_chars=resultado.chars,
            ocr_custo_usd=resultado.cost_usd,
            ocr_erro=resultado.error,
            ocr_areas=_areas(resultado.text),
            similaridade=round(_similaridade(d.get("extracted_text") or "", resultado.text), 4),
        )
        (args.saida / f"doc_{d['id']}_ocr_real.txt").write_text(
            resultado.text or "", encoding="utf-8"
        )
        resultados.append(linha)

        print(
            f"doc {linha['id']:>4}  {str(linha['arquivo'])[:34]:<34} "
            f"prod={linha['prod_chars']:>6}ch  ocr={linha['ocr_chars']:>6}ch "
            f"[{resultado.method}/{resultado.model_used or '-'}]  "
            f"sim={linha['similaridade']:.2%}  areas_prod={linha['prod_areas']} "
            f"areas_ocr={linha['ocr_areas']}"
            + (f"  ERRO={resultado.error}" if resultado.error else "")
        )

    destino = args.saida / "gate_ocr_originais.json"
    destino.write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
