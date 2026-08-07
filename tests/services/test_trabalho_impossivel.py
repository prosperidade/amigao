"""O sistema não cobra trabalho impossível (auditoria 06/08).

Duas frentes, mesma doença: o sistema pedindo ao consultor uma decisão que não
muda nada.

1. **Divergência sem destino virava Ação.** No caso 16, em produção, a
   consolidação criou a Ação id 49 — "Resolver divergência de vtn" — para um
   campo que não está na allowlist nem existe como coluna em `matriculas`.
   Nenhuma escolha de fonte faria aquele valor entrar na base.
2. **Órgão composto passava pelo guard da ADR-034.** `Rota.orgao_competente` do
   caso 16 diz "IBAMA (esfera federal) e ... SEMAD (esfera estadual)".
   `esfera_do_orgao` devolvia só a primeira que casa ("federal"), que É uma
   esfera do caso — então o guard aprovava a prosa inteira, metade errada
   inclusive, e a rota mandava defender na SEMAD um auto do IBAMA.
"""

from __future__ import annotations

from app.services.esfera import esfera_do_orgao, esferas_do_texto
from app.services.rota_materializer import orgao_fora_das_esferas
from app.services.staging_consolidation import destino_nao_existe_na_base

# Texto real do campo `orgao_competente` da rota 2 (processo 16) em produção.
ORGAO_COMPOSTO_CASO16 = (
    "IBAMA (esfera federal) e Secretaria de Estado de Meio Ambiente e "
    "Desenvolvimento Sustentável de Goiás - SEMAD (esfera estadual)"
)


# ---------------------------------------------------------------------------
# 1. Divergência sobre campo que não existe não é divergência
# ---------------------------------------------------------------------------

def test_vtn_nao_tem_coluna_em_lugar_nenhum():
    """O exemplar do defeito: `vtn` não existe como coluna em `matriculas`."""
    assert destino_nao_existe_na_base("matricula", "vtn") is True


def test_recusa_declarada_nao_e_ausencia_e_segue_gerando_trabalho():
    """A distinção que impede a correção de virar um novo sumiço.

    `total_area_ha` é recusado por DECISÃO (área do imóvel é derivada da soma
    das matrículas) — mas divergir entre o CAR e a soma é achado clássico. A
    recusa de `rat_data_emissao` diz textualmente que "a diferença entre eles
    aparece como divergência a resolver". Confundir "recusado por decisão" com
    "não existe" apagaria trabalho real do consultor.
    """
    assert destino_nao_existe_na_base("imovel", "total_area_ha") is False
    assert destino_nao_existe_na_base("imovel", "rat_data_emissao") is False
    assert destino_nao_existe_na_base("imovel", "rat_protocolo") is False


def test_campos_que_tem_casa_nunca_sao_descartados():
    assert destino_nao_existe_na_base("matricula", "cartorio") is False
    assert destino_nao_existe_na_base("matricula", "area_ha") is False
    assert destino_nao_existe_na_base("imovel", "car_code") is False
    assert destino_nao_existe_na_base("cliente", "full_name") is False
    # Alias staging→coluna continua valendo (`document` → `cpf_cnpj`).
    assert destino_nao_existe_na_base("cliente", "document") is False


def test_destino_sem_campo_ou_entidade_desconhecida_nao_existe():
    assert destino_nao_existe_na_base("matricula", None) is True
    assert destino_nao_existe_na_base("matricula", "   ") is True
    assert destino_nao_existe_na_base("planeta", "cartorio") is True


# ---------------------------------------------------------------------------
# 2. Esfera composta
# ---------------------------------------------------------------------------

def test_o_texto_do_caso16_nomeia_as_duas_esferas():
    """A medição que motivou o fix, em uma linha."""
    assert esferas_do_texto(ORGAO_COMPOSTO_CASO16) == {"federal", "estadual"}
    # A função de UMA esfera continua devolvendo uma só — é o contrato dela,
    # e é justamente por isso que o guard não podia depender dela aqui.
    assert esfera_do_orgao(ORGAO_COMPOSTO_CASO16) == "federal"


def test_caso_so_federal_acusa_a_metade_estadual_do_texto_composto():
    """O defeito exato: caso com autos do IBAMA aprovava a prosa inteira."""
    assert orgao_fora_das_esferas(ORGAO_COMPOSTO_CASO16, ["federal"]) is True


def test_caso_com_as_duas_esferas_aceita_o_texto_composto():
    assert orgao_fora_das_esferas(ORGAO_COMPOSTO_CASO16, ["federal", "estadual"]) is False


def test_orgao_simples_mantem_o_comportamento_de_antes():
    """Nada do que já funcionava muda de resposta."""
    assert orgao_fora_das_esferas("SEMAD-GO", ["federal"]) is True
    assert orgao_fora_das_esferas("IBAMA", ["federal"]) is False
    assert orgao_fora_das_esferas("IBAMA-GO", ["federal"]) is False
    # Não reconhecido continua não sendo acusado — na dúvida não se apaga.
    assert orgao_fora_das_esferas("Cliente / Advogado", ["federal"]) is False
    assert orgao_fora_das_esferas("Cartório de Registro de Imóveis", ["federal"]) is False
    # Sem esferas conhecidas do caso, o guard não age.
    assert orgao_fora_das_esferas(ORGAO_COMPOSTO_CASO16, []) is False


def test_pista_generica_nao_soma_esfera_a_orgao_ja_reconhecido():
    """"estado de" mora dentro do nome próprio da SEMAD.

    Se as pistas fracas somassem sempre, todo texto com "Secretaria de Estado
    de Meio Ambiente" contaria estadual duas vezes — e, pior, um texto só
    federal que citasse "Governo do Estado" de passagem viraria bi-esfera e
    seria acusado sem motivo.
    """
    assert esferas_do_texto("Superintendência do IBAMA em Goiás") == {"federal"}
    assert esferas_do_texto("") == set()
    assert esferas_do_texto(None) == set()
