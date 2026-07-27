"""A maçaneta do gate E2→E3: transformar a análise do agente em algo assinável.

Contexto medido no processo 15 (26/07): 2 jobs de diagnóstico concluídos, ZERO
linhas em `regulatory_diagnoses`, e o gate cobrando "diagnóstico assinado". O
`content` produzido aqui é o que passa (ou não) no gate Pydantic do POST — por
isso os testes validam contra o schema real, não contra um dict qualquer.
"""

import pytest

from app.schemas.stage_output import validate_diagnostic_content
from app.services.diagnosis_materializer import (
    DiagnosisMaterializationError,
    build_content_from_job_result,
)


class TestBuildContent:
    def test_result_novo_vira_content_valido(self):
        result = {
            "content": "Imóvel com CAR pendente e auto de infração federal em aberto.",
            "hipoteses": ["Retificação incorreta do CAR"],
            "lacunas": ["Falta certidão atualizada"],
            "checklist_documental": ["Matrícula atualizada"],
            "afirmacoes": [
                {"texto": "CAR pendente", "categoria": "passivo",
                 "fontes": [{"tipo": "documento", "ref": "356", "descricao": "Recibo CAR"}]}
            ],
            "sources": [{"type": "document", "ref": "356"}],
            "confidence": 0.7,
        }
        content = build_content_from_job_result(result, ai_job_id=993)

        validate_diagnostic_content(content)  # gate real — levanta se inválido
        assert content["content"].startswith("Imóvel com CAR")
        assert content["hipoteses"] == ["Retificação incorreta do CAR"]
        assert content["confidence"] == 0.7
        assert content["metadata"]["ai_job_id"] == 993

    def test_result_legado_dual_emit(self):
        """Job antigo só tem `situacao_geral`/`passivos_identificados`."""
        result = {
            "situacao_geral": "Situação regular com pendências cadastrais.",
            "passivos_identificados": ["CAR pendente", "Divergência de área"],
            "acoes_remediacao": ["Retificar o CAR"],
        }
        content = build_content_from_job_result(result, ai_job_id=1)

        validate_diagnostic_content(content)
        assert content["content"] == "Situação regular com pendências cadastrais."
        assert content["hipoteses"] == ["CAR pendente", "Divergência de área"]
        assert content["checklist_documental"] == ["Retificar o CAR"]

    def test_sem_sources_usa_o_proprio_job_como_fonte(self):
        """`sources` não pode ser vazio (StageOutputContent) — e não se inventa
        documento: a fonte honesta é a execução do agente."""
        content = build_content_from_job_result(
            {"situacao_geral": "Texto."}, ai_job_id=42
        )
        validate_diagnostic_content(content)
        assert content["sources"][0]["ref"] == "ai_job:42"

    def test_confidence_fora_de_faixa_e_descartada(self):
        content = build_content_from_job_result(
            {"content": "Texto.", "confidence": 7.5}, ai_job_id=1
        )
        assert "confidence" not in content
        validate_diagnostic_content(content)

    @pytest.mark.parametrize("result", [{}, None, {"hipoteses": ["x"]}, {"content": "   "}])
    def test_sem_texto_falha_com_causa_nomeada(self, result):
        """Erro com causa, não 422 genérico: a mensagem vai para a consultora."""
        with pytest.raises(DiagnosisMaterializationError) as exc:
            build_content_from_job_result(result, ai_job_id=1)
        assert "diagnóstico" in str(exc.value).lower()

    def test_campos_desconhecidos_do_agente_nao_vazam(self):
        """`DiagnosticoPreliminarContent` é `extra="forbid"`: copiar o result
        inteiro estouraria o gate. A allowlist é proposital."""
        result = {
            "content": "Texto.",
            "campo_novo_do_agente": {"qualquer": "coisa"},
            "requires_review": True,
        }
        content = build_content_from_job_result(result, ai_job_id=1)
        assert "campo_novo_do_agente" not in content
        assert "requires_review" not in content
        validate_diagnostic_content(content)
