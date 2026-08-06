"""Selo "sem casa" cobrindo o imóvel — o caminho por onde o caso 15 vazou.

Medido em prod (processo 15, 26/07): a consultora aceitou `total_area_ha` e
`modulos_fiscais`, clicou em Gravar na base, e nada pousou. A varredura de
`flag_sem_casa` só olhava `target_entity == 'matricula'`, então nenhuma das duas
linhas recebeu selo. A tela dizia "Aceito", em azul, e pronto.

Selo que não cobre o caminho por onde o dado se perde não é selo.

**Atualizado em 03/08 (dívida #200).** `modulos_fiscais` saiu daqui porque
**deixou de não ter casa**: ele ganhou coluna em `properties`, entrada na
allowlist e campo no Hub — é atributo do imóvel (área ÷ módulo fiscal), decide
porte e portanto exceção do Código Florestal. Este arquivo guardava o SINTOMA
("o campo some sem selo"); a causa foi curada na origem, então o guard mudou de
lado: agora exige que ele **não** seja selado, porque selar um campo que pousa
diria à consultora que o dado se perdeu quando ele foi gravado.

`total_area_ha` continua aqui — aquele é derivado de verdade e nunca vai pousar.
"""

from app.models.property import Property
from app.services.staging_consolidation import _destino_sem_casa


class TestDestinoSemCasaImovel:
    def test_total_area_ha_e_derivada_e_nunca_grava(self):
        """Área do imóvel = soma das matrículas. O motivo explica ONDE aceitar."""
        motivo = _destino_sem_casa("imovel", "total_area_ha")
        assert motivo is not None
        assert "soma das matrículas" in motivo
        assert "em cada matrícula" in motivo

    def test_campo_sem_coluna_na_base(self):
        """Campo que a extração produz e a base não guarda (aqui, `vtn`).

        Era `modulos_fiscais` — aceito às 14:32:54 no caso 15 e sumido. Ele saiu
        deste teste porque **ganhou coluna** (#200); o cenário continua real com
        outro campo, e é ele que este guard protege.
        """
        motivo = _destino_sem_casa("imovel", "vtn")
        assert motivo is not None
        assert "vtn" in motivo
        assert "ainda não tem campo" in motivo
        assert "ficha do imóvel" in motivo
        # Diz o que fazer, não só o que faltou.
        assert "é campo a pedir" in motivo

    def test_modulos_fiscais_pousa_e_por_isso_nao_e_selado(self):
        """O sintoma do caso 15 curado na origem (#200).

        Selar um campo que POUSA é tão errado quanto não selar o que se perde:
        diria à consultora que o dado sumiu quando ele foi gravado. Este teste
        existe para quebrar se alguém tirar a coluna ou a entrada na allowlist.
        """
        assert "modulos_fiscais" in Property.__table__.columns
        assert _destino_sem_casa("imovel", "modulos_fiscais") is None

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
            _destino_sem_casa("imovel", "vtn"),
            _destino_sem_casa("imovel", "regulatory_issues"),
            _destino_sem_casa("imovel", "rat_protocolo"),
            _destino_sem_casa("cliente", "profissao"),
            _destino_sem_casa("matricula", "campo_que_nao_existe"),
        ]
        for motivo in motivos:
            assert motivo
            for termo in self.PROIBIDOS:
                assert termo not in motivo, f"jargão '{termo}' em: {motivo}"

    def test_motivos_tem_concordancia_correta(self):
        """"na cadastro do cliente" chegou a existir nesta rodada.

        O gênero muda com a entidade ("ficha" é feminino, "cadastro" é
        masculino), e a preposição estava fixa no template. Texto que a
        consultora lê não pode sair torto.
        """
        assert "no cadastro do cliente" in _destino_sem_casa("cliente", "profissao")
        assert "na ficha do imóvel" in _destino_sem_casa("imovel", "vtn")
        assert "na ficha da matrícula" in _destino_sem_casa("matricula", "inexistente")
        for entidade, campo in [("cliente", "profissao"), ("imovel", "vtn"),
                                ("matricula", "inexistente")]:
            assert "na cadastro" not in _destino_sem_casa(entidade, campo)
