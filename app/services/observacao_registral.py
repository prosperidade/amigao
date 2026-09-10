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

Fronteira da Frente E: temporalidade não era modelada — `data` e `prazo` eram
guardados como TEXTO puro; a única reconciliação era a baixa que cita, por
escrito, o ato que baixa.

Frente F (ADR-066) fecha HIST-001: cada observação tipada ganha três campos
estruturados, extraídos com âncora como qualquer valor — `data_ato`,
`altera_ato` (generaliza o antigo `ato_referenciado`: baixa OU retificação) — e
`ato` (o rótulo do próprio ato, já existia desde a Frente E). E um campo
DERIVADO, nunca extraído pelo LLM: `vigencia`
(:func:`derivar_vigencia`) — vigente | baixado | retificado | expirado |
indeterminado, calculado por REGRA sobre o grafo de `altera_ato` + datas +
tipo. O LLM extrai fatos; o sistema deriva estado. Silêncio nunca vira
`vigente` — sem prova de data de origem e sem alteração encontrada, o estado é
`indeterminado`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
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

# Frente F (ADR-066) — tipos onde "vigente/baixado/expirado" faz sentido como
# ESTADO. `compra_venda`, `georreferenciamento`, `baixa` e `aditivo` são
# eventos que acontecem uma vez (a `compra_venda` TRANSFERE, não "vigora"); um
# gravame ou um direito sobre parte do imóvel PERMANECE até algo o encerrar —
# é exatamente a mesma linha que `TIPOS_AREA_PARCIAL` já traçou (objeto que
# existe DENTRO do imóvel, com vida própria), somada aos gravames.
TIPOS_COM_VIGENCIA = TIPOS_GRAVAME | TIPOS_AREA_PARCIAL

# Só `arrendamento`/`usufruto` carregam PRAZO com termo final no vocabulário
# medido (doc 548 AV.10: "15 anos ... 01/01/2013 a 01/01/2028"). Hipoteca tem
# "vencimento" da CRH, mas isso não baixa o gravame por si — só a averbação de
# baixa faz isso (ver doc 549: a hipoteca vence e o gravame segue registrado
# até a AV.09/10/12). Aplicar prazo a gravame inventaria expiração que o
# registro não afirma.
_TIPOS_COM_TERMO = frozenset({TIPO_ARRENDAMENTO, TIPO_USUFRUTO})

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

# Frente F (ADR-066) — vocabulário fechado do campo DERIVADO `vigencia`.
# Nunca escrito pelo LLM; só por :func:`derivar_vigencia`.
VIGENCIA_VIGENTE = "vigente"
VIGENCIA_BAIXADO = "baixado"
VIGENCIA_RETIFICADO = "retificado"
VIGENCIA_EXPIRADO = "expirado"
VIGENCIA_INDETERMINADO = "indeterminado"


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
#
# Frente F (ADR-066): `data` → `data_ato` e `ato_referenciado` → `altera_ato`
# (mesmo papel, nome que combina com o par extraído-vs-derivado: `vigencia` é
# quem responde "e daí?" a partir de `data_ato`/`altera_ato`). `adquirentes`/
# `transmitentes` são novos — só fazem sentido em `compra_venda`, o único tipo
# que TRANSFERE titularidade registral (ver :func:`titular_atual`).
ATRIBUTOS_DO_ATO = (
    "ato", "data_ato", "area_ha", "valor", "partes", "adquirentes",
    "transmitentes", "prazo", "altera_ato", "descricao",
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

    @property
    def retificado_por(self) -> Optional[str]:
        return self.atributos.get("retificado_por")

    @property
    def vigencia(self) -> Optional[str]:
        """Estado DERIVADO (:func:`derivar_vigencia`) — None até a derivação
        rodar; nunca preenchido pelo LLM."""
        return self.atributos.get("vigencia")

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
        for chave in ("area_ha", "valor", "prazo", "data_ato"):
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
        for chave_papel, rotulo in (("adquirentes", "adquirido por"), ("transmitentes", "de")):
            nomes = self.atributos.get(chave_papel)
            if isinstance(nomes, list) and nomes:
                partes.append(f"{rotulo} {', '.join(str(n) for n in nomes if n)[:120]}")
        if self.baixado_por:
            partes.append(f"baixado por {self.baixado_por}")
        elif self.retificado_por:
            partes.append(f"retificado por {self.retificado_por}")
        if self.vigencia == VIGENCIA_EXPIRADO:
            partes.append("expirado")
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


def aplicar_alteracoes(observacoes: list[Observacao]) -> None:
    """Marca o ato que uma BAIXA ou um ADITIVO declara alterar.

    Reconciliação por REFERÊNCIA ESCRITA, não por data: a averbação cita o ato
    que ela altera — *"Averba-se para constar a baixa da cédula … constante da
    **AV.03**, acima"*. Sem isso, as três hipotecas do doc 549 (AV.03/04/05),
    todas baixadas por AV.09/AV.10/AV.12, continuariam sendo afirmadas como
    gravames vigentes.

    Frente F (ADR-066) generaliza a Frente E: `aditivo` já tinha casa no
    vocabulário ("aditivo de cédula/hipoteca", doc 547 AV.11/13/14) e o próprio
    prompt já pedia `altera_ato` para ele ("quando o ato ... adita outro
    ato") — só que o código nunca lia. Aqui os dois tipos alimentam o mesmo
    grafo, com o campo diferente (`baixado_por` vs. `retificado_por`), porque
    `vigencia` (:func:`derivar_vigencia`) precisa distinguir os dois estados.

    **Cuidado medido no texto real (doc 549):** quase toda averbação abre com
    uma referência de ARQUIVAMENTO para OUTRA matrícula — *"AV.02 MAT. 3.673
    -(Averbação referente a Av.09 Mat. 2007 e Av. 04 Mat. 3.669)-"*. Isso não é
    alteração: é a matrícula ANTERIOR do mesmo ato, numa certidão diferente. O
    prompt instrui o modelo a não confundir os dois; aqui a defesa é a mesma
    de sempre — `por_chave` só resolve rótulos que existem NESTA lista de
    atos, então uma referência para uma matrícula que não está no documento
    simplesmente não casa com nada e é ignorada, não interpretada.

    Modifica em lugar (`atributos["baixado_por"]`/`atributos["retificado_por"]`).
    Ato que não encontra o alvo citado não some nem vira erro: continua uma
    observação visível, só sem o grafo fechado do outro lado.
    """
    por_chave = {o.chave: o for o in observacoes if o.chave}
    for obs in observacoes:
        if obs.tipo not in (TIPO_BAIXA, TIPO_ADITIVO):
            continue
        citados = _atos_citados(obs.atributos.get("altera_ato"))
        if not citados:
            # O modelo nem sempre preenche `altera_ato`; a descrição costuma
            # trazer a referência literal ("constante da AV.03").
            citados = [c for c in _atos_citados(obs.atributos.get("descricao"))
                       if c != obs.chave]
        campo = "baixado_por" if obs.tipo == TIPO_BAIXA else "retificado_por"
        for chave in citados:
            alvo = por_chave.get(chave)
            if alvo is None or alvo is obs or alvo.tipo in (TIPO_BAIXA, TIPO_ADITIVO):
                continue
            if alvo.tipo not in TIPOS_COM_VIGENCIA:
                # Medido no doc 548 real: AV.14 ("QUITAÇÃO DA DÍVIDA") cita o
                # R-13 (compra_venda) — o PREÇO da venda foi pago, não a venda
                # desfeita. `compra_venda` não tem estado de vigência (é
                # evento, TIPOS_COM_VIGENCIA não o inclui); marcar
                # `baixado_por` nele apareceria em `resumo()` como "R-13
                # baixado por AV.14", sugerindo a venda anulada. Só tipos com
                # estado de vigência são alvo válido de baixa/retificação.
                continue
            alvo.atributos[campo] = obs.ato or chave
            logger.info(
                "observacao_registral: %s (%s) %s por %s",
                alvo.ato, alvo.tipo, campo, obs.ato,
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
            "data_ato": obs.atributos.get("data_ato"),
        }
        saida.append({k: v for k, v in item.items() if v not in (None, "", [], {})})
    return saida


def ultimo_por_destino(observacoes: list[Observacao]) -> dict[tuple[str, str], Observacao]:
    """Qual observação leva o destino, quando duas disputam a mesma coluna.

    A coluna é uma só; dois atos do mesmo tipo (uma averbação de RL e, mais
    adiante, a relocação dela) não podem gravar os dois. Vence o **último ato do
    documento** — a certidão é cronológica por construção, então "mais adiante"
    é o mais recente que o próprio documento afirma. Isto é ordem no papel, não
    vigência derivada por regra (:func:`derivar_vigencia`) — as duas concordam
    na prática (o ato mais recente tende a ser o vigente), mas são mecanismos
    diferentes: este resolve "quem grava a coluna", aquele resolve "isto ainda
    vale". :func:`rl_vigente` reaproveita este, não duplica.
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


# ---------------------------------------------------------------------------
# Frente F (ADR-066) — vigência DERIVADA, nunca extraída
# ---------------------------------------------------------------------------

_DATA_RE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")


def _ultima_data(bruto: Any) -> Optional[date]:
    """A última data `DD/MM/AAAA` dentro do texto, ou None.

    "Última", não "primeira": um prazo escrito como "01/01/2013 a 01/01/2028"
    tem DUAS datas, e o termo FINAL — o que importa para expiração — é a
    segunda. Datas inválidas (dia/mês fora de faixa) são ignoradas, não
    derrubam a busca inteira."""
    datas: list[date] = []
    for d, m, y in _DATA_RE.findall(str(bruto or "")):
        try:
            datas.append(date(int(y), int(m), int(d)))
        except ValueError:
            continue
    return datas[-1] if datas else None


def derivar_vigencia(
    observacoes: list[Observacao], data_referencia: Optional[date] = None
) -> None:
    """Preenche `atributos["vigencia"]` de cada observação — por REGRA, nunca
    pelo LLM. Modifica em lugar; roda depois de :func:`aplicar_alteracoes`
    (precisa de `baixado_por`/`retificado_por` já resolvidos).

    Ordem de decisão, a mesma tabela do ADR-066:

    1. **Alterado** — outro ato desta matrícula cita este em `altera_ato`.
       `baixa` ⇒ `baixado`; `aditivo` ⇒ `retificado`. Referência textual,
       igual a :func:`aplicar_alteracoes` — não é inferência.
    2. **Prazo com termo** — só `arrendamento`/`usufruto` (:data:`_TIPOS_COM_TERMO`).
       Termo final < `data_referencia` ⇒ `expirado`; senão `vigente`. A
       comparação é com a data de referência do CASO, não com `date.today()`
       — quem chama decide "vigente quando" (default: hoje, quando ninguém
       tem uma data de caso à mão).
    3. **Ato de origem com data** (`data_ato` presente, sem alteração
       encontrada) ⇒ `vigente`.
    4. **Nenhuma das anteriores** ⇒ `indeterminado`. Nunca `vigente` por
       default — silêncio não é vigência (a mesma regra do ADR-065 para
       "partes[0] não é o credor": o sistema só afirma o que o documento
       sustenta).

    Só tipos em :data:`TIPOS_COM_VIGENCIA` recebem o campo — `compra_venda`,
    `baixa`, `aditivo` etc. são eventos, não estados; `vigencia` neles não
    responderia pergunta nenhuma.
    """
    ref = data_referencia or date.today()
    for obs in observacoes:
        if obs.tipo not in TIPOS_COM_VIGENCIA:
            continue
        if obs.baixado_por:
            obs.atributos["vigencia"] = VIGENCIA_BAIXADO
            continue
        if obs.retificado_por:
            obs.atributos["vigencia"] = VIGENCIA_RETIFICADO
            continue
        if obs.tipo in _TIPOS_COM_TERMO:
            termo_final = _ultima_data(obs.atributos.get("prazo"))
            if termo_final is not None:
                obs.atributos["vigencia"] = (
                    VIGENCIA_EXPIRADO if termo_final < ref else VIGENCIA_VIGENTE
                )
                continue
        if obs.atributos.get("data_ato"):
            obs.atributos["vigencia"] = VIGENCIA_VIGENTE
            continue
        obs.atributos["vigencia"] = VIGENCIA_INDETERMINADO


def rl_vigente(observacoes: list[Observacao]) -> Optional[Observacao]:
    """A averbação de Reserva Legal vigente da matrícula.

    Reaproveita :func:`ultimo_por_destino` — RL é uma COLUNA
    (`matricula.averbacao_rl`), então "vigente" e "quem grava a coluna" são a
    mesma pergunta para este tipo (ao contrário dos gravames, que são lista).
    None quando a matrícula não tem RL averbada nos atos.
    """
    return ultimo_por_destino(observacoes).get(("matricula", "averbacao_rl"))


def cadeia_titularidade(observacoes: list[Observacao]) -> list[dict[str, Any]]:
    """Uma linha por (pessoa, papel, ato) — só a partir de `compra_venda`, o
    único tipo que TRANSFERE titularidade registral nesta matrícula.

    `papel_no_ato` (adquirente/transmitente) só existe quando o próprio ato o
    distingue — nunca por posição na lista. É a mesma lição do achado
    `partes[0]` do ADR-065 (doc 550: a ordem das partes não é estável entre
    execuções), aplicada a titularidade: o prompt só preenche
    `adquirentes`/`transmitentes` quando o texto nomeia os dois lados
    ("foi adquirido por X ... por compra feita a Y").
    """
    linhas: list[dict[str, Any]] = []
    for obs in observacoes:
        if obs.tipo != TIPO_COMPRA_VENDA:
            continue
        for papel, chave_papel in (("adquirente", "adquirentes"), ("transmitente", "transmitentes")):
            for nome in obs.atributos.get(chave_papel) or []:
                if not nome:
                    continue
                linhas.append({
                    "nome": nome, "papel_no_ato": papel, "ato": obs.ato,
                    "data_ato": obs.atributos.get("data_ato"), "ordem": obs.ordem,
                })
    return linhas


def titular_atual(observacoes: list[Observacao]) -> Optional[dict[str, Any]]:
    """O titular do ato de transferência (`compra_venda`) mais recente.

    "Sem ato posterior que o transfira" (ADR-066) é automático para o ÚLTIMO
    ato: por definição não há nenhum depois dele nesta matrícula. Os
    adquirentes de atos ANTERIORES aparecem em :func:`cadeia_titularidade`
    como titulares passados (e, no caso comum, como transmitentes do ato
    seguinte — mas isso não é verificado aqui: cada ato fala por si).

    None quando nenhum ato de compra e venda desta matrícula nomeia
    adquirente — a matrícula pode não ter tido transferência registrada, ou o
    texto não distinguiu os dois lados.
    """
    transferencias = [
        o for o in observacoes
        if o.tipo == TIPO_COMPRA_VENDA and o.atributos.get("adquirentes")
    ]
    if not transferencias:
        return None
    ultimo = max(transferencias, key=lambda o: o.ordem)
    return {
        "titulares": ultimo.atributos["adquirentes"],
        "ato": ultimo.ato,
        "data_ato": ultimo.atributos.get("data_ato"),
    }


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
