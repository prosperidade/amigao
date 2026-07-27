"""Selo "sem casa" cobrindo o imóvel — o caminho por onde o caso 15 vazou.

Medido em prod (processo 15, 26/07): a consultora aceitou `total_area_ha` e
`modulos_fiscais`, clicou em Gravar na base, e nada pousou. A varredura de
`flag_sem_casa` só olhava `target_entity == 'matricula'`, então nenhuma das duas
linhas recebeu selo. A tela dizia "Aceito", em azul, e pronto.

Selo que não cobre o caminho por onde o dado se perde não é selo.
"""

from app.services.staging_consolidation import _destino_sem_casa


class TestDestinoSemCasaImovel:
    def test_total_area_ha_e_derivada_e_nunca_grava(self):
        """Área do imóvel = soma das matrículas. O motivo explica ONDE aceitar."""
        motivo = _destino_sem_casa("imovel", "total_area_ha")
        assert motivo is not None
        assert "soma das matrículas" in motivo
        assert "em cada matrícula" in motivo

    def test_campo_sem_coluna_na_base(self):
        """`modulos_fiscais` não existe em `properties` — aceito em 14:32:54, sumiu."""
        motivo = _destino_sem_casa("imovel", "modulos_fiscais")
        assert motivo is not None
        assert "modulos_fiscais" in motivo
        assert "não tem campo na ficha do imóvel" in motivo

    def test_pendencias_do_rat_viram_alerta_nao_campo(self):
        motivo = _destino_sem_casa("imovel", "regulatory_issues")
        assert motivo is not None
        assert "alertas" in motivo

    def test_campo_com_casa_nao_recebe_selo(self):
        """Controle negativo: o que grava normalmente não pode ser marcado."""
        for campo in ("car_code", "car_status", "municipality", "state", "app_area_ha"):
            assert _destino_sem_casa("imovel", campo) is None, campo

    def test_aceito_sem_destino(self):
        motivo = _destino_sem_casa("imovel", None)
        assert motivo is not None and "sem campo de destino" in motivo


class TestDestinoSemCasaCliente:
    def test_campo_inexistente_no_cliente(self):
        motivo = _destino_sem_casa("cliente", "profissao")
        assert motivo is not None
        assert "cadastro do cliente" in motivo

    def test_campo_valido_do_cliente_passa(self):
        assert _destino_sem_casa("cliente", "full_name") is None
        assert _destino_sem_casa("cliente", "cpf_cnpj") is None


class TestMotivoEmLinguagemDeConsultora:
    """O motivo aparece NA TELA (item 9/14). Não pode falar como engenheiro."""

    PROIBIDOS = ("allowlist", "target_field", "staging", "None", "null", "column")

    def test_motivos_nao_usam_jargao(self):
        motivos = [
            _destino_sem_casa("imovel", "total_area_ha"),
            _destino_sem_casa("imovel", "modulos_fiscais"),
            _destino_sem_casa("imovel", "regulatory_issues"),
            _destino_sem_casa("cliente", "profissao"),
        ]
        for motivo in motivos:
            assert motivo
            for termo in self.PROIBIDOS:
                assert termo not in motivo, f"jargão '{termo}' em: {motivo}"
