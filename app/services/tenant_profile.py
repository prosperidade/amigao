"""Perfil emissor do tenant — dados que assinam a proposta/contrato (S5-B).

O ``Tenant`` do sistema é mínimo (id/nome/orçamento de IA). A proposta e o
contrato nos moldes Mirante exigem os dados institucionais de QUEM EMITE a peça:
razão social, CNPJ, endereço, responsável técnico (nome/título/CREA), dados
bancários e as condições comerciais padrão (foro, prazos, multa).

Esses dados vivem em ``tenant.settings["issuer"]`` (JSON aditivo — migration
``f1a7c2d9e4b6``). Quando um campo OBRIGATÓRIO falta, a geração do documento é
BLOQUEADA com mensagem honesta nomeando o que falta — coerente com "placeholder
não resolvido = geração bloqueada" (ADR-029) e com "IA propõe, humano decide"
(o consultor completa o perfil antes de a peça sair).

As CONDIÇÕES comerciais têm defaults sensatos (não bloqueiam); a identidade e os
dados bancários NÃO têm default (bloqueiam se ausentes) — nunca inventamos CNPJ
ou conta, como o gerador legado fazia (``"00.000.000/0001-00"``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Defaults das condições comerciais (não bloqueiam a geração — o consultor ajusta).
DEFAULT_VALIDADE_PROPOSTA_DIAS = 30
DEFAULT_MULTA_PERCENTUAL = "10%"
DEFAULT_RESCISAO_NOTIFICACAO_DIAS = 30
DEFAULT_BONUS_MALUS_PERCENTUAL = 20  # ±20% (OPCIONAL, desligado por default)


@dataclass
class BonusMalus:
    """Cláusula de desempenho ±% (OPCIONAL — desligada por padrão)."""

    ativo: bool = False
    percentual: int = DEFAULT_BONUS_MALUS_PERCENTUAL


@dataclass
class IssuerProfile:
    """Perfil institucional do tenant que assina a peça (proposta/contrato)."""

    # Identidade (obrigatórios)
    razao_social: str = ""
    cnpj: str = ""
    endereco: str = ""
    # Responsável técnico (obrigatórios — assinam a proposta)
    rt_nome: str = ""
    rt_titulo: str = ""
    rt_crea: str = ""
    # Dados bancários do tenant (obrigatórios no contrato)
    banco_nome: str = ""
    banco_agencia: str = ""
    banco_conta: str = ""
    banco_titular: str = ""
    banco_pix: Optional[str] = None  # opcional
    # Condições comerciais (com defaults — não bloqueiam)
    foro: str = ""  # obrigatório
    prazo_execucao: Optional[str] = None  # opcional (cai no prazo estimado da rota)
    validade_proposta_dias: int = DEFAULT_VALIDADE_PROPOSTA_DIAS
    multa_percentual: str = DEFAULT_MULTA_PERCENTUAL
    rescisao_notificacao_dias: int = DEFAULT_RESCISAO_NOTIFICACAO_DIAS
    bonus_malus: BonusMalus = field(default_factory=BonusMalus)


# Campos obrigatórios: (atributo, rótulo humano) — nomeados na mensagem de bloqueio.
_REQUIRED: list[tuple[str, str]] = [
    ("razao_social", "Razão social do tenant"),
    ("cnpj", "CNPJ do tenant"),
    ("endereco", "Endereço do tenant"),
    ("rt_nome", "Nome do responsável técnico"),
    ("rt_titulo", "Título do responsável técnico"),
    ("rt_crea", "CREA do responsável técnico"),
    ("banco_nome", "Banco (dados bancários do tenant)"),
    ("banco_agencia", "Agência (dados bancários do tenant)"),
    ("banco_conta", "Conta (dados bancários do tenant)"),
    ("banco_titular", "Titular da conta (dados bancários do tenant)"),
    ("foro", "Foro (comarca) das condições comerciais"),
]


def load_issuer_profile(tenant: Any) -> IssuerProfile:
    """Constrói o ``IssuerProfile`` a partir de ``tenant.settings["issuer"]``.

    Tolerante a settings ausente/parcial (mocks, tenants antigos): campos que
    faltam ficam vazios e serão apontados por :func:`missing_issuer_fields`.
    """
    settings = getattr(tenant, "settings", None) or {}
    issuer = settings.get("issuer", {}) if isinstance(settings, dict) else {}
    rt = issuer.get("responsavel_tecnico", {}) or {}
    banco = issuer.get("banco", {}) or {}
    cond = issuer.get("condicoes", {}) or {}
    bm_raw = cond.get("bonus_malus", {}) or {}

    return IssuerProfile(
        razao_social=(issuer.get("razao_social") or "").strip(),
        cnpj=(issuer.get("cnpj") or "").strip(),
        endereco=(issuer.get("endereco") or "").strip(),
        rt_nome=(rt.get("nome") or "").strip(),
        rt_titulo=(rt.get("titulo") or "").strip(),
        rt_crea=(rt.get("crea") or "").strip(),
        banco_nome=(banco.get("nome") or "").strip(),
        banco_agencia=(banco.get("agencia") or "").strip(),
        banco_conta=(banco.get("conta") or "").strip(),
        banco_titular=(banco.get("titular") or "").strip(),
        banco_pix=(banco.get("pix") or None),
        foro=(cond.get("foro") or "").strip(),
        prazo_execucao=(cond.get("prazo_execucao") or None),
        validade_proposta_dias=int(
            cond.get("validade_proposta_dias", DEFAULT_VALIDADE_PROPOSTA_DIAS)
        ),
        multa_percentual=(cond.get("multa_percentual") or DEFAULT_MULTA_PERCENTUAL),
        rescisao_notificacao_dias=int(
            cond.get("rescisao_notificacao_dias", DEFAULT_RESCISAO_NOTIFICACAO_DIAS)
        ),
        bonus_malus=BonusMalus(
            ativo=bool(bm_raw.get("ativo", False)),
            percentual=int(bm_raw.get("percentual", DEFAULT_BONUS_MALUS_PERCENTUAL)),
        ),
    )


def missing_issuer_fields(profile: IssuerProfile) -> list[str]:
    """Rótulos humanos dos campos obrigatórios ausentes (vazio = perfil completo)."""
    return [label for attr, label in _REQUIRED if not getattr(profile, attr, "")]
