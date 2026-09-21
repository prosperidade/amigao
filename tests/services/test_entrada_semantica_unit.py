"""Recorte puro; cenários sintéticos, não substituem os casos reais do gate."""
import unittest
from datetime import date
from decimal import Decimal

from app.schemas.entrada_semantica import FalecimentoDeclarado, ParteExtraida, ParticipacaoExtraida
from app.services.identidade_observacao import identidade_observacao, localizar_trecho, normalizar_conteudo
from app.services.motor_cartorario import (
    AtoMaterial,
    IdentidadeAto,
    avaliar_material,
    avaliar_matriculas,
    qualificar_representacao,
)
from app.services.property_audit import audit_property
from app.services.taxonomia_documental import destino_consolidavel, propor_especie


class EntradaSemanticaTests(unittest.TestCase):
    def test_certidao_eletronica_nao_cai_no_tipo_indeterminado(self):
        # Synthetic title variants, no real document text or personal data.
        for modifier in ("", "Eletrônica "):
            title = "Certidão " + modifier + "de Inteiro Teor da Matrícula"
            self.assertEqual(propor_especie(title, "matricula"), "certidao_matricula")

    def test_destino_nao_promove_area_de_escritura_a_area_registral(self):
        self.assertIsNone(destino_consolidavel("escritura_publica", "area_documental_ha"))
        self.assertIsNone(destino_consolidavel("contrato_servico_documental", "car_area_ha"))
        self.assertEqual(destino_consolidavel("certidao_matricula", "area_documental_ha"), ("matricula", "area_ha"))

    def test_falecido_e_espolio_no_mesmo_trecho_nao_colidem(self):
        a = {"chave": "falecido"}
        b = {"chave": "espolio"}
        self.assertNotEqual(identidade_observacao(558, 1, 1, "parte", a, 0, 30),
                            identidade_observacao(558, 1, 1, "parte", b, 0, 30))

    def test_quatro_matriculas_mesmo_cartorio_nao_compartilham_saldo(self):
        # Real document/matricula identifiers supplied by the user; transfers
        # below are synthetic controls, not reconstructed ELODI contents.
        acts = [AtoMaterial(IdentidadeAto(doc, numero, "Cartório comum", "R.1"),
            "compra_venda", date(2020, 1, 1), 1,
            transmitentes={"A": Decimal(1)}, adquirentes={f"B-{numero}": Decimal(1)})
            for doc, numero in ((547, "3.181"), (548, "3.313"), (549, "3.673"), (550, "4.387"))]
        ref = date(2026, 9, 18)
        contexts = {(a.identidade.serventia, a.identidade.matricula): {
            "especie": "certidao_matricula", "cobertura_completa": True,
            "data_certidao": ref, "saldo_inicial": {"A": Decimal(1)}} for a in acts}
        result = avaliar_matriculas(atos=acts, data_referencia=ref, contexto_por_matricula=contexts)
        self.assertEqual(len(result), 4)
        for row in result:
            self.assertEqual(len(row["documentos"]), 1)
            self.assertEqual(row["participacoes_derivadas"], {f"B-{row['matricula']}": "1"})
        with self.assertRaises(ValueError):
            avaliar_material(especie="certidao_matricula", atos=acts, data_referencia=ref)

    def test_inventariante_declarado_em_contrato_sobrevive_sem_poderes(self):
        p = ParticipacaoExtraida(parte_chave="representante", papel="inventariante",
            representado_chave="espolio", trecho="inventariante", inicio=date(2022, 1, 1), posicao_inicio=35)
        self.assertEqual(p.inicio, date(2022, 1, 1))
        self.assertEqual(p.posicao_inicio, 35)
        out = qualificar_representacao(especie="contrato_servico_documental", alcance=None, inicio=p.inicio,
            fim=None, representado=p.representado_chave, data_referencia=date(2026, 9, 18))
        self.assertEqual(out["estado_confirmacao"], "declarado")
        self.assertEqual(out["poderes_na_data"], "nao_determinado")
        self.assertIn("documento_de_nomeacao_ou_poderes", out["lacunas"])

    def test_pf_falecida_e_espolio_sao_partes_distintas(self):
        falecido = ParteExtraida(chave="falecido", nome="Pessoa do caso", natureza="pf",
            trecho="TITULAR FALECIDO")
        declaracao = FalecimentoDeclarado(sujeito=falecido.chave, trecho="TITULAR FALECIDO")
        espolio = ParteExtraida(chave="espolio", nome="Espólio da pessoa do caso", natureza="espolio",
            falecido_chave=falecido.chave, inventario="5286960-36.2022.8.09.0051", trecho="ESPÓLIO")
        self.assertEqual(falecido.natureza, "pf")
        self.assertEqual(declaracao.predicado, "falecimento_declarado")
        self.assertIsNone(declaracao.data)
        self.assertIsNone(espolio.identificador)
        self.assertEqual(espolio.falecido_chave, falecido.chave)

    def test_aliases_documentais_do_recorte_producao(self):
        self.assertEqual(propor_especie("", "cpf_cnpj"), "documento_pessoal")
        self.assertEqual(propor_especie("", "doc_pessoal"), "documento_pessoal")
        self.assertEqual(propor_especie("", "kml_sigef"), "arquivo_geoespacial")

    def test_identidade_nao_depende_da_formatacao_do_valor(self):
        a = {"predicado": "valor_negocio", "valor": "R$150.000,00"}
        b = {"predicado": "valor_negocio", "valor": "R$ 150.000,00"}
        self.assertEqual(normalizar_conteudo(a), normalizar_conteudo(b))
        self.assertEqual(identidade_observacao(559, 1, 1, "observacao", a, 100, 140),
                         identidade_observacao(559, 1, 1, "observacao", b, 100, 140))
        self.assertNotEqual(identidade_observacao(559, 1, 1, "observacao", a, 100, 140),
                            identidade_observacao(999, 1, 1, "observacao", a, 100, 140))

    def test_trecho_repetido_exige_posicao(self):
        with self.assertRaises(ValueError):
            localizar_trecho("ATO ATO", "ATO")
        self.assertEqual(localizar_trecho("ATO ATO", "ATO", 4), 4)

    def test_escritura_nao_herda_matricula(self):
        self.assertEqual(propor_especie("ESCRITURA PÚBLICA de compra e venda", "matricula"), "escritura_publica")
        self.assertEqual(propor_especie("CONTRATO PARTICULAR", "matricula"), "contrato_particular")
        self.assertEqual(propor_especie("CERTIDÃO DE INTEIRO TEOR", "matricula"), "certidao_matricula")

    def test_escritura_nao_prova_estado_atual(self):
        out = avaliar_material(especie="escritura_publica", atos=[], data_referencia=date(2026, 9, 18))
        self.assertEqual(out["estado_titularidade"], "nao_determinado")
        self.assertTrue(any("certidao_adequada" in x for x in out["lacunas"]))

    def test_transmissao_parcial_preserva_saldo(self):
        ato = AtoMaterial(IdentidadeAto(1, "M1", "CNS1", "R.1"), "compra_venda", date(2020, 1, 1), 1,
            transmitentes={"A": Decimal("0.25")}, adquirentes={"B": Decimal("0.25")})
        out = avaliar_material(especie="certidao_matricula", atos=[ato], data_referencia=date(2026, 9, 18),
            cobertura_completa=True, data_certidao=date(2026, 9, 18), saldo_inicial={"A": Decimal("1")})
        self.assertEqual(out["participacoes_derivadas"], {"A": "0.75", "B": "0.25"})

    def test_cadeia_incompleta_nao_escolhe_ultimo(self):
        ato = AtoMaterial(IdentidadeAto(1, "M1", "CNS1", "R.99"), "compra_venda", date(2020, 1, 1), 99,
            transmitentes={"A": Decimal(1)}, adquirentes={"B": Decimal(1)})
        out = avaliar_material(especie="certidao_matricula", atos=[ato], data_referencia=date(2026, 9, 18))
        self.assertEqual(out["participacoes_derivadas"], {})

    def test_referencia_de_outra_matricula_nao_resolve(self):
        ato = AtoMaterial(IdentidadeAto(1, "M1", "CNS1", "AV.1"), "hipoteca", date(2020, 1, 1), 1)
        baixa = AtoMaterial(IdentidadeAto(1, "M1", "CNS1", "AV.2"), "baixa", date(2021, 1, 1), 2,
            alvo=IdentidadeAto(1, "M2", "CNS1", "AV.1"), relacao="baixa")
        out = avaliar_material(especie="certidao_matricula", atos=[ato, baixa], data_referencia=date(2026, 9, 18))
        self.assertEqual(out["relacoes"], [])
        self.assertTrue(any("vinculo_explicito" in x for x in out["lacunas"]))

    def test_quatro_confrontos_recebem_payload_aninhado(self):
        rows = audit_property(property_data={"area_documental_ha": 100}, extracted_data={"extracted_fields": {
            "car_area_ha": 110, "ccir_area_ha": 120, "itr_area_ha": 130}})
        areas = [r for r in rows if r.familia == "area"]
        self.assertEqual(len(areas), 4)
        self.assertTrue(all(r.evidencia["area_a_ha"] and r.evidencia["area_b_ha"] for r in areas))


if __name__ == "__main__":
    unittest.main()


def test_ancora_recupera_layout_mas_preserva_literal_e_posicao():
    from app.services.identidade_observacao import resolver_ancora_literal
    texto = "Cabeçalho\nÁrea:\n  12,3 ha\nFim"
    trecho, inicio = resolver_ancora_literal(texto, "Área: 12,3 ha")
    assert trecho == "Área:\n  12,3 ha"
    assert texto[inicio:inicio + len(trecho)] == trecho


def test_ancora_layout_repetido_exige_posicao():
    import pytest

    from app.services.identidade_observacao import resolver_ancora_literal
    texto = "Área:\n12 ha; Área:\n12 ha"
    with pytest.raises(ValueError, match="repetido"):
        resolver_ancora_literal(texto, "Área: 12 ha")
    assert resolver_ancora_literal(texto, "Área: 12 ha", 13)[1] == 13


def test_ancora_nao_corrige_numero_ou_pontuacao():
    import pytest

    from app.services.identidade_observacao import resolver_ancora_literal
    with pytest.raises(ValueError, match="não existe"):
        resolver_ancora_literal("Área:\n12,3 ha", "Área: 12.3 ha")


def test_offset_global_disambiguates_and_invalid_item_does_not_stop_others():
    from app.services.entrada_semantica import validar_proposta
    text = "same | same | unique"
    valid, rejected = validar_proposta({"observacoes": [
        {"predicado": "x", "valor": 1, "trecho": "same"},
        {"predicado": "y", "valor": 2, "trecho": "same", "posicao_inicio": 7, "posicao_fim": 11},
        {"predicado": "z", "valor": 3, "trecho": "unique"}]}, text, 0, len(text))
    assert [o.predicado for o in valid.observacoes] == ["y", "z"]
    assert [(o.posicao_inicio, o.posicao_fim) for o in valid.observacoes] == [(7, 11), (14, 20)]
    assert len(rejected) == 1 and "repetido" in rejected[0]["motivo"]


def test_offset_outside_chunk_and_wrong_offset_on_repeated_literal_are_rejected():
    from app.services.entrada_semantica import validar_proposta
    valid, rejected = validar_proposta({"observacoes": [
        {"predicado": "x", "valor": 1, "trecho": "first", "posicao_inicio": 0, "posicao_fim": 5},
        {"predicado": "y", "valor": 2, "trecho": "last", "posicao_inicio": 6, "posicao_fim": 9}]}, "first last last", 6, 15)
    assert not valid.observacoes and len(rejected) == 2
    assert rejected[1]["motivo"].startswith("Offsets nao correspondem ao trecho literal; Trecho repetido")


def test_wrong_offsets_on_unique_literal_are_replaced_by_its_only_position():
    from app.services.entrada_semantica import validar_proposta
    text = "Header. TITULAR FALECIDO em 2022. Fim"
    valid, rejected = validar_proposta({"observacoes": [
        {"predicado": "situacao", "valor": "x", "trecho": "TITULAR FALECIDO", "posicao_inicio": 5, "posicao_fim": 21}]},
        text, 0, len(text))
    assert not rejected
    assert (valid.observacoes[0].posicao_inicio, valid.observacoes[0].posicao_fim) == (8, 24)


def test_rejected_party_invalidates_only_its_dependent_claim():
    from app.services.entrada_semantica import validar_proposta
    valid, rejected = validar_proposta({"partes": [{"chave": "p", "nome": "Name", "natureza": "pf", "trecho": "missing"}],
        "participacoes": [{"parte_chave": "p", "papel": "adquirente", "trecho": "buyer"}],
        "observacoes": [{"predicado": "area", "valor": 1, "trecho": "area"}]}, "buyer area", 0, 10)
    assert not valid.partes and not valid.participacoes
    assert len(valid.observacoes) == 1 and len(rejected) == 2
    assert rejected[1] == {"colecao": "participacoes", "indice": 0, "motivo": "Dependência de parte rejeitada",
                           "posicao_inicio": 0, "posicao_fim": 5}


def test_registry_rejects_contract_proposal_without_losing_valid_act():
    from app.services.entrada_semantica import validar_proposta
    valid, rejected = validar_proposta({"atos": [{"natureza": "compra", "especie": "registro", "ordem": 1, "trecho": "R-1"}],
        "contratos": [{"objeto": "unsupported", "trecho": "contract"}]}, "R-1 contract", 0, 12, especie="certidao_matricula")
    assert len(valid.atos) == 1 and not valid.contratos
    assert len(rejected) == 1 and rejected[0]["colecao"] == "contratos"


# Synthetic material only. Each case below once failed the whole document.
DEED = "A vende a B. B adquire. C representa D. Consulta 2022."


def test_unknown_represented_party_rejects_only_that_participation():
    from app.services.entrada_semantica import validar_proposta
    valid, rejected = validar_proposta({"partes": [
        {"chave": "a", "nome": "A", "natureza": "pf", "trecho": "A vende"},
        {"chave": "b", "nome": "B", "natureza": "pf", "trecho": "B adquire"},
        {"chave": "c", "nome": "C", "natureza": "pf", "trecho": "C representa"}],
        "participacoes": [
        {"parte_chave": "a", "papel": "transmitente", "trecho": "A vende"},
        {"parte_chave": "c", "papel": "representante", "representado_chave": "d", "trecho": "C representa D"},
        {"parte_chave": "b", "papel": "adquirente", "trecho": "B adquire"}]}, DEED, 0, len(DEED))
    assert [p.papel for p in valid.participacoes] == ["transmitente", "adquirente"]
    assert [p.chave for p in valid.partes] == ["a", "b", "c"]
    assert [(r["colecao"], r["indice"], r["motivo"]) for r in rejected] == [
        ("participacoes", 1, "Representado sem parte extraída")]


def test_schema_invalid_item_is_rejected_alone_without_echoing_input():
    from app.services.entrada_semantica import validar_proposta
    valid, rejected = validar_proposta({"partes": [
        {"chave": "e", "nome": "SECRET NAME", "natureza": "espolio", "identificador": "1", "tipo_identificador": "cpf",
         "falecido_chave": "a", "trecho": "D."},
        {"chave": "a", "nome": "A", "natureza": "pf", "trecho": "A vende"}],
        "observacoes": [{"predicado": "p", "trecho": "B adquire"}], "extra": []}, DEED, 0, len(DEED))
    assert [p.chave for p in valid.partes] == ["a"] and not valid.observacoes
    assert [(r["colecao"], r["indice"]) for r in rejected] == [("extra", None), ("partes", 0), ("observacoes", 0)]
    assert "Espólio exige falecido" in rejected[1]["motivo"] and "SECRET" not in str(rejected)


def test_duplicate_key_and_estate_of_rejected_person_cascade_to_dependents():
    from app.services.entrada_semantica import validar_proposta
    valid, rejected = validar_proposta({"partes": [
        {"chave": "a", "nome": "A", "natureza": "pf", "trecho": "A vende"},
        {"chave": "a", "nome": "A", "natureza": "pf", "trecho": "A vende a B"},
        {"chave": "e", "nome": "Espólio de A", "natureza": "espolio", "falecido_chave": "a", "trecho": "D."},
        {"chave": "c", "nome": "C", "natureza": "pf", "trecho": "C representa"}],
        "participacoes": [{"parte_chave": "c", "papel": "inventariante", "representado_chave": "e",
                           "trecho": "C representa D"}],
        "falecimentos_declarados": [{"sujeito": "a", "trecho": "Consulta 2022."}]}, DEED, 0, len(DEED))
    assert [p.chave for p in valid.partes] == ["c"] and not valid.participacoes and not valid.falecimentos_declarados
    assert [(r["colecao"], r["indice"], r["motivo"]) for r in rejected] == [
        ("falecimentos_declarados", 0, "Falecimento declarado exige trecho TITULAR FALECIDO"),
        ("partes", 0, "Chave de parte duplicada no documento"),
        ("partes", 1, "Chave de parte duplicada no documento"),
        ("partes", 2, "Dependência de parte rejeitada"),
        ("participacoes", 0, "Dependência de parte rejeitada")]


def test_literal_support_is_checked_per_item_before_persistence():
    from app.services.entrada_semantica import validar_proposta
    text = "TITULAR FALECIDO. A, CPF 123. Contrato com processo 5286960-36.2022. A, CPF 123."
    valid, rejected = validar_proposta({"partes": [
        {"chave": "a", "nome": "A", "natureza": "pf", "identificador": "123", "tipo_identificador": "cpf",
         "trecho": "A, CPF 123"},
        {"chave": "b", "nome": "A", "natureza": "pf", "identificador": "123", "tipo_identificador": "cpf",
         "trecho": "A, CPF 123", "posicao_inicio": 18, "posicao_fim": 28}],
        "falecimentos_declarados": [{"sujeito": "b", "ano": 2021, "trecho": "TITULAR FALECIDO"},
                                    {"sujeito": "b", "trecho": "TITULAR FALECIDO"}],
        "contratos": [{"objeto": "x", "referencia_processo_judicial": ["9999999-00.2022"], "trecho": "Contrato com processo"}]},
        text, 0, len(text), especie="comprovante_situacao_cadastral_cpf")
    assert [p.chave for p in valid.partes] == ["b"] and len(valid.falecimentos_declarados) == 1
    assert [(r["colecao"], r["motivo"]) for r in rejected] == [
        ("partes", "Trecho repetido exige posição explícita; primeira ocorrência não vence"),
        ("contratos", "Objeto contratual não sustentado pela espécie documental"),
        ("falecimentos_declarados", "Ano de falecimento ausente do trecho")]


def test_identifier_absent_from_party_anchor_rejects_the_party():
    from app.services.entrada_semantica import validar_proposta
    valid, rejected = validar_proposta({"partes": [
        {"chave": "a", "nome": "A", "natureza": "pf", "identificador": "999", "tipo_identificador": "cpf",
         "trecho": "A vende"}]}, DEED, 0, len(DEED))
    assert not valid.partes and rejected[0]["motivo"] == "Identificador ou inventário ausente do trecho da parte"


def test_response_that_is_not_an_object_fails_whole():
    import pytest

    from app.services.entrada_semantica import validar_proposta
    with pytest.raises(ValueError, match="não é objeto JSON"):
        validar_proposta([], DEED, 0, len(DEED))
