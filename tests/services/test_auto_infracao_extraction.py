"""Fase 1 (N2) — auto de infração como fato de passivo. Testes das funções
puras (parse de coordenadas, cruzamento autuado×titular) e do lookup de
enquadramento (integração com knowledge_catalog)."""

from __future__ import annotations

from app.services.auto_infracao_extraction import (
    check_autuado_diverge_titular,
    lookup_enquadramento,
    parse_coordenadas,
)


class TestParseCoordenadas:
    def test_par_latlong_com_virgula_decimal(self):
        texto = "Área localizada nas coordenadas -14,236; -49,528, próxima ao rio."
        assert parse_coordenadas(texto) == (-14.236, -49.528)

    def test_par_latlong_com_ponto_decimal(self):
        assert parse_coordenadas("Coordenadas: -14.236 / -49.528") == (-14.236, -49.528)

    def test_sem_coordenadas_retorna_none(self):
        assert parse_coordenadas("Supressão de vegetação nativa sem autorização.") is None

    def test_texto_vazio_retorna_none(self):
        assert parse_coordenadas(None) is None
        assert parse_coordenadas("") is None

    def test_fora_de_faixa_valida_retorna_none(self):
        """999,999 não é uma coordenada válida — não deve "parsear" lixo."""
        assert parse_coordenadas("999,999; 999,999") is None


class TestCheckAutuadoDivergeTitular:
    def test_cpf_igual_ao_titular_nao_diverge(self):
        assert check_autuado_diverge_titular(
            "João Silva", "123.456.789-00",
            titular_nome="João Silva", titular_cpf="12345678900",
        ) is None

    def test_cpf_diferente_do_titular_diverge(self):
        nota = check_autuado_diverge_titular(
            "José Autuado", "111.111.111-11",
            titular_nome="João Silva", titular_cpf="12345678900",
        )
        assert nota is not None
        assert "titular atual" in nota

    def test_cpf_bate_com_proprietario_de_matricula_nao_diverge(self):
        assert check_autuado_diverge_titular(
            "Maria Proprietária", "222.222.222-22",
            titular_nome="João Silva", titular_cpf="12345678900",
            matricula_proprietarios=[{"nome": "Maria Proprietária", "cpf": "222.222.222-22"}],
        ) is None

    def test_sem_dados_do_autuado_nao_diverge(self):
        assert check_autuado_diverge_titular(None, None, titular_nome="João", titular_cpf="123") is None

    def test_sem_titular_para_comparar_nao_diverge_por_nome(self):
        """Sem CPF nem candidatos, cai no fallback de nome; sem nenhum
        candidato de nome também, não há o que comparar."""
        assert check_autuado_diverge_titular("José", None) is None


class TestLookupEnquadramento:
    def test_texto_vazio_retorna_lista_vazia(self, db_session):
        assert lookup_enquadramento(None, db_session=db_session) == []
        assert lookup_enquadramento("", db_session=db_session) == []

    def test_sem_citacao_parseavel_marca_nao_localizada(self, db_session):
        """Texto livre sem "Lei X/AAAA" reconhecível: ainda assim devolve um
        item marcado não localizado — nunca inventa fonte (Princípio 11)."""
        result = lookup_enquadramento("desmatamento em área de preservação", db_session=db_session)
        assert len(result) == 1
        assert result[0]["localizada"] is False

    def test_citacao_nao_localizada_no_corpus_vazio(self, db_session):
        """Sem nenhum LegislationDocument no knowledge_catalog do tenant de
        teste, a citação nunca é encontrada — resultado honesto."""
        result = lookup_enquadramento("Lei 9.605/98 art.70", db_session=db_session, tenant_id=999999)
        assert len(result) == 1
        assert result[0]["citacao"]
        assert result[0]["localizada"] is False
        assert result[0]["chunk_id"] is None
