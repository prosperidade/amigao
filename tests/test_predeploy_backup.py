"""Backup de pré-deploy — retenção, nome do objeto e bloqueio da migration.

A retenção é a parte que apaga coisas: estes testes travam que ela nunca desce
abaixo do mínimo, nunca apaga o que é recente e nunca sai do prefixo.
"""

from datetime import UTC, datetime, timedelta

import pytest
from scripts import predeploy_backup as pb
from scripts.predeploy_backup import (
    PREFIXO,
    ObjetoBackup,
    nome_do_objeto,
    selecionar_para_apagar,
    url_libpq,
)

AGORA = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def _objs(idades_em_dias: list[int], prefixo: str = PREFIXO) -> list[ObjetoBackup]:
    return [ObjetoBackup(f"{prefixo}d{i:03d}.dump", AGORA - timedelta(days=d)) for i, d in enumerate(idades_em_dias)]


def test_mantem_o_que_e_recente_mesmo_acima_do_minimo():
    objs = _objs(list(range(25)))  # 25 dumps, um por dia, todos < 30 dias
    assert selecionar_para_apagar(objs, AGORA, dias=30, minimo=10) == []


def test_apaga_antigos_alem_do_minimo():
    objs = _objs([1, 2, 40, 50, 60])
    assert sorted(selecionar_para_apagar(objs, AGORA, dias=30, minimo=2)) == sorted(
        [objs[2].chave, objs[3].chave, objs[4].chave]
    )


def test_minimo_protege_antigos_quando_nao_ha_recentes():
    # Meses sem deploy: todos velhos, mas os 10 mais novos ficam.
    objs = _objs([100 + i for i in range(12)])
    apagar = selecionar_para_apagar(objs, AGORA, dias=30, minimo=10)
    assert sorted(apagar) == sorted([objs[10].chave, objs[11].chave])


def test_nunca_apaga_fora_do_prefixo():
    objs = _objs([90, 91, 92], prefixo="manual/")
    assert selecionar_para_apagar(objs, AGORA, dias=30, minimo=1) == []


@pytest.mark.parametrize("dias,minimo", [(0, 10), (30, 0)])
def test_parametro_de_retencao_invalido_recusa(dias, minimo):
    with pytest.raises(ValueError):
        selecionar_para_apagar(_objs([1]), AGORA, dias=dias, minimo=minimo)


def test_nome_do_objeto_carrega_momento_commit_e_revisao():
    chave = nome_do_objeto(AGORA, "3c0e3697abcdef0123", "072ge001")
    assert chave == "predeploy/20260922T120000Z_3c0e3697abcd_072ge001.dump"
    assert nome_do_objeto(AGORA, None, None).endswith("_semcommit_semalembic.dump")


@pytest.mark.parametrize(
    "entrada",
    [
        "postgresql+psycopg2://u:p@h:5432/db",
        "postgresql://u:p@h:5432/db",
        "postgres://u:p@h:5432/db",
    ],
)
def test_url_libpq_remove_driver_sqlalchemy(entrada):
    assert url_libpq(entrada) == "postgresql://u:p@h:5432/db"


def test_falha_no_dump_sai_1_e_nao_segue(monkeypatch, capsys):
    """exit 1 é o que faz o `&&` do preDeploy não rodar o alembic."""
    monkeypatch.setattr(pb, "revisao_alembic", lambda url: "072ge001")

    def dump_quebrado(url, destino):
        raise pb.BackupFalhou("pg_dump saiu com 1: server version mismatch")

    enviado = []
    monkeypatch.setattr(pb, "gerar_dump", dump_quebrado)
    monkeypatch.setattr(pb, "enviar", lambda *a, **k: enviado.append(a))
    assert pb.main(["--no-retention"]) == 1
    assert enviado == []
    saida = capsys.readouterr().out
    assert "ERRO_backup_predeploy" in saida
    assert "p@h" not in saida  # senha da URL nunca vai para o log


def test_falha_na_retencao_nao_derruba_o_backup(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(pb, "revisao_alembic", lambda url: "072ge001")
    monkeypatch.setattr(pb, "gerar_dump", lambda url, destino: destino.write_bytes(b"PGDMP-fake"))
    monkeypatch.setattr(pb, "conferir_dump", lambda caminho: 42)
    monkeypatch.setattr(pb, "cliente_s3", lambda: object())
    monkeypatch.setattr(pb, "garantir_bucket", lambda s3, bucket: None)
    monkeypatch.setattr(pb, "enviar", lambda *a, **k: None)

    def retencao_quebrada(*a, **k):
        raise RuntimeError("R2 fora")

    monkeypatch.setattr(pb, "aplicar_retencao", retencao_quebrada)
    assert pb.main([]) == 0
    saida = capsys.readouterr().out
    assert "backup_ok" in saida and "ERRO_retencao" in saida
