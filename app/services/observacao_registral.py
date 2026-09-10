"""Observação registral TIPADA — o que o ato É, antes de dizer onde ele pousa.

Frente E (ADR-065). Até aqui a extração de matrícula devolvia **gavetas**:
`averbacao_app`, `averbacao_rl`, `onus`. Quem lê uma certidão sabe que ela não é
feita de três gavetas — é feita de ATOS (`R-nn` registros, `AV.nn` averbações),
cada um com natureza própria. Sem um lugar para dizer a natureza, todo ato que
não fosse APP, RL ou gravame era **forçado** numa das três, e o mapeamento
carimbava fielmente o campo errado:

- doc 548, `AV.10` — arrendamento de 50 ha para terceiro por 15 anos → gravado em
  `averbacao_app`. O documento nunca diz APP.
- doc 549, `R-11` — preço de uma compra e venda → gravado como **hipoteca**;
  `R.15` — alienação fiduciária do **Itaú** → gravada como hipoteca do Banco do
  Brasil. E as três hipotecas de verdade (AV.03/04/05) estavam **baixadas** por
  AV.09/AV.10/AV.12 — corretamente ausentes, mas sem que o sistema soubesse que
  "livre de hipoteca" é informação, e não silêncio.
- doc 547, `Av.03` — RELOCAÇÃO de reserva legal de `185,85.60ha` → entrou como
  `area_registrada_ha`, a área do IMÓVEL (dívida #221). Âncora válida, formato
  válido, normalização correta, campo errado.

O padrão é um só: **o modelo acerta o valor e erra o tipo**. Nenhuma das quatro
contenções do ADR-064 barra isso, porque nenhuma delas pergunta o que o número é.

Aqui o ato vira uma observação com `tipo`, e o destino é decidido DEPOIS, por
tipo, num mapa enumerado (:data:`DESTINO_POR_TIPO`). Tipo sem coluna
correspondente **não é erro**: vira observação visível sem destino, nunca
espremida numa gaveta alheia.

Fronteira desta frente: **temporalidade não é modelada.** `data` e `prazo` são
guardados como TEXTO, do jeito que o documento escreve; não existe vigência,
cancelamento nem "qual é o atual" como campo consultável. A única reconciliação
feita é a que o próprio documento declara por escrito — a baixa que **cita o ato
que baixa** (ver :func:`aplicar_baixas`) —, e essa é referência textual, não
inferência de tempo.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vocabulário fechado
# ---------------------------------------------------------------------------
# Derivado dos QUATRO documentos reais da ELODI (docs 547–550, certidões de
# inteiro teor de Alto Paraíso de Goiás), lidos ato a ato. Cada tipo abaixo tem
# pelo menos uma ocorrência literal nesses documentos, EXCETO os três marcados
# como "registral clássico": esses o sistema já nomeava no próprio prompt
# ("Arrendamento, servidão, usufruto, hipoteca, penhora e alienação não são APP
# nem RL") sem nunca ter tido casa para eles — deixá-los de fora empurraria ato
# conhecido para `nao_classificado`.
#
# Fechado de propósito: o que não está aqui vira `nao_classificado` e aparece na
# tela como tal. Vocabulário aberto é a mesma doença das três gavetas — o modelo
# inventa um rótulo e ninguém sabe o que ele quis dizer.
TIPO_AREA_REGISTRADA = "area_registrada"
TIPO_RESERVA_LEGAL = "reserva_legal"
TIPO_APP = "app"
TIPO_GEORREFERENCIAMENTO = "georreferenciamento"
TIPO_COMPRA_VENDA = "compra_venda"
TIPO_COMPROMISSO = "compromisso_compra_venda"
TIPO_ARRENDAMENTO = "arrendamento"
TIPO_SERVIDAO = "servidao"
TIPO_USUFRUTO = "usufruto"
TIPO_HIPOTECA = "hipoteca"
TIPO_ALIENACAO_FIDUCIARIA = "alienacao_fiduciaria"
TIPO_PENHORA = "penhora"
TIPO_BAIXA = "baixa"
TIPO_ADITIVO = "aditivo"
TIPO_NAO_CLASSIFICADO = "nao_classificado"

VOCABULARIO: dict[str, str] = {
    # tipo → onde ele foi visto (rastro do vocabulário, não decoração)
    TIPO_AREA_REGISTRADA: "abertura da matrícula (doc 547: 926,36.54ha)",
    TIPO_RESERVA_LEGAL: "doc 549 AV.02 (492,9252ha em conjunto) · doc 547 Av.03 (relocação 185,85.60ha)",
    TIPO_APP: "gaveta existente no schema; sem ocorrência nos 4 documentos",
    TIPO_GEORREFERENCIAMENTO: "doc 547 AV-01 · doc 548 AV.01 · doc 549 AV.01",
    TIPO_COMPRA_VENDA: "doc 549 R-11 e R-13 · doc 548 R-11 e R-20 · doc 550 R-01",
    TIPO_COMPROMISSO: "doc 549 AV.06 · doc 548 AV.09 (compromissado com)",
    TIPO_ARRENDAMENTO: "doc 548 AV.10 (50 ha, 15 anos) · doc 547 Av.04 e AV.05",
    TIPO_SERVIDAO: "doc 549 AV.07 (servidão de passagem)",
    TIPO_USUFRUTO: "registral clássico — já nomeado no prompt, sem casa até aqui",
    TIPO_HIPOTECA: "doc 549 AV.03/04/05 · doc 548 AV.02..AV.08, R-21..R-26 · doc 550 R-02..R-04",
    TIPO_ALIENACAO_FIDUCIARIA: "doc 549 R.15 (Itaú) · doc 550 R.05 e R.06 · doc 547 R-16",
    TIPO_PENHORA: "registral clássico — já nomeado no prompt, sem casa até aqui",
    TIPO_BAIXA: "doc 549 AV.09/10/12 (baixa de hipoteca) e AV.14 (quitação) · doc 548 AV.19 (rescisão de arrendamento)",
    TIPO_ADITIVO: "doc 547 AV.11, AV.13, AV.14 (aditivo de cédula/hipoteca)",
    TIPO_NAO_CLASSIFICADO: "escape — ato que o vocabulário não cobre, visível como tal",
}

TIPOS = frozenset(VOCABULARIO)

# Gravames: compõem a linha agregada `onus` (coluna `matricula.onus_gravames`,
# que é UMA coluna de texto — daí a agregação, e não uma linha com destino por
# gravame, que faria a primeira gravar e as outras virarem reconciliação falsa;
# é a mesma razão pela qual `proprietarios` é uma linha só, ver PR #155).
TIPOS_GRAVAME = frozenset({TIPO_HIPOTECA, TIPO_ALIENACAO_FIDUCIARIA, TIPO_PENHORA})

# Tipos cuja área é de um OBJETO DENTRO do imóvel — nunca a área do imóvel.
# É a trava da dívida #221: a área da reserva legal não pode ocupar
# `area_registrada_ha` só porque estava no texto e passou no formato.
TIPOS_AREA_PARCIAL = frozenset({
    TIPO_RESERVA_LEGAL, TIPO_APP, TIPO_ARRENDAMENTO, TIPO_SERVIDAO, TIPO_USUFRUTO,
})

# ── Mapeamento tipo → destino, EXPLÍCITO e enumerado ───────────────────────
# Só entra aqui o tipo que tem coluna correspondente na base. Ausência é
# resposta legítima: a observação existe, fica visível, e não pousa em lugar
# nenhum. Antes desta frente a ausência era resolvida na marra — todo ato sem
# gaveta caía em `averbacao_app`.
DESTINO_POR_TIPO: dict[str, tuple[str, str]] = {
    TIPO_RESERVA_LEGAL: ("matricula", "averbacao_rl"),
    TIPO_APP: ("matricula", "averbacao_app"),
    # Gravames NÃO têm destino individual — ver TIPOS_GRAVAME e `onus_vigentes`.
}

MOTIVO_SEM_CASA = (
    "observação sem coluna correspondente no cadastro — registrada como "
    "observação do documento, não gravada na base"
)
MOTIVO_SUBSTITUIDA = (
    "há outro ato do mesmo tipo mais adiante nesta matrícula ({ato}) — "
    "só o último ato do documento leva o valor para a base"
)
MOTIVO_GRAVAME = (
    "gravame — entra na base pela linha de ônus da matrícula, que reúne os "
    "gravames não baixados"
)
MOTIVO_AREA_DE_OUTRO_OBJETO = (
    "esta área é de {tipo} ({ato}), não do imóvel — não grava como área da "
    "matrícula"
)


# Sinônimos que o modelo devolve na prática, e o tipo canônico correspondente.
# A chave é comparada já normalizada (minúscula, sem acento, sem pontuação).
_SINONIMOS: dict[str, str] = {
    "reserva legal": TIPO_RESERVA_LEGAL,
    "averbacao de reserva legal": TIPO_RESERVA_LEGAL,
    "relocacao de reserva legal": TIPO_RESERVA_LEGAL,
    "rl": TIPO_RESERVA_LEGAL,
    "area de preservacao permanente": TIPO_APP,
    "averbacao de app": TIPO_APP,
    "preservacao permanente": TIPO_APP,
    "georreferenciamento": TIPO_GEORREFERENCIAMENTO,
    "georeferenciamento": TIPO_GEORREFERENCIAMENTO,
    "certificacao": TIPO_GEORREFERENCIAMENTO,
    "compra e venda": TIPO_COMPRA_VENDA,
    "compra venda": TIPO_COMPRA_VENDA,
    "venda e compra": TIPO_COMPRA_VENDA,
    "transmissao": TIPO_COMPRA_VENDA,
    "compromisso de compra e venda": TIPO_COMPROMISSO,
    "compromisso de venda e compra": TIPO_COMPROMISSO,
    "promessa de compra e venda": TIPO_COMPROMISSO,
    "arrendamento": TIPO_ARRENDAMENTO,
    "servidao": TIPO_SERVIDAO,
    "servidao de passagem": TIPO_SERVIDAO,
    "usufruto": TIPO_USUFRUTO,
    "hipoteca": TIPO_HIPOTECA,
    "hipoteca cedular": TIPO_HIPOTECA,
    "registro de hipoteca": TIPO_HIPOTECA,
    "alienacao fiduciaria": TIPO_ALIENACAO_FIDUCIARIA,
    "alienacao": TIPO_ALIENACAO_FIDUCIARIA,
    "penhora": TIPO_PENHORA,
    "arresto": TIPO_PENHORA,
    "baixa": TIPO_BAIXA,
    "baixa de hipoteca": TIPO_BAIXA,
    "cancelamento": TIPO_BAIXA,
    "quitacao": TIPO_BAIXA,
    "quitacao da divida": TIPO_BAIXA,
    "rescisao": TIPO_BAIXA,
    "rescisao de arrendamento": TIPO_BAIXA,
    "liberacao": TIPO_BAIXA,
    "aditivo": TIPO_ADITIVO,
    "aditamento": TIPO_ADITIVO,
    "retificacao": TIPO_ADITIVO,
    "area registrada": TIPO_AREA_REGISTRADA,
    "area do imovel": TIPO_AREA_REGISTRADA,
}

_ACENTOS = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
                         "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")


def _slug(bruto: Any) -> str:
    """Minúscula, sem acento, sem pontuação — a forma de comparar rótulo."""
    texto = str(bruto or "").translate(_ACENTOS).lower()
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def normalizar_tipo(bruto: Any) -> str:
    """Rótulo do modelo → tipo do vocabulário. Fora dele: `nao_classificado`.

    Nunca levanta e nunca inventa: rótulo desconhecido vira o escape, que é
    VISÍVEL na Conferência. O ato aparece com o que o documento disse dele —
    o oposto de ser empurrado para `averbacao_app` por não ter onde caber.
    """
    slug = _slug(bruto)
    if not slug:
        return TIPO_NAO_CLASSIFICADO
    direto = slug.replace(" ", "_")
    if direto in TIPOS:
        return direto
    if slug in _SINONIMOS:
        return _SINONIMOS[slug]
    # Rótulo composto ("registro de hipoteca em 2º grau", "da compra e venda"):
    # o sinônimo mais LONGO que aparece dentro dele vence — "compromisso de
    # compra e venda" não pode ser lido como "compra e venda".
    candidatos = [(len(k), v) for k, v in _SINONIMOS.items() if k in slug]
    if candidatos:
        return max(candidatos)[1]
    logger.info("observacao_registral: tipo fora do vocabulário: %r", bruto)
    return TIPO_NAO_CLASSIFICADO


# ---------------------------------------------------------------------------
# Rótulo do ato (AV.03, R-11, R.15) — identidade normalizada
# ---------------------------------------------------------------------------
# Dedupe/casamento por identificador normalizado, nunca por string crua: o mesmo
# ato aparece como "AV.03", "Av.03", "AV-03" e "AV 03" no mesmo documento.
_ATO_RE = re.compile(r"\b(AV|R)[.\-\s]{0,2}(\d{1,3})\b", re.IGNORECASE)


def chave_ato(bruto: Any) -> Optional[str]:
    """`"Av.03"` → `"AV-3"`. None quando não há rótulo de ato reconhecível."""
    m = _ATO_RE.search(str(bruto or ""))
    if m is None:
        return None
    return f"{m.group(1).upper()}-{int(m.group(2))}"


def _atos_citados(texto: Any) -> list[str]:
    """Todos os rótulos de ato citados num texto, normalizados."""
    return [f"{p.upper()}-{int(n)}" for p, n in _ATO_RE.findall(str(texto or ""))]


# ---------------------------------------------------------------------------
# A observação
# ---------------------------------------------------------------------------

# Atributos que o esqueleto do prompt pede por ato. `descricao` é o que o
# documento diz; os demais são recortes dele. Nenhum deles é obrigatório —
# ato sem atributo nenhum ainda é um ato, e some se exigirmos completude.
ATRIBUTOS_DO_ATO = (
    "ato", "data", "area_ha", "valor", "partes", "prazo",
    "ato_referenciado", "descricao",
)


@dataclass
class Observacao:
    """Um ato da matrícula, com o que ele É antes de onde ele pousa."""

    tipo: str
    atributos: dict[str, Any] = field(default_factory=dict)
    ordem: int = 0
    """Posição do ato na lista devolvida pelo modelo (a certidão é cronológica
    por construção — usada só para desempatar dois atos do MESMO destino)."""

    @property
    def ato(self) -> Optional[str]:
        return self.atributos.get("ato")

    @property
    def chave(self) -> Optional[str]:
        return chave_ato(self.ato)

    @property
    def baixado_por(self) -> Optional[str]:
        return self.atributos.get("baixado_por")

    def resumo(self) -> str:
        """Uma linha legível para a tela, montada só com literais do ato.

        Não é interpretação: é concatenação do que veio do documento. O
        `field_value.value` da linha de staging precisa ser algo que a
        consultora leia sem abrir o JSON.
        """
        partes: list[str] = []
        if self.ato:
            partes.append(str(self.ato))
        partes.append(rotulo_humano(self.tipo))
        for chave in ("area_ha", "valor", "prazo", "data"):
            valor = self.atributos.get(chave)
            if valor in (None, "", [], {}):
                continue
            if chave == "area_ha":
                partes.append(f"{valor} ha")
            else:
                partes.append(str(valor))
        pessoas = self.atributos.get("partes")
        if isinstance(pessoas, list) and pessoas:
            partes.append(", ".join(str(p) for p in pessoas if p)[:120])
        elif isinstance(pessoas, str) and pessoas.strip():
            partes.append(pessoas.strip()[:120])
        if self.baixado_por:
            partes.append(f"baixado por {self.baixado_por}")
        return " · ".join(p for p in partes if p)


_ROTULOS = {
    TIPO_AREA_REGISTRADA: "Área registrada",
    TIPO_RESERVA_LEGAL: "Reserva Legal",
    TIPO_APP: "APP",
    TIPO_GEORREFERENCIAMENTO: "Georreferenciamento",
    TIPO_COMPRA_VENDA: "Compra e venda",
    TIPO_COMPROMISSO: "Compromisso de compra e venda",
    TIPO_ARRENDAMENTO: "Arrendamento",
    TIPO_SERVIDAO: "Servidão",
    TIPO_USUFRUTO: "Usufruto",
    TIPO_HIPOTECA: "Hipoteca",
    TIPO_ALIENACAO_FIDUCIARIA: "Alienação fiduciária",
    TIPO_PENHORA: "Penhora",
    TIPO_BAIXA: "Baixa",
    TIPO_ADITIVO: "Aditivo",
    TIPO_NAO_CLASSIFICADO: "Ato não classificado",
}


def rotulo_humano(tipo: Optional[str]) -> str:
    return _ROTULOS.get(tipo or "", _ROTULOS[TIPO_NAO_CLASSIFICADO])


def observacoes_de(atos: Any) -> list[Observacao]:
    """Lista de atos do JSON → observações tipadas, na ordem do documento."""
    if not isinstance(atos, list):
        return []
    saida: list[Observacao] = []
    for i, bruto in enumerate(atos):
        if not isinstance(bruto, dict):
            continue
        atributos = {
            k: v for k, v in bruto.items()
            if k in ATRIBUTOS_DO_ATO and v not in (None, "", [], {})
        }
        if not atributos:
            continue
        saida.append(Observacao(tipo=normalizar_tipo(bruto.get("tipo")),
                                atributos=atributos, ordem=i))
    return saida


def aplicar_baixas(observacoes: list[Observacao]) -> None:
    """Marca com `baixado_por` o gravame que uma BAIXA declara ter baixado.

    Reconciliação por REFERÊNCIA ESCRITA, não por data: a averbação de baixa
    cita o ato que ela baixa — *"Averba-se para constar a baixa da cédula …
    constante da **AV.03**, acima"*. Sem isso, as três hipotecas do doc 549
    (AV.03/04/05), todas baixadas por AV.09/AV.10/AV.12, continuariam sendo
    afirmadas como gravames vigentes.

    Modifica em lugar (`atributos["baixado_por"]`). Baixa que não encontra o ato
    citado não some nem vira erro: continua uma observação de baixa visível.
    """
    por_chave = {o.chave: o for o in observacoes if o.chave}
    for obs in observacoes:
        if obs.tipo != TIPO_BAIXA:
            continue
        citados = _atos_citados(obs.atributos.get("ato_referenciado"))
        if not citados:
            # O modelo nem sempre preenche `ato_referenciado`; a descrição
            # costuma trazer a referência literal ("constante da AV.03").
            citados = [c for c in _atos_citados(obs.atributos.get("descricao"))
                       if c != obs.chave]
        for chave in citados:
            alvo = por_chave.get(chave)
            if alvo is None or alvo is obs or alvo.tipo == TIPO_BAIXA:
                continue
            alvo.atributos["baixado_por"] = obs.ato or chave
            logger.info(
                "observacao_registral: %s (%s) baixado por %s",
                alvo.ato, alvo.tipo, obs.ato,
            )


def destino_de(obs: Observacao) -> Optional[tuple[str, str]]:
    """(entidade, coluna) do tipo, ou None quando o tipo não tem casa."""
    return DESTINO_POR_TIPO.get(obs.tipo)


def onus_vigentes(observacoes: list[Observacao]) -> list[dict[str, Any]]:
    """Os gravames que o documento afirma e NÃO declara baixados.

    Chave `partes` (lista), não `credor` (singular) — gate medido: o modelo não
    ordena as partes de forma estável entre execuções (doc 550, R.05/R.06: uma
    execução devolveu "BANCO DO BRASIL S/A" primeiro, a outra "JOEL CENCI" —
    mesmo dado, ordem trocada). Escolher `partes[0]` como "o credor" seria
    inventar um papel que o modelo não afirma — exatamente o que "papel de
    pessoa" (fora do escopo desta frente, ver ADR-065) existe para não fazer.
    Mostrar a lista inteira é a resposta honesta: quem lê decide quem é quem.
    """
    saida: list[dict[str, Any]] = []
    for obs in observacoes:
        if obs.tipo not in TIPOS_GRAVAME or obs.baixado_por:
            continue
        item = {
            "tipo": rotulo_humano(obs.tipo),
            "partes": obs.atributos.get("partes"),
            "valor": obs.atributos.get("valor"),
            "ato": obs.ato,
            "data": obs.atributos.get("data"),
        }
        saida.append({k: v for k, v in item.items() if v not in (None, "", [], {})})
    return saida


def ultimo_por_destino(observacoes: list[Observacao]) -> dict[tuple[str, str], Observacao]:
    """Qual observação leva o destino, quando duas disputam a mesma coluna.

    A coluna é uma só; dois atos do mesmo tipo (uma averbação de RL e, mais
    adiante, a relocação dela) não podem gravar os dois. Vence o **último ato do
    documento** — a certidão é cronológica por construção, então "mais adiante"
    é o mais recente que o próprio documento afirma. Isto é ordem no papel, não
    vigência inferida: a temporalidade continua fora desta frente.
    """
    escolha: dict[tuple[str, str], Observacao] = {}
    for obs in observacoes:
        destino = destino_de(obs)
        if destino is None:
            continue
        atual = escolha.get(destino)
        if atual is None or obs.ordem >= atual.ordem:
            escolha[destino] = obs
    return escolha


def area_de_outro_objeto(
    observacoes: list[Observacao], valor_area: Any
) -> Optional[Observacao]:
    """A observação cuja área é IGUAL à candidata a área do imóvel, se houver.

    Fecha a dívida **#221**: no doc 547 o modelo devolveu `185,85.60` como
    `area_registrada_ha` — é a área da RELOCAÇÃO DA RESERVA LEGAL (Av.03, char
    56.111). Âncora válida (o valor está no texto), formato válido (área
    plausível), normalização correta (185,856 ha): **nenhuma das quatro
    contenções do ADR-064 barra**, porque nenhuma pergunta o que o número é.

    Agora pergunta. Se o mesmo número aparece como área de um ato de reserva
    legal, APP, arrendamento, servidão ou usufruto, ele é área DAQUILO — e a
    linha da área do imóvel perde o destino em vez de gravar 185,856 ha como
    área de uma matrícula de 926 ha.
    """
    alvo = _area_comparavel(valor_area)
    if alvo is None:
        return None
    for obs in observacoes:
        if obs.tipo not in TIPOS_AREA_PARCIAL:
            continue
        if _area_comparavel(obs.atributos.get("area_ha")) == alvo:
            return obs
    return None


def _area_comparavel(bruto: Any) -> Optional[float]:
    """Área em hectares para COMPARAR (nunca para gravar).

    Passa pela mesma porta única do resto do sistema: a notação registral
    (`185,85.60`) é decodificada por regra antes de comparar, senão
    `185,85.60` e `185,856` seriam números diferentes.
    """
    if bruto in (None, "", [], {}) or isinstance(bruto, bool):
        return None
    from app.services.area_registral import normalizar_area_registral  # noqa: PLC0415
    from app.services.inconsistency_matrix import parse_area_ha  # noqa: PLC0415

    registral = normalizar_area_registral(bruto)
    valor = registral.valor_ha if registral else parse_area_ha(bruto)
    if valor is None:
        return None
    return round(float(valor), 4)
