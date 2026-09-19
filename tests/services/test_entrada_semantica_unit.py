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
