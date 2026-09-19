"""ADR-075 — medição do desmembramento das coletâneas. Somente leitura; não é ferramenta de ingestão.

Uso (banco dev, só SELECT):
  1. Exportar cada coletânea para <dir>/<id>.txt e <dir>/<id>.meta ("UF|identifier"):
       docker exec amigao_do_meio_ambiente-db-1 psql -U postgres -d amigao_db -At \
         -c "select full_text from legislation_documents where id=<id>" > <dir>/<id>.txt
     Coletâneas: source_type='compendio_regente' (29) + ids 12, 13, 15 (GO, gravadas como 'manual').
  2. Exportar as normas avulsas (as demais) em CSV (id, full_text):
       psql ... -c "\\copy (select id, full_text from legislation_documents
                  where source_type <> 'compendio_regente' and id not in (12,13,15)) to stdout with csv"
  3. python adr075_medir_coletaneas.py <dir> <avulsos.csv>

Sinais medidos:
  - cabeçalho de impressão do navegador ('dd/mm/aaaa, hh:mm <título>' + URL + 'n/m');
  - cabeçalho formal do ato em linha própria, em maiúsculas: TIPO Nº numero, DE ... DE aaaa;
  - critério ESTRITO: o cabeçalho tem abertura de documento nos 400 caracteres anteriores;
  - repetição de texto por bloco normalizado (entre coletâneas e com normas avulsas).
Limites: regex por cabeçalho; o estrito perde cabeçalho sem contexto de abertura e o largo conta
cabeçalho citado em maiúsculas. O número real de atos fica entre os dois.
"""
import collections
import csv
import hashlib
import pathlib
import re
import sys
import unicodedata

TIPOS = (r"LEI COMPLEMENTAR|LEI DELEGADA|LEI|DECRETO[- ]LEI|DECRETO LEGISLATIVO|DECRETO|"
         r"INSTRU[CÇ][AÃ]O NORMATIVA CONJUNTA|INSTRU[CÇ][AÃ]O NORMATIVA|RESOLU[CÇ][AÃ]O CONJUNTA|"
         r"RESOLU[CÇ][AÃ]O|PORTARIA CONJUNTA|PORTARIA|DELIBERA[CÇ][AÃ]O|NOTA T[EÉ]CNICA|PARECER|"
         r"EMENDA CONSTITUCIONAL|ORIENTA[CÇ][AÃ]O JUR[IÍ]DICA NORMATIVA|ORIENTA[CÇ][AÃ]O NORMATIVA")
RE_ATO = re.compile(
    rf"^[ \t﻿]*(?P<tipo>{TIPOS})(?:\s+[A-ZÇÃÕÉÊÍÓÚ/\-]+){{0,6}}?\s+N\s*[º°oO.]*\s*(?P<num>\d[\d\.]*)"
    rf"(?:\s*[/-]\s*(?P<ano1>\d{{2,4}}))?(?:[^\n]{{0,40}}?\bDE\s+(?P<ano2>(?:19|20)\d{{2}}))?",
    re.M)
RE_PRINT = re.compile(r"^[ \t﻿]*(\d{2}/\d{2}/\d{4}), (\d{2}:\d{2}) (?P<titulo>.+)$", re.M)
RE_URL_PAG = re.compile(r"(https?://\S+?)\s+(\d+)/(\d+)\s*$", re.M)
RE_SUMARIO = re.compile(r"\b(SUM[AÁ]RIO|[IÍ]NDICE)\b", re.I)
RE_ABERTURA = re.compile(r"(ESTADO D[OE]|GOVERNO DO ESTADO|ASSEMBLEIA LEGISLATIVA|SECRETARIA DE ESTADO|"
                         r"Compilado|\b1/\d+\s*$|CONSELHO ESTADUAL|PODER EXECUTIVO|GABINETE)", re.M)


def norm_tipo(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[- ]+", " ", t).strip()


def cabecalhos(s):
    for m in RE_ATO.finditer(s):
        i = m.start("tipo")
        linha = s[i:s.find("\n", i)]
        corpo = re.sub(r"[^A-Za-zÀ-ú]", "", linha)
        if not corpo or sum(c.isupper() for c in corpo) / len(corpo) < 0.7 or len(linha) > 160:
            continue
        ano = m.group("ano2") or m.group("ano1") or "?"
        if len(ano) == 2:
            ano = ("19" if int(ano) > 30 else "20") + ano
        num = m.group("num").replace(".", "").lstrip("0") or "0"
        yield i, norm_tipo(m.group("tipo")), num, ano


def blocos(s):
    b = [x for x in re.split(r"\n\s*\n", s) if len(x.strip()) >= 120]
    if len(b) < 50:
        b = [x for x in s.split("\n") if len(x.strip()) >= 80]
    return [re.sub(r"\s+", " ", x).strip().lower() for x in b]


def main(pasta, avulsos_csv):
    pasta = pathlib.Path(pasta)
    largo, estrito = collections.defaultdict(set), collections.defaultdict(set)
    ec = 0
    paginas = urls = sumarios = 0
    textos = {}
    for txt in sorted(pasta.glob("*.txt"), key=lambda p: int(p.stem)):
        uf = (pasta / f"{txt.stem}.meta").read_text(encoding="utf-8").split("|")[0]
        s = txt.read_text(encoding="utf-8", errors="replace")
        textos[txt.stem] = s
        paginas += len(RE_PRINT.findall(s))
        urls += len({u for u, _, _ in RE_URL_PAG.findall(s)})
        sumarios += bool(RE_SUMARIO.search(s[: max(5000, len(s) // 50)]))
        for i, tipo, num, ano in cabecalhos(s):
            if tipo == "EMENDA CONSTITUCIONAL":
                ec += 1
                continue
            chave = (uf, tipo, num, ano)
            largo[txt.stem].add(chave)
            if RE_ABERTURA.search(s[max(0, i - 400):i]):
                estrito[txt.stem].add(chave)
    u_largo, u_estrito = set().union(*largo.values()), set().union(*estrito.values())
    ocorr = collections.Counter(k for v in estrito.values() for k in v)
    print(f"coletaneas: {len(textos)} | caracteres: {sum(map(len, textos.values()))}")
    print(f"paginas impressas: {paginas} | URLs de origem distintas (soma por coletanea): {urls} | com sumario: {sumarios}")
    print(f"atos distintos ESTRITO: {len(u_estrito)} {dict(collections.Counter(k[0] for k in u_estrito))}"
          f" | sem ano: {sum(1 for k in u_estrito if k[3] == '?')}"
          f" | em mais de uma coletanea: {sum(1 for n in ocorr.values() if n > 1)}")
    print(f"atos distintos LARGO (sem emenda constitucional): {len(u_largo)}"
          f" | sem ano: {sum(1 for k in u_largo if k[3] == '?')} | linhas de emenda constitucional: {ec}")
    print("por tipo (estrito):", dict(collections.Counter(k[1] for k in u_estrito)))

    csv.field_size_limit(10**9)
    avul = set()
    with open(avulsos_csv, encoding="utf-8", newline="") as f:
        for _id, texto in csv.reader(f):
            avul |= {hashlib.sha1(b.encode()).hexdigest() for b in blocos(texto)}
    total = rep_av = rep_col = 0
    visto = {}
    for k, s in sorted(textos.items(), key=lambda x: int(x[0])):
        for b in blocos(s):
            h = hashlib.sha1(b.encode()).hexdigest()
            total += len(b)
            if h in avul:
                rep_av += len(b)
            elif h in visto and visto[h] != k:
                rep_col += len(b)
            else:
                visto.setdefault(h, k)
    print(f"texto em blocos: {total} | repetido com norma avulsa: {rep_av / total:.1%}"
          f" | repetido entre coletaneas: {rep_col / total:.1%} | removivel: {(rep_av + rep_col) / total:.1%}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
