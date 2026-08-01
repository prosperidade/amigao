"""vigencia — a norma revogada é citável, jamais como vigente (ADR-037).

O caso 15 é um auto de infração de 2007 cujo enquadramento invoca o Decreto
3.179/1999 e a Lei 4.771/1965. Ambos foram revogados. A defesa PRECISA citá-los,
porque valiam na data do fato (*tempus regit actum*) — e o sistema não pode, em
hipótese alguma, apresentá-los como direito vigente.

Duas regras, e elas se completam:

1. **A norma histórica entra no corpus.** Deixá-la de fora não protege ninguém:
   força o consultor a buscar fora do sistema exatamente na hora mais delicada.

2. **O rótulo viaja no dado, não no prompt.** O aviso de revogação é gravado no
   `title` do chunk, e não injetado por um agente específico. Assim qualquer
   consumidor — o `LegislacaoAgent` de hoje, o diagnóstico, um agente que ainda
   não existe — recebe o aviso pelo simples fato de ter recebido o trecho. Um
   aviso que mora no prompt de um agente protege um agente; um aviso que mora no
   dado protege o dado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Prefixo procurado pelos testes e pelo consumidor. Em caixa alta e entre
# colchetes porque precisa sobreviver a um LLM lendo 8 trechos com pressa.
MARCADOR_HISTORICA = "[NORMA HISTÓRICA"


@dataclass(frozen=True)
class Vigencia:
    """Janela de vigência de uma norma. `fim=None` significa vigente."""

    inicio: date | None = None
    fim: date | None = None
    sucessora_ref: str | None = None

    @property
    def historica(self) -> bool:
        """Norma que já não vale. Nem por isso inútil — ver o módulo."""
        return self.fim is not None

    def vigente_em(self, quando: date) -> bool:
        """A norma valia nesta data?

        Sem início declarado, assume-se que já valia (o corpus tem documentos
        anteriores a esta coluna existir; tratá-los como "ainda não vigentes"
        os apagaria da busca de um dia para o outro).
        """
        if self.inicio and quando < self.inicio:
            return False
        if self.fim and quando > self.fim:
            return False
        return True


def _br(quando: date) -> str:
    return quando.strftime("%d/%m/%Y")


def rotulo_historico(vigencia: Vigencia) -> str:
    """O aviso que acompanha todo trecho de norma revogada.

    Devolve string vazia para norma vigente — quem chama concatena sem precisar
    testar nada.
    """
    if not vigencia.historica or vigencia.fim is None:
        return ""

    partes = [f"{MARCADOR_HISTORICA} — revogada em {_br(vigencia.fim)}"]
    if vigencia.sucessora_ref:
        partes.append(f", sucedida por {vigencia.sucessora_ref}")
    partes.append(
        f". Aplicável a fatos anteriores a {_br(vigencia.fim)} "
        "(tempus regit actum); NÃO citar como norma vigente]"
    )
    return "".join(partes)


def titulo_com_vigencia(titulo: str | None, vigencia: Vigencia) -> str | None:
    """Título do chunk carregando o rótulo, quando houver.

    É este valor que o `_format_rag_context` do agente coloca no cabeçalho de
    cada trecho — por isso o rótulo chega ao modelo sem que nenhum agente
    precise saber que vigência existe.
    """
    if not vigencia.historica:
        return titulo
    rotulo = rotulo_historico(vigencia)
    if not titulo:
        return rotulo
    if MARCADOR_HISTORICA in titulo:  # idempotente: reindexar não duplica
        return titulo
    return f"{titulo} {rotulo}"


def vigencia_do_documento(doc: object) -> Vigencia:
    """Extrai a vigência de um `LegislationDocument` sem acoplar ao ORM."""
    inicio = getattr(doc, "vigencia_inicio", None)
    fim = getattr(doc, "vigencia_fim", None)
    ref = getattr(doc, "sucessora_ref", None)

    # A sucessora pode estar no corpus (FK) em vez de nomeada em texto.
    if not ref:
        sucessora = getattr(doc, "sucessora", None)
        if sucessora is not None:
            ref = getattr(sucessora, "identifier", None) or getattr(sucessora, "title", None)

    # `effective_date` é datetime; `vigencia_inicio` é date. Sem início próprio,
    # cai no antigo — a coluna nova não invalida o que já estava lá.
    if inicio is None:
        efetiva = getattr(doc, "effective_date", None)
        inicio = efetiva.date() if hasattr(efetiva, "date") else efetiva

    return Vigencia(inicio=inicio, fim=fim, sucessora_ref=ref)
