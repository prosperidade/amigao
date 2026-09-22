"""Desmembramento por regra fixa, identidade canônica e dispositivos (ADR-075 §5, A1).

Os textos imitam os formatos MEDIDOS nas coletâneas do dev (22/09): bloco de
impressão no fim da página (MS/MT/GO), URL e "n/m" em linhas separadas (AC),
URL truncada que perde um caractere na página 10, paginação solta que é código
CNAE, ficha do portal LEGIS antes da lei.
"""

from __future__ import annotations

from app.services.zona_normativa.desmembramento import desmembrar
from app.services.zona_normativa.dispositivos import extrair_dispositivos
from app.services.zona_normativa.hierarquia import tipo_e_nivel_semad
from app.services.zona_normativa.identidade import (
    identidade_de_cabecalho,
    identidade_de_identificador,
)


def _pagina(corpo: str, titulo: str, url: str, n: int, m: int) -> str:
    return f"{corpo}\n10/05/2026, 18:31 {titulo}\n{url} {n}/{m}\n\n"


def test_identidade_nunca_string_crua():
    a = identidade_de_identificador("Res. CONAMA 369/2006", scope="federal", uf=None, agency=None)
    b = identidade_de_cabecalho("RESOLUÇÃO CONAMA Nº 369, DE 28 DE MARÇO DE 2006", ente_padrao="ms")
    assert a.chave == b.chave == "resolucao|br|conama|369|2006"   # CONAMA é federal em qualquer coletânea
    assert identidade_de_identificador("IN SEMAD-GO 01/2024", scope="estadual", uf="GO",
                                       agency=None).chave == "in|go|semad|1|2024"


def test_decreto_estadual_nao_e_federal():
    go = identidade_de_identificador("Decreto GO 9.710/2020", scope="estadual", uf="GO", agency=None)
    br = identidade_de_identificador("Decreto 9.710/2020", scope="federal", uf=None, agency=None)
    assert go.chave != br.chave     # Parecer 84: "Decreto Federal 9.710/2020" é de Goiás


def test_identidade_sem_ano_ou_orgao_nao_fecha():
    assert not identidade_de_cabecalho("L6938", ente_padrao="br").determinada           # título do Planalto
    assert not identidade_de_cabecalho("PORTARIA Nº 183/2020", ente_padrao="go").determinada  # sem órgão
    assert identidade_de_cabecalho("PORTARIA Nº 131/2018/GS/SINFRA", ente_padrao="mt").chave == \
        "portaria|mt|sinfra|131|2018"
    assert identidade_de_cabecalho("LEI ORDINÁRIA Nº 1022, DE 21 DE JANEIRO 1992", ente_padrao="ac").ano == 1992


def test_troca_de_url_corta_e_titulo_confirma():
    t = (
        _pagina("DECRETO Nº 16.588 DE 12/03/2025\nDispõe sobre X.\nArt. 1º Fica...", "DECRETO Nº 16.588 DE 12/03/2025",
                "https://aacpdappls.net.ms.gov.br/ato/aaa", 1, 2)
        + _pagina("Art. 2º Segue.", "DECRETO Nº 16.588 DE 12/03/2025", "https://aacpdappls.net.ms.gov.br/ato/aaa", 2, 2)
        + _pagina("LEI Nº 6.160 DE 18/12/2023\nInstitui Y.\nArt. 1º ...", "LEI Nº 6.160 DE 18/12/2023",
                  "https://aacpdappls.net.ms.gov.br/ato/bbb", 1, 1)
    )
    segs = desmembrar(t, "ms")
    assert [s.identidade.chave for s in segs] == ["decreto|ms||16588|2025", "lei|ms||6160|2023"]
    assert all(s.sinal == "impressao" for s in segs)
    assert "10/05/2026" not in segs[0].texto and "aacpdappls" not in segs[0].texto   # mobiliário sai
    assert segs[0].pagina_inicio == 1 and segs[0].pagina_fim == 2


def test_url_truncada_na_pagina_10_nao_parte_o_documento():
    base = "app1.sefaz.mt.gov.br/sistema/legislacao/legislacaotribut.nsf/173e6c0d2202fdcb03258b1700659f1e/5cca3a70942e8d0a03258"
    t = "DECRETO Nº 1.031, DE 2 DE JUNHO DE 2017\nRegulamenta Z.\n"
    for n in range(1, 12):
        url = base + ("d4600560…" if n >= 10 else "d46005601…")
        t += _pagina(f"Art. {n} texto.", "app1.sefaz.mt.gov.br/x", "https://" + url, n, 11)
    segs = desmembrar(t, "mt")
    assert len(segs) == 1 and segs[0].pagina_fim == 11


def test_paginacao_solta_nao_e_sinal():
    t = ("DECRETO Nº 262, DE 16 DE OUTUBRO DE 2019\nInstitui a APF.\nArt. 1º Tabela:\n"
         "Criação de equinos MÉDIO 0152-\n1/01\nTratamento de sementes 0141-\n5/01\n")
    segs = desmembrar(t, "mt")
    assert len(segs) == 1 and segs[0].identidade.chave == "decreto|mt||262|2019"


def test_acre_url_e_pagina_em_linhas_separadas_e_ficha_do_portal():
    t = (
        "26/04/2026, 14:47\nLEGIS :: Portal da Legislação do Estado do Acre\n\nCompilado\nESTADO DO ACRE\n"
        "LEI ORDINÁRIA Nº 1022, DE 21 DE JANEIRO 1992\n\nLEI N. 1.022, DE 21 DE JANEIRO DE 1992\n"
        "Dispõe sobre o conselho.\nArt. 1º Fica criado.\nhttps://legis.ac.gov.br/detalhar/3218\n\n\n\n1/1\n\n"
    )
    segs = desmembrar(t, "ac")
    assert len(segs) == 1
    assert segs[0].identidade.chave == "lei|ac||1022|1992"
    assert "LEGIS :: Portal" not in segs[0].texto


def test_cabecalho_citado_no_meio_nao_corta_e_sem_sinal_fica_marcado():
    t = (
        "Texto solto de abertura sem cabeçalho nenhum, repetido para passar do mínimo. " * 8 + "\n"
        "LEI Nº 9.523, DE 20 DE ABRIL DE 2011\nDispõe sobre o zoneamento.\nArt. 1º Conforme\n"
        "LEI Nº 12.651, DE 25 DE MAIO DE 2012\nno meio do texto, sem abertura depois.\nArt. 2º Fim.\n"
    )
    segs = desmembrar(t, "mt")
    assert [s.sinal for s in segs] == ["sem_sinal", "cabecalho_formal"]
    assert "regiao_sem_sinal_de_fronteira" in segs[0].motivos and not segs[0].determinado
    assert segs[1].identidade.chave == "lei|mt||9523|2011"


def test_dispositivos_regra_de_ordem_paragrafos_e_anexo():
    t = (
        "LEI Nº 1, DE 2020\nEmenta.\nArt. 1º A lei altera outra:\n"
        "Art. 3º texto citado da lei alterada, sem aspas.\n"
        "Art. 2º Segundo artigo.\n§ 1º Primeiro parágrafo.\n§ 2º Segundo.\n"
        "Art. 18. Descumprimento.\nParágrafo único. Único.\nANEXO I\nArt. 5 da tabela\n"
    )
    ds = extrair_dispositivos(t)
    arts = [d.artigo for d in ds if d.tipo == "artigo"]
    # LIMITAÇÃO CONHECIDA, registrada: citação SEM aspas com número MAIOR que o
    # corrente abre artigo ("Art. 3º" citado), e o "Art. 2º" real vira texto dele.
    # A regra de ordem só protege contra citação de número menor. Norma de
    # alteração passa pela revisão humana antes de ser validada.
    assert arts == ["1", "3", "18"]
    assert [d.tipo for d in ds][0] == "preambulo" and ds[-1].tipo == "anexo"
    art18 = next(d for d in ds if d.artigo == "18")
    assert [f.paragrafo for f in art18.filhos] == ["unico"]


def test_dispositivo_citado_fora_de_ordem_fica_no_corrente():
    ds = extrair_dispositivos("Art. 1º Um.\nArt. 5º Cinco.\nArt. 3º citado.\nArt. 6º Seis.\n")
    assert [d.artigo for d in ds] == ["1", "5", "6"]
    assert "Art. 3º citado" in next(d for d in ds if d.artigo == "5").texto


def test_semad_nome_do_arquivo_separa_tipologia_de_tr():
    assert tipo_e_nivel_semad("matriz_ipe", "A2.1 - Silvicultura LICENÇA AMBIENTAL ÚNICA - LAU.pdf")[0] == \
        "ficha_tipologia"
    assert tipo_e_nivel_semad("norma_procedural", "TERMO_DE_REFERÊNCIA_RELATÓRIO.pdf")[:2] == \
        ("termo_referencia", "exigencia")
    assert tipo_e_nivel_semad("norma_procedural", "tipologias_disponiveis (7).pdf")[1] == "nao_determinado"
    assert tipo_e_nivel_semad("manual_ipe", "Manual AUMPF.pdf")[1] == "procedimento"


def test_artigo_quebrado_em_linha_e_hifen_de_frase():
    # Medido no dev: "Art. \n79." (Decreto 6.514 — descumprir embargo) sumia; "Art. 2º- A
    # licença" (CONAMA 237) virava art. 2-A e o "Art. 8º - O órgão" virava 8-O.
    ds = extrair_dispositivos(
        "Art. 1º Um.\nArt. 2º- A licença ambiental.\nArt. \n79. Descumprir embargo.\n"
        "Art. 80 - O órgão.\nArt. 80-A. Acrescido.\n"
    )
    assert [d.artigo for d in ds if d.tipo == "artigo"] == ["1", "2", "79", "80", "80-A"]


def test_impressao_com_dois_atos_e_cortada():
    # Medido: a EC MT 115/2023 vinha com o texto da LC MT 592/2017 dentro da mesma
    # impressão; marcar não bastava, quem buscava a LC achava a EC.
    t = (
        _pagina("EMENDA CONSTITUCIONAL Nº 115, DE 2023\nESTADO DE MATO GROSSO\nDispõe sobre o CAR.\nArt. 1º Fica.",
                "EC 115", "https://app1.sefaz.mt.gov.br/x", 1, 2)
        + _pagina("ESTADO DE MATO GROSSO\nLEI COMPLEMENTAR Nº 592, DE 26 DE MAIO DE 2017\n"
                  "Dispõe sobre o PRA.\nArt. 10 O Cadastro Ambiental Rural não autoriza atividade.",
                  "EC 115", "https://app1.sefaz.mt.gov.br/x", 2, 2)
    )
    segs = desmembrar(t, "mt")
    assert [s.identidade.chave for s in segs] == ["emenda_constitucional|mt||115|2023",
                                                  "lei_complementar|mt||592|2017"]
    assert all("multiplos_atos_na_impressao" in s.motivos for s in segs)


def test_segmento_absorvedor_perde_a_identidade():
    # Medido: o cabeçalho "RESOLUÇÃO CMN Nº 5.193" abriu um segmento de 565 mil
    # caracteres no MT-NUC07 (a resolução real tem 11,8 mil) e disputava vagas.
    cabeca = ("ESTADO DE MATO GROSSO\nRESOLUÇÃO CMN Nº 5.193, DE 19 DE DEZEMBRO DE 2024\n"
              "Dispõe sobre crédito rural.\nArt. 1º Fica instituído.\n")
    engolido = "Tabela de operações de crédito rural sem articulação nenhuma. " * 900
    grande = next(s for s in desmembrar(cabeca + engolido, "mt") if s.sinal == "cabecalho_formal")
    assert "segmento_absorvedor" in grande.motivos and not grande.determinado
    # O mesmo cabeçalho, com o ato articulado, continua com identidade.
    ok = cabeca + "".join(f"Art. {n} texto do artigo com algum conteúdo.\n" for n in range(2, 60))
    articulado = next(s for s in desmembrar(ok, "mt") if s.sinal == "cabecalho_formal")
    assert articulado.identidade.chave == "resolucao|br|cmn|5193|2024" and articulado.motivos == []
