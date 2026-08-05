"""Guarda de sanidade do chunker (#117) — fatia gigante não é artigo.

O `_split_by_pattern` assume que o documento é articulado do início ao fim: tudo
entre um cabeçalho e o próximo pertence àquele cabeçalho. Quando o texto **deixa
de ser articulado** (sumário paginado, rodapé de captura web, anexo, lista de
diretrizes), todo o rabo não-normativo é atribuído ao último cabeçalho visto.

Medido em 04/08: o `Art. 51.` do MT-NUC01 virou 374 pedaços de 261.280 tokens,
todos rotulados `"Art. 51. (parte N)"` — e dentro daquela fatia de 1.045.121
chars **não existe outro cabeçalho de artigo**. Não é fronteira perdida; é
ausência de fronteira. Nenhum regex melhor corrige, porque não há o que casar.

O dano não é o corte, é o **rótulo**: sumário de zoneamento etiquetado como
artigo de lei. Rótulo mentiroso é pior que ausência de rótulo — passa na
conferência.
"""

import logging

from app.services.chunking import (
    LIMITE_ARTIGO_TOKENS,
    MAX_ARTIGO_TOKENS,
    MAX_TOKENS,
    ROTULO_NAO_ARTICULADO,
    _CHARS_PER_TOKEN,
    chunk_text,
)


def _texto(tokens: int, recheio: str = "palavra ") -> str:
    """Bloco de texto com aproximadamente `tokens` tokens (4 chars/token)."""
    return (recheio * (tokens * _CHARS_PER_TOKEN // len(recheio) + 1))[
        : tokens * _CHARS_PER_TOKEN
    ]


def _rotulos(chunks):
    return [c.section or "" for c in chunks]


# --------------------------------------------------------------------------
# O que a guarda NÃO pode estragar
# --------------------------------------------------------------------------

def test_artigo_pequeno_continua_inteiro_e_rotulado():
    """Controle: o caso comum (p50 = 129 tokens) não é tocado."""
    texto = "Art. 70. Considera-se infração administrativa ambiental toda ação.\n"
    texto += "Art. 71. O processo administrativo observará os seguintes prazos.\n"

    chunks = chunk_text(texto)

    assert len(chunks) == 2
    assert chunks[1].section.startswith("Art. 71.")
    assert "(parte" not in chunks[1].section


def test_artigo_grande_LEGITIMO_mantem_o_rotulo_de_artigo():
    """Artigo extenso de verdade (o `Art. 61-A` tem 4.644 tokens) é cortado por
    tamanho — isso é a estratégia funcionando — e **continua sendo artigo**.

    Se a guarda pegasse este caso, ela trocaria um defeito por outro: o
    dispositivo perderia a identidade que ele legitimamente tem.
    """
    grande = (LIMITE_ARTIGO_TOKENS + MAX_TOKENS) // 2  # folgadamente dentro
    texto = f"Art. 61-A. Nas Areas de Preservacao Permanente.\n{_texto(grande)}\n"
    texto += "Art. 62. Nos casos de areas rurais consolidadas.\n"

    chunks = chunk_text(texto)
    rotulos = _rotulos(chunks)

    assert any(r.startswith("Art. 61-A.") for r in rotulos), (
        "artigo grande legitimo tem de manter o proprio rotulo"
    )
    assert not any(ROTULO_NAO_ARTICULADO in r for r in rotulos)


def test_preludio_gigante_nao_e_reetiquetado():
    """Ementa/cabeçalho antes do primeiro artigo também cai na passada
    estrutural e também pode ser gigante — mas **não alega ser artigo nenhum**.

    Não há etiqueta mentirosa para corrigir, então a guarda não o toca. Medido:
    4 prelúdios acima do limite, 474 chunks. Mexer neles seria alterar o que não
    está quebrado.
    """
    texto = f"DIARIO OFICIAL DO ESTADO\n{_texto(LIMITE_ARTIGO_TOKENS + 2000)}\n"
    texto += "Art. 1º Esta lei dispoe sobre.\nArt. 2º Revogam-se as disposicoes.\n"

    chunks = chunk_text(texto)

    assert not any(ROTULO_NAO_ARTICULADO in (c.section or "") for c in chunks)


# --------------------------------------------------------------------------
# O que a guarda existe para impedir
# --------------------------------------------------------------------------

def test_fatia_absorvedora_NAO_herda_o_rotulo_de_artigo():
    """O coração da #117.

    Um artigo curto seguido de 10.000 tokens de material não articulado (é o que
    acontece no compêndio: o artigo de vigência é a última coisa articulada e o
    anexo vem logo depois). Sem a guarda, tudo isso sai como
    `"Art. 38. (parte N)"` — sumário e formulário etiquetados como artigo de lei.
    """
    # Dois artigos: a passada estrutural so acontece quando o padrao quebra em
    # mais de uma fatia — como em qualquer norma real.
    texto = (
        "Art. 37. Os casos omissos serao resolvidos pelo orgao ambiental.\n"
        "Art. 38. Esta lei entra em vigor na data de sua publicacao.\n"
        + _texto(LIMITE_ARTIGO_TOKENS + 2000, "anexo tabela zoneamento pagina ")
    )

    chunks = chunk_text(texto)
    rotulos = _rotulos(chunks)

    assert not any(r.startswith("Art. 38.") for r in rotulos), (
        "nenhum pedaco pode continuar alegando ser o Art. 38"
    )
    assert any(r.startswith(ROTULO_NAO_ARTICULADO) for r in rotulos), (
        "o material tem de sair sob rotulo honesto"
    )
    # O artigo VIZINHO, que e legitimo, nao pode ser afetado: a guarda age na
    # fatia absorvedora, nao no documento inteiro.
    assert any(r.startswith("Art. 37.") for r in rotulos)


def test_o_conteudo_NAO_some_ao_cair_na_estrategia_alternativa():
    """Perder conteúdo seria trocar um defeito por outro.

    O material continua indexado; o que ele perde é a etiqueta falsa.
    """
    marca_inicio = "MARCADOR_PRIMEIRO"
    marca_fim = "MARCADOR_ULTIMO"
    texto = (
        "Art. 37. Os casos omissos serao resolvidos pelo orgao ambiental.\n"
        f"Art. 38. Esta lei entra em vigor. {marca_inicio}\n"
        + _texto(LIMITE_ARTIGO_TOKENS + 2000, "conteudo do anexo que precisa sobreviver ")
        + f"\n{marca_fim}"
    )

    chunks = chunk_text(texto)
    tudo = "\n".join(c.text for c in chunks)

    assert marca_inicio in tudo, "o inicio da fatia nao pode sumir"
    assert marca_fim in tudo, "o fim da fatia nao pode sumir"
    assert chunks, "a fatia tem de continuar produzindo chunks"


def test_a_guarda_NUNCA_age_em_silencio():
    """Estratégia alternativa é declarada, não silenciosa.

    Guarda que corrige calada vira o proximo defeito invisivel: ninguem descobre
    que 3.380 chunks mudaram de rotulo, nem por que.
    """
    texto = (
        "Art. 37. Os casos omissos serao resolvidos pelo orgao ambiental.\n"
        "Art. 38. Esta lei entra em vigor na data de sua publicacao.\n"
        + _texto(LIMITE_ARTIGO_TOKENS + 2000)
    )

    # Handler direto no logger do modulo: a configuracao de logging do projeto
    # instala handler proprio, e `caplog` sozinho nao ve o registro.
    class _Escuta(logging.Handler):
        def __init__(self):
            super().__init__(level=logging.WARNING)
            self.mensagens: list[str] = []

        def emit(self, record):
            self.mensagens.append(record.getMessage())

    escuta = _Escuta()
    log = logging.getLogger("app.services.chunking")
    log.addHandler(escuta)
    try:
        chunk_text(texto)
    finally:
        log.removeHandler(escuta)

    avisos = escuta.mensagens
    assert any("fatia_absorvedora" in m for m in avisos), (
        "a guarda tem de deixar rastro no log"
    )
    assert any("Art. 38" in m for m in avisos), (
        "o log precisa dizer QUAL rotulo foi recusado"
    )


def test_limite_esta_acima_do_maior_artigo_genuino_conhecido():
    """O limiar não foi escolhido no olho.

    Distribuição medida sobre 24.577 fatias de artigo em 102 documentos:
    p50=129, p90=499, p95=737, p99=2.144, p99,9=23.483, max=261.280.
    O maior artigo confirmadamente genuino do corpus tem ~6.289 tokens.
    """
    MAIOR_ARTIGO_GENUINO_MEDIDO = 6289
    assert LIMITE_ARTIGO_TOKENS > MAIOR_ARTIGO_GENUINO_MEDIDO
    assert LIMITE_ARTIGO_TOKENS > MAX_TOKENS


# --------------------------------------------------------------------------
# Teto do artigo (#118) — o corte por tamanho para de partir dispositivo
# --------------------------------------------------------------------------

def test_artigos_medidos_cabem_INTEIROS():
    """Os três que a Fase 2 tem de acomodar, medidos no corpus: 4.644 (Art. 61-A
    do Código Florestal), 5.578 (art. 100 da CF) e 6.289 (art. 19 da 6.938).

    Chunk grande demais dilui — o vetor vira um ponto que representa tudo
    vagamente e perde o dispositivo específico, que é o que a peça cita. Chunk
    pequeno demais parte o dispositivo. O tamanho certo é a unidade semântica do
    domínio: o artigo.
    """
    for medido in (4644, 5578, 6289):
        texto = (
            f"Art. 61-A. Dispositivo de {medido} tokens.\n{_texto(medido)}\n"
            "Art. 62. Artigo seguinte, curto.\n"
        )
        chunks = chunk_text(texto)
        do_artigo = [c for c in chunks if (c.section or "").startswith("Art. 61-A.")]

        assert len(do_artigo) == 1, (
            f"artigo de {medido} tokens foi partido em {len(do_artigo)} — "
            "o teto ainda corta dispositivo"
        )
        assert "(parte" not in (do_artigo[0].section or "")


def test_chunk_pequeno_continua_pequeno():
    """Subir o teto do artigo não pode inflar o caso comum (p50 = 129 tokens):
    o teto é limite, não alvo."""
    texto = "".join(
        f"Art. {n}. Dispositivo curto e objetivo sobre licenciamento.\n"
        for n in range(1, 12)
    )

    chunks = chunk_text(texto)

    assert all(c.tokens < 100 for c in chunks), (
        "artigo curto tem de continuar curto"
    )


def test_teto_ampliado_vale_SO_para_artigo():
    """Capítulo e seção seguem em MAX_TOKENS.

    Para eles, 7.000 tokens num chunk só não é "dispositivo inteiro" — é
    diluição. A unidade semântica do domínio é o artigo, não o capítulo.
    """
    grande = MAX_ARTIGO_TOKENS - 1000
    texto = (
        f"CAPITULO I\nDAS DISPOSICOES GERAIS\n{_texto(grande)}\n"
        f"CAPITULO II\nDO LICENCIAMENTO\n{_texto(200)}\n"
    )

    chunks = chunk_text(texto)

    assert any("(parte" in (c.section or "") for c in chunks), (
        "capitulo gigante tem de continuar sendo cortado por MAX_TOKENS"
    )
    assert all(c.tokens <= MAX_TOKENS for c in chunks)


def test_corte_por_tamanho_e_ultimo_recurso_E_deixa_rastro():
    """O corte não some — só deixa de ser a regra. Quando acontece, loga:
    dispositivo partido ao meio sem rastro significa busca devolvendo meio
    artigo sem ninguem ficar sabendo."""
    acima = MAX_ARTIGO_TOKENS + 500  # ainda abaixo da guarda (8.000)
    texto = (
        f"Art. 1º Artigo enorme.\n{_texto(acima)}\n"
        "Art. 2º Artigo seguinte.\n"
    )

    class _Escuta(logging.Handler):
        def __init__(self):
            super().__init__(level=logging.INFO)
            self.mensagens: list[str] = []

        def emit(self, record):
            self.mensagens.append(record.getMessage())

    escuta = _Escuta()
    log = logging.getLogger("app.services.chunking")
    nivel = log.level
    log.setLevel(logging.INFO)
    log.addHandler(escuta)
    try:
        chunks = chunk_text(texto)
    finally:
        log.removeHandler(escuta)
        log.setLevel(nivel)

    assert any("(parte" in (c.section or "") for c in chunks), (
        "acima do teto do artigo o corte por tamanho ainda vale"
    )
    assert any("artigo_cortado_por_tamanho" in m for m in escuta.mensagens), (
        "corte de artigo tem de deixar rastro"
    )


# --------------------------------------------------------------------------
# Estrutura da norma como dado (#119) — extração sim, navegação não
# --------------------------------------------------------------------------

_NORMA = """TITULO II
DAS AREAS DE PRESERVACAO PERMANENTE
CAPITULO I
DA DELIMITACAO
SECAO II
DO REGIME DE PROTECAO
Art. 61-A. Nas Areas de Preservacao Permanente, na forma do art. 12 da Lei 12.651/2012, e autorizada a continuidade.
Art. 62. Nos casos previstos no art. 61-A, observa-se o disposto no art. 225 da Constituicao Federal.
"""


def test_hierarquia_e_preservada():
    """O chunker corta pelo padrão mais granular e descartava os níveis acima.
    A hierarquia não precisa ser inferida — está escrita, só não era guardada.
    Medido antes: 12 chunks de 3.192 federais tinham rótulo hierárquico."""
    chunks = chunk_text(_NORMA)
    art61a = next(c for c in chunks if c.dispositivo == "61-A")

    assert art61a.hierarquia == {
        "titulo": "TITULO II",
        "capitulo": "CAPITULO I",
        "secao": "SECAO II",
    }


def test_dispositivo_vai_para_campo_proprio_nao_para_o_texto():
    """93,1% dos chunks federais mencionam um artigo e o número não estava em
    campo consultável — vivia dentro de `section`, como texto."""
    chunks = chunk_text(_NORMA)

    assert [c.dispositivo for c in chunks if c.dispositivo] == ["61-A", "62"]


def test_dispositivo_LIDO_e_distinguivel_de_HERDADO():
    """Campo preenchido por herança tem de ser distinguível de campo lido do
    texto. Rótulo herdado apresentado como lido é a família #121/#123.

    Num artigo partido por tamanho, só o primeiro pedaço contém o cabeçalho —
    os demais herdam, e dizem que herdaram.
    """
    grande = MAX_ARTIGO_TOKENS + 500  # forca o corte por tamanho
    texto = f"Art. 5º Dispositivo extenso.\n{_texto(grande)}\nArt. 6º Outro.\n"

    pedacos = [c for c in chunk_text(texto) if c.dispositivo == "5"]

    assert len(pedacos) > 1, "o artigo precisa ter sido partido para o teste valer"
    assert pedacos[0].dispositivo_origem == "lido"
    assert all(p.dispositivo_origem == "herdado" for p in pedacos[1:])


def test_referencia_com_norma_nomeada_e_extraida_com_o_alvo():
    chunks = chunk_text(_NORMA)
    art61a = next(c for c in chunks if c.dispositivo == "61-A")

    assert art61a.referencias == [
        {
            "artigo": "12",
            "norma_alvo": "Lei 12.651/2012",
            "formula": "na forma do",
            "trecho": "na forma do art. 12 da Lei 12.651/2012, e autorizada a continuidade.",
        }
    ]


def test_referencia_sem_norma_nomeada_NAO_e_adivinhada():
    """Quando o texto não nomeia a norma, o alvo é gravado como não declarado.

    Supor "é a norma atual" seria inferência apresentada como leitura — e
    referência que não resolve é **dado legítimo**, nunca descartada em silêncio
    nem consertada por aproximação.
    """
    chunks = chunk_text(_NORMA)
    art62 = next(c for c in chunks if c.dispositivo == "62")
    alvos = {r["norma_alvo"] for r in (art62.referencias or [])}

    assert "nao_declarado_no_texto" in alvos, (
        "a referencia ao art. 61-A nao nomeia norma — tem de ficar assim"
    )
    assert "Constituicao Federal" in alvos
    assert art62.referencias, "referencia nao resolvida NAO pode ser descartada"


def test_norma_alvo_so_conta_quando_segue_o_artigo_DIRETAMENTE():
    """Alvo errado é pior que alvo ausente, porque tem cara de dado.

    Em "art. 8 aplica-se conforme resolucao CONAMA 369" a resolução é OUTRA
    referência, não o alvo do art. 8.
    """
    from app.services.chunking import _extrair_referencias

    achadas = _extrair_referencias(
        "nos termos do art. 8 aplica-se conforme resolucao CONAMA 369"
    )

    assert achadas[0]["artigo"] == "8"
    assert achadas[0]["norma_alvo"] == "nao_declarado_no_texto"


def test_fatia_absorvedora_perde_o_dispositivo_mas_mantem_a_hierarquia():
    """A fatia não é aquele artigo — então não carrega o número dele. Mas ela
    está mesmo dentro daquele título/capítulo, e isso continua verdadeiro."""
    texto = (
        "TITULO I\nDAS DISPOSICOES GERAIS\n"
        "Art. 37. Os casos omissos serao resolvidos pelo orgao ambiental.\n"
        "Art. 38. Esta lei entra em vigor na data de sua publicacao.\n"
        + _texto(LIMITE_ARTIGO_TOKENS + 2000, "anexo tabela zoneamento pagina ")
    )

    absorvidos = [
        c for c in chunk_text(texto)
        if (c.section or "").startswith(ROTULO_NAO_ARTICULADO)
    ]

    assert absorvidos
    assert all(c.dispositivo is None for c in absorvidos), (
        "material absorvido nao pode alegar ser o artigo"
    )
    assert all(c.hierarquia == {"titulo": "TITULO I"} for c in absorvidos)


def test_referencia_SEM_formula_gatilho_nao_e_capturada_e_isso_e_o_escopo():
    """Limitação declarada, não escondida.

    A #119 mediu **329** referências federais por três fórmulas: "na forma do
    art." (27), "nos termos do art." (64) e "previsto/disposto no art." (238).
    Menção solta — *"o prazo do art. 225"* — fica de fora.

    É escolha de escopo: alargar o gatilho aumentaria a captura e também os
    falsos positivos, e o número que justifica a fase é o das três fórmulas.
    Quem ler o campo `referencias` precisa saber que ele não é exaustivo.
    """
    from app.services.chunking import _extrair_referencias

    assert _extrair_referencias("observa-se o prazo do art. 225 da Constituicao") == []
    assert _extrair_referencias("nos termos do art. 225 da Constituicao") != []
