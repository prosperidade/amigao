"""Fundamento da regra resolvido por IDENTIDADE no catálogo normativo (ADR-073 §6).

A regra declara ``{"fonte": "tipo|ente|orgao|numero|ano", "artigo": "29", "paragrafo": None}``.
Aqui isso vira ``(fonte_versao_id, dispositivo_id, caminho)`` — ou uma razão de não ter
virado, sem nunca procurar substituta por semelhança:

- ``fonte_ausente`` — a identidade não está no catálogo (ou não tem identidade determinada);
- ``versao_nao_elegivel`` — a versão corrente não serve à política ``interno`` do ADR-075
  (``bruto``, bloqueada, ou fora da vigência na data de referência);
- ``dispositivo_ausente`` — o artigo/parágrafo não existe NAQUELA versão.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.zona_normativa.recuperacao import POLITICAS

POLITICA = "interno"
RAZOES = ("fonte_ausente", "versao_nao_elegivel", "dispositivo_ausente", "sem_fundamento_declarado")


@dataclass(frozen=True)
class Resolucao:
    fonte_versao_id: int | None = None
    dispositivo_id: int | None = None
    caminho: str | None = None
    rotulo: str | None = None
    status_validacao: str | None = None
    razao: str | None = None
    detalhe: str | None = None

    @property
    def resolvido(self) -> bool:
        return self.razao is None

    def dispositivo_citavel(self, fundamento: dict) -> str:
        """Forma que `citacao.verificar` entende: "art. 29" / "art. 29, § 1º"."""
        par = fundamento.get("paragrafo")
        base = f"art. {fundamento['artigo']}"
        if par == "unico":
            return f"{base}, parágrafo único"
        return f"{base}, § {par}º" if par else base


def _versao_corrente(session: Session, fonte_id: int):
    """A versão que nenhuma outra substitui.

    Pode haver mais de uma: a mesma fonte com duas proveniências (avulso e coletânea)
    tem duas versões sem relação de substituição — 69 fontes no catálogo de dev. O
    desempate é determinístico: a mais curada (validado > proposto > bruto), depois a
    mais nova. Assim a versão que a curadoria propôs é a que fundamenta.
    """
    return session.execute(text(
        """
        SELECT v.id, v.status_validacao, v.vigencia_estado, v.vigencia_inicio, v.vigencia_fim,
               v.bloqueio_citacao
          FROM fonte_normativa_versao v
         WHERE v.fonte_id = :f
           AND NOT EXISTS (SELECT 1 FROM fonte_normativa_versao s WHERE s.substitui_versao_id = v.id)
         ORDER BY CASE v.status_validacao WHEN 'validado' THEN 0 WHEN 'proposto' THEN 1 ELSE 2 END,
                  v.id DESC
         LIMIT 1
        """
    ), {"f": fonte_id}).first()


def resolver(
    session: Session, fundamento: dict | None, *, tenant_id: int, data_referencia: date
) -> Resolucao:
    if not fundamento or not fundamento.get("fonte") or not fundamento.get("artigo"):
        return Resolucao(razao="sem_fundamento_declarado", detalhe="regra sem fonte e artigo declarados")

    fonte = session.execute(text(
        "SELECT id, rotulo, identidade_determinada FROM fonte_normativa "
        "WHERE identidade = :i AND (tenant_id IS NULL OR tenant_id = :t)"
    ), {"i": fundamento["fonte"], "t": tenant_id}).first()
    if fonte is None or not fonte.identidade_determinada:
        # Q-ISIS-19: ato em segmento `nao_determinado` de coletânea não serve de
        # fundamento até a revisão — não se procura por semelhança.
        return Resolucao(razao="fonte_ausente", detalhe=f"{fundamento['fonte']} não está no catálogo")

    v = _versao_corrente(session, fonte.id)
    pol = POLITICAS[POLITICA]
    if v is None:
        return Resolucao(rotulo=fonte.rotulo, razao="versao_nao_elegivel", detalhe="fonte sem versão")
    motivo = None
    if v.status_validacao not in pol.status:
        motivo = f"versão {v.id} está {v.status_validacao}; {POLITICA} aceita {list(pol.status)}"
    elif v.bloqueio_citacao and not pol.aceita_bloqueada:
        motivo = f"versão {v.id} bloqueada: {v.bloqueio_citacao}"
    elif v.vigencia_estado == "nao_determinada" and not pol.aceita_vigencia_nao_determinada:
        motivo = f"versão {v.id} com vigência não determinada"
    elif (v.vigencia_inicio and v.vigencia_inicio > data_referencia) or (
        v.vigencia_fim and v.vigencia_fim < data_referencia
    ):
        motivo = f"versão {v.id} fora da vigência em {data_referencia}"
    if motivo:
        return Resolucao(rotulo=fonte.rotulo, status_validacao=v.status_validacao,
                         razao="versao_nao_elegivel", detalhe=motivo)

    params = {"v": v.id, "a": str(fundamento["artigo"]).upper()}
    sql = "SELECT id, caminho FROM dispositivo WHERE fonte_versao_id = :v AND artigo = :a"
    if fundamento.get("paragrafo"):
        sql += " AND paragrafo = :p"
        params["p"] = str(fundamento["paragrafo"])
    else:
        sql += " AND tipo = 'artigo'"
    d = session.execute(text(sql + " ORDER BY ordem LIMIT 1"), params).first()
    if d is None:
        return Resolucao(fonte_versao_id=None, rotulo=fonte.rotulo, status_validacao=v.status_validacao,
                         razao="dispositivo_ausente",
                         detalhe=f"art. {params['a']}{' § ' + params['p'] if 'p' in params else ''} "
                                 f"não existe na versão {v.id}")
    return Resolucao(fonte_versao_id=v.id, dispositivo_id=d.id, caminho=d.caminho, rotulo=fonte.rotulo,
                     status_validacao=v.status_validacao)


def verificar_passo(session: Session, passo, *, data_referencia: date) -> list[str]:
    """Reverifica o fundamento de um passo do motor NO MOMENTO da validação (ADR-073 §7).

    A fonte pode ter mudado de estado entre a geração e a validação (devolvida a
    ``bruto``, bloqueada, fora de vigência). Usa o mesmo verificador da citação por ID
    (`citacao.verificar`, destino ``interno``) — pertencimento a conjunto, não semelhança —
    e também procura menção a norma na descrição sem o ID correspondente.
    """
    from app.services.zona_normativa.citacao import Afirmacao, Citacao, carregar_envelope, verificar  # noqa: PLC0415

    if passo.fundamento_fonte_versao_id is None or passo.fundamento_dispositivo_id is None:
        return ["passo do motor sem fundamento resolvido por ID: traga a fonte pela curadoria "
                "e gere de novo, ou remova o passo com motivo"]
    d = session.execute(text(
        "SELECT artigo, paragrafo FROM dispositivo WHERE id = :d AND fonte_versao_id = :v"
    ), {"d": passo.fundamento_dispositivo_id, "v": passo.fundamento_fonte_versao_id}).first()
    if d is None or not d.artigo:
        return ["o dispositivo do fundamento não pertence à versão citada"]
    citavel = Resolucao().dispositivo_citavel({"artigo": d.artigo, "paragrafo": d.paragrafo})
    envelope = carregar_envelope(session, {passo.fundamento_fonte_versao_id})
    veredito = verificar(
        session,
        [Afirmacao(texto=passo.descricao or passo.titulo,
                   citacoes=[Citacao(fonte_versao_id=passo.fundamento_fonte_versao_id, dispositivo=citavel)])],
        envelope, destino=POLITICA, data_referencia=data_referencia,
    )
    return [f"{f.tipo}: {f.detalhe}" for f in veredito.falhas]
