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
