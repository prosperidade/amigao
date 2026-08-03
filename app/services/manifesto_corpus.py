"""manifesto_corpus — o corpus passa a ser dirigido por curadoria versionada.

Até aqui, o que entrava no corpus era uma **lista fixa escrita à mão** dentro de
`scripts/ingest_federais_canonicos.py`. A medição de 31/07 mostrou o custo disso:
o corpus federal tinha exatamente o tamanho da lista que alguém digitou em abril,
e ninguém sabia que era esse o limite — parecia falha de ingestão.

A partir daqui a fonte de verdade é um **manifesto versionado** (CSV no repo),
extraído da curadoria da Isis. Quem decide o que entra é a curadoria; o código só
executa, e executa reclamando quando a linha não se sustenta.

Duas distinções que o manifesto carrega e que o corpus não tinha:

**tipo** — `norma` × `referencia_operacional`. A matriz da Isis lista, lado a
lado, o Decreto 6.514/2008 e a página "Obter Certidão de Embargo" do gov.br. As
duas são úteis e só uma é fundamentação. Página de serviço vetorizada competiria
com lei na busca por similaridade — a mesma física que o ADR-036 descreveu — e
apareceria como fonte de uma peça assinada. Fica no manifesto (versionada,
exibível ao consultor) e **fora** do corpus vetorial.

**observacao_curadoria** — o que a ingestão descobriu e a curadoria precisa
saber: revogação não sinalizada, URL truncada, portal que responde 403. É um
canal de volta para a Isis, não um comentário de código.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Só estes entram no corpus vetorial.
TIPO_NORMA = "norma"
TIPO_REFERENCIA = "referencia_operacional"
TIPOS_VALIDOS = {TIPO_NORMA, TIPO_REFERENCIA}

ESFERAS_VALIDAS = {"federal", "estadual", "municipal", "nacional"}

# A curadoria da Isis usa este texto para "conferi e é a fonte certa". Qualquer
# outro valor (pendente, não localizado, em tramitação) NÃO entra: o corpus não
# recebe norma que a própria curadoria não conseguiu confirmar.
STATUS_VALIDADO = "fonte oficial validada"


class ManifestoInvalido(ValueError):
    """Erro de contrato do manifesto. Falha no CARREGAMENTO, não na ingestão —
    manifesto quebrado não deve começar a baixar nada."""


@dataclass(frozen=True)
class LinhaManifesto:
    identifier: str
    titulo: str
    url: str
    bloco: str
    orgao: str | None = None
    esfera: str = "federal"
    uf: str | None = None
    tipo: str = TIPO_NORMA
    status_fonte: str = ""
    fonte_oficial: bool = False
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    sucessora_ref: str | None = None
    validation_keyword: str = ""
    observacao_curadoria: str | None = None
    demand_types: list[str] = field(default_factory=list)

    @property
    def historica(self) -> bool:
        return self.vigencia_fim is not None

    @property
    def ingerivel(self) -> bool:
        """Entra no corpus vetorial?

        Três condições, e todas já custaram caro uma vez:
        - é NORMA (não página de serviço) — ADR-036, a física da busca;
        - a curadoria VALIDOU a fonte — não ingerimos o que ela não confirmou;
        - tem URL.
        """
        return (
            self.tipo == TIPO_NORMA
            and self.status_fonte.strip().lower() == STATUS_VALIDADO
            and bool(self.url)
        )

    @property
    def motivo_nao_ingerivel(self) -> str | None:
        if self.ingerivel:
            return None
        if self.tipo != TIPO_NORMA:
            return "referência operacional — versionada, não vetorizada"
        if not self.url:
            return "sem URL"
        return f"status da curadoria: {self.status_fonte or '(vazio)'}"


def _data(valor: str | None) -> date | None:
    valor = (valor or "").strip()
    if not valor:
        return None
    ano, mes, dia = (int(p) for p in valor.split("-"))
    return date(ano, mes, dia)


def _bool(valor: str | None) -> bool:
    return (valor or "").strip().lower() in {"1", "true", "sim", "yes", "y"}


COLUNAS_OBRIGATORIAS = ("identifier", "titulo", "url", "bloco", "tipo", "status_fonte")


def carregar_manifesto(caminho: str | Path) -> list[LinhaManifesto]:
    """Lê e VALIDA o manifesto. Levanta antes de baixar qualquer coisa."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise ManifestoInvalido(f"manifesto não encontrado: {caminho}")

    linhas: list[LinhaManifesto] = []
    with caminho.open(encoding="utf-8", newline="") as fh:
        leitor = csv.DictReader(fh)
        faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in (leitor.fieldnames or [])]
        if faltando:
            raise ManifestoInvalido(
                f"{caminho.name}: colunas obrigatórias ausentes: {', '.join(faltando)}"
            )

        for n, bruto in enumerate(leitor, start=2):  # linha 1 é o cabeçalho
            ident = (bruto.get("identifier") or "").strip()
            if not ident:
                raise ManifestoInvalido(f"{caminho.name}:{n} — identifier vazio")

            tipo = (bruto.get("tipo") or TIPO_NORMA).strip()
            if tipo not in TIPOS_VALIDOS:
                raise ManifestoInvalido(
                    f"{caminho.name}:{n} ({ident}) — tipo {tipo!r} inválido; "
                    f"use um de {sorted(TIPOS_VALIDOS)}"
                )

            esfera = (bruto.get("esfera") or "federal").strip()
            if esfera not in ESFERAS_VALIDAS:
                raise ManifestoInvalido(
                    f"{caminho.name}:{n} ({ident}) — esfera {esfera!r} inválida"
                )

            keyword = (bruto.get("validation_keyword") or "").strip()
            linha = LinhaManifesto(
                identifier=ident,
                titulo=(bruto.get("titulo") or "").strip(),
                url=(bruto.get("url") or "").strip(),
                bloco=(bruto.get("bloco") or "").strip(),
                orgao=(bruto.get("orgao") or "").strip() or None,
                esfera=esfera,
                uf=(bruto.get("uf") or "").strip() or None,
                tipo=tipo,
                status_fonte=(bruto.get("status_fonte") or "").strip(),
                fonte_oficial=_bool(bruto.get("fonte_oficial")),
                vigencia_inicio=_data(bruto.get("vigencia_inicio")),
                vigencia_fim=_data(bruto.get("vigencia_fim")),
                sucessora_ref=(bruto.get("sucessora_ref") or "").strip() or None,
                validation_keyword=keyword,
                observacao_curadoria=(bruto.get("observacao_curadoria") or "").strip() or None,
                demand_types=[
                    d.strip() for d in (bruto.get("demand_types") or "").split("|") if d.strip()
                ],
            )

            # A guarda que pegou o mirror do LegisWeb servindo uma resolução da
            # SEFAZ-AM no lugar da IN IBAMA 10/2012. Sem keyword não há como
            # saber se o que baixou é o que se pediu — e "parece certo" já provou
            # que não basta. Só se exige de quem vai ser ingerido.
            if linha.ingerivel and not keyword:
                raise ManifestoInvalido(
                    f"{caminho.name}:{n} ({ident}) — validation_keyword é obrigatória "
                    "para linha ingerível: sem ela, fonte trocada entra calada"
                )

            # Norma histórica sem sucessora é possível (nem toda revogação tem
            # substituta), mas sucessora sem fim de vigência é incoerente.
            if linha.sucessora_ref and not linha.vigencia_fim:
                raise ManifestoInvalido(
                    f"{caminho.name}:{n} ({ident}) — sucessora_ref sem vigencia_fim: "
                    "se foi sucedida, houve fim de vigência"
                )

            linhas.append(linha)

    return linhas
