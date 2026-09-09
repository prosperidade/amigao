"""Âncora no texto — todo valor extraído aponta para onde ele está (ADR-064, contenção 1).

Motivador REAL, medido na confirmação da entrada de 09/09 (achado N1):

    O `nirf_cib` da matrícula 3.673 (doc 549) em produção é `6.442.022-1`.
    Essa string NÃO EXISTE no texto do documento — 34.815 chars, `LIKE
    '%6.442.022%'` = false. Ela é, literal, o EXEMPLO escrito no prompt
    ("ex.: 6.442.022-1"). Foi gravada com `confidence: high`, destino
    `matricula.nirf_cib` — o degrau 1 da cascata ITR↔matrícula.

O mesmo valor aparece em três processos diferentes. Num deles é verdadeiro (foi
de lá que o exemplo nasceu); nos outros dois é o prompt vazando para o dado.

A regra desta contenção: **valor que não existe no texto não entra no staging**.
Não some — vira linha explícita, visível na Conferência, sem destino na base.
"Nada some sem dizer" (P12); e o Princípio 11 ("nenhuma afirmação sem fonte")
deixa de ser aspiração e vira condição de entrada.

Verificação por busca NORMALIZADA, não por igualdade: o LLM copia
`6.816.752-0` de um texto que pode trazer `6.816.752-0`, `6816752-0` ou
`6.816.752 - 0`, e copia `Fazenda "POSSE OU PORCOS - GLEBA 4"` de um texto que
escreve `FAZENDA "POSSE OU PORCOS- GLEBA 4"`. Igualdade exata rejeitaria dado
bom; por isso dígitos para números/códigos e palavras para nomes.

FRONTEIRA DECLARADA (ADR-064): a âncora é regra dura para valores ESCALARES.
Valores COMPOSTOS (`onus`, `averbacao_app`, `matricula_listada`,
`proprietarios`) são descrições que o modelo redige — não há literal para
casar. Para eles a âncora é informativa: ancoramos as folhas escalares e
registramos quantas ancoraram, sem barrar a linha. Tipar e datar observação é a
frente seguinte; barrar aqui apagaria o material dela.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

# Um número/código com poucos dígitos casa em qualquer lugar de um documento de
# 80 mil caracteres ("2" está sempre lá). Abaixo deste piso a busca por dígitos
# não prova nada e caímos na busca por texto.
MIN_DIGITOS_PARA_BUSCA = 4

# Idem para texto: uma palavra de 2 letras casa em tudo.
MIN_CHARS_PARA_BUSCA = 3

# Janela do trecho guardado como prova, em cada lado da posição encontrada.
TRECHO_CHARS = 90


@dataclass(frozen=True)
class Ancora:
    """Onde, no `extracted_text`, o valor foi encontrado."""

    pos: int
    """Índice no texto ORIGINAL do documento (o mesmo eixo do relatório de auditoria)."""

    trecho: str
    """Janela ao redor, para o consultor conferir com o olho."""

    metodo: str
    """`digitos` (números/códigos) ou `texto` (nomes/denominações)."""

    def as_dict(self) -> dict[str, Any]:
        return {"pos": self.pos, "trecho": self.trecho, "metodo": self.metodo}


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


class TextoIndexado:
    """Índice de busca normalizada sobre o texto de UM documento.

    Construído uma vez por documento e reusado por todos os campos. Medido: ~0,1s
    para 85k chars — irrelevante ao lado da chamada ao LLM, mas o suficiente para
    não valer a pena repetir por campo.

    Dois eixos, ambos com mapa de volta para a posição ORIGINAL:

    - **dígitos**: só os algarismos, na ordem. `6.816.752-0` e `6816752 0`
      colapsam na mesma sequência `68167520`.
    - **texto**: minúsculas, sem acento, pontuação virando espaço único.
      `FAZENDA "POSSE OU PORCOS- GLEBA 4"` e `Fazenda "Posse ou Porcos - Gleba
      4"` colapsam em `fazenda posse ou porcos gleba 4`.
    """

    __slots__ = ("_texto", "_digitos", "_pos_digitos", "_norm", "_pos_norm")

    def __init__(self, texto: Optional[str]) -> None:
        self._texto = texto or ""
        self._digitos, self._pos_digitos = self._indexar_digitos(self._texto)
        self._norm, self._pos_norm = self._indexar_texto(self._texto)

    # -- construção ---------------------------------------------------------

    @staticmethod
    def _indexar_digitos(texto: str) -> tuple[str, list[int]]:
        buf: list[str] = []
        pos: list[int] = []
        for i, ch in enumerate(texto):
            if ch.isdigit():
                buf.append(ch)
                pos.append(i)
        return "".join(buf), pos

    @staticmethod
    def _indexar_texto(texto: str) -> tuple[str, list[int]]:
        """Normaliza mantendo, para cada char normalizado, a posição original.

        A normalização por caractere (e não por `re.sub` no texto inteiro) existe
        só por causa do mapa: sem ele a posição devolvida seria a do texto
        normalizado, e o consultor receberia um offset que não abre em lugar
        nenhum.
        """
        buf: list[str] = []
        pos: list[int] = []
        espaco_pendente = False
        for i, ch in enumerate(texto):
            # Atalho para ASCII: normalizar Unicode caractere a caractere custa
            # caro num documento de 82k chars, e a esmagadora maioria deles é
            # ASCII puro, que não precisa de normalização nenhuma.
            base = ch.lower() if ch.isascii() else _sem_acento(ch).lower()
            alnum = "".join(c for c in base if c.isalnum())
            if not alnum:
                espaco_pendente = bool(buf)  # não abre com espaço
                continue
            if espaco_pendente:
                buf.append(" ")
                pos.append(i)
                espaco_pendente = False
            for c in alnum:
                buf.append(c)
                pos.append(i)
        return "".join(buf), pos

    # -- busca --------------------------------------------------------------

    @staticmethod
    def normalizar_texto(valor: str) -> str:
        """Mesma normalização do eixo de texto, para o lado do VALOR."""
        base = _sem_acento(str(valor)).lower()
        return re.sub(r"[^a-z0-9]+", " ", base).strip()

    @staticmethod
    def normalizar_digitos(valor: str) -> str:
        return re.sub(r"\D", "", str(valor))

    def _trecho(self, pos: int) -> str:
        ini = max(0, pos - TRECHO_CHARS)
        fim = min(len(self._texto), pos + TRECHO_CHARS)
        return re.sub(r"\s+", " ", self._texto[ini:fim]).strip()

    def buscar(self, valor: Any) -> Optional[Ancora]:
        """Localiza o valor no documento. None = não está lá.

        Números/códigos tentam DÍGITOS primeiro (é o eixo que tolera a pontuação
        de milhar e o hífen); qualquer valor tenta TEXTO em seguida. Um valor
        misto ("CCIR nº 02031617154") acha por qualquer um dos dois.
        """
        if valor is None or isinstance(valor, bool) or not self._texto:
            return None
        bruto = str(valor).strip()
        if not bruto:
            return None

        for digitos in self._agulhas_numericas(bruto):
            idx = self._digitos.find(digitos)
            if idx >= 0:
                pos = self._pos_digitos[idx]
                return Ancora(pos=pos, trecho=self._trecho(pos), metodo="digitos")

        agulha = self.normalizar_texto(bruto)
        if len(agulha) >= MIN_CHARS_PARA_BUSCA:
            idx = self._norm.find(agulha)
            if idx >= 0:
                pos = self._pos_norm[idx]
                return Ancora(pos=pos, trecho=self._trecho(pos), metodo="texto")

        # Valor curto demais para qualquer eixo provar coisa alguma (ex.: uf
        # "GO", área "5"). Não afirmamos que está e não afirmamos que não está —
        # quem separa "não está no documento" de "a busca não se aplica" é
        # `valor_e_verificavel`, consultado ANTES desta chamada.
        return None

    def _agulhas_numericas(self, bruto: str) -> list[str]:
        """Sequências de dígitos a procurar, da mais específica para a menos.

        A segunda existe por causa do float: o modelo às vezes devolve
        ``1010.0`` onde o documento escreve ``1010,5583`` — os dígitos viram
        `10100`, que não está no texto, e o valor seria BARRADO por engano. Zeros
        à direita de uma parte decimal são artefato de serialização, não dado.
        """
        agulhas: list[str] = []
        principal = self.normalizar_digitos(bruto)
        if len(principal) >= MIN_DIGITOS_PARA_BUSCA:
            agulhas.append(principal)
        m = re.fullmatch(r"\s*(-?\d+)[.,](\d*?)0+\s*", bruto)
        if m:
            alternativa = re.sub(r"\D", "", m.group(1) + m.group(2))
            if len(alternativa) >= MIN_DIGITOS_PARA_BUSCA and alternativa not in agulhas:
                agulhas.append(alternativa)
        return agulhas

    def valor_e_verificavel(self, valor: Any) -> bool:
        """False quando o valor é curto demais para a busca provar qualquer coisa.

        Vale para `uf` ("GO", "Goiás" passa), números de um dígito e afins.
        Rejeitar esses por "sem âncora" seria mentir sobre a evidência: a busca
        não falhou, ela não se aplica.
        """
        if valor is None or isinstance(valor, bool):
            return False
        bruto = str(valor).strip()
        if not bruto:
            return False
        return (
            bool(self._agulhas_numericas(bruto))
            or len(self.normalizar_texto(bruto)) >= MIN_CHARS_PARA_BUSCA
        )


# ---------------------------------------------------------------------------
# Valores compostos — âncora informativa (fronteira declarada, ver docstring)
# ---------------------------------------------------------------------------

def _folhas_escalares(valor: Any, prefixo: str = "") -> list[tuple[str, Any]]:
    """Achata dict/list em (caminho, escalar). Ignora vazios."""
    saida: list[tuple[str, Any]] = []
    if isinstance(valor, dict):
        for k, v in valor.items():
            saida.extend(_folhas_escalares(v, f"{prefixo}.{k}" if prefixo else str(k)))
    elif isinstance(valor, (list, tuple)):
        for i, v in enumerate(valor):
            saida.extend(_folhas_escalares(v, f"{prefixo}[{i}]"))
    elif valor not in (None, "", [], {}) and not isinstance(valor, bool):
        saida.append((prefixo or "valor", valor))
    return saida


def ancorar_composto(valor: Any, indice: TextoIndexado) -> dict[str, Any]:
    """Cobertura de âncora de um valor COMPOSTO — informa, não barra.

    Devolve quantas folhas escalares foram encontradas no documento e QUAIS não
    foram. É assim que "credor Banco do Brasil" numa alienação fiduciária do
    Itaú (erro reproduzido nas duas execuções do doc 549) aparece como sinal, em
    vez de seguir como afirmação silenciosa — sem que esta frente precise
    entender o que é um ônus.
    """
    folhas = _folhas_escalares(valor)
    verificaveis = [(c, v) for c, v in folhas if indice.valor_e_verificavel(v)]
    sem_ancora = [c for c, v in verificaveis if indice.buscar(v) is None]
    return {
        "escopo": "composto",
        "folhas": len(folhas),
        "verificaveis": len(verificaveis),
        "ancoradas": len(verificaveis) - len(sem_ancora),
        "sem_ancora": sem_ancora[:10],
    }
