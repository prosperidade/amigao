"""
Relatório de clientes duplicados por CPF/CNPJ normalizado (ENT-002).

SÓ LÊ. Não altera nada — a spec veta fusão automática de registros históricos
("Não executar fusão automática dos registros históricos sem plano de migração e
auditoria", ENT-002). Este script existe para responder, ANTES de aplicar a
migration ADR-063, duas perguntas: existe duplicado neste banco? e quais são?

Uso:
    python scripts/relatorio_duplicados_documento.py            # banco do .env
    python scripts/relatorio_duplicados_documento.py --json     # saída JSON

Saída vazia = a migration aplica a constraint sem obstáculo.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Bootstrap sys.path pra importar app.* rodando como `python scripts/...`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402

# Mesma expressão do índice único: identidade é o conjunto de DÍGITOS.
SQL = """
SELECT c.tenant_id,
       t.name                                            AS tenant,
       regexp_replace(c.cpf_cnpj, '[^0-9]', '', 'g')     AS documento,
       count(*)                                          AS quantos,
       array_agg(c.id ORDER BY c.id)                     AS ids,
       array_agg(c.full_name ORDER BY c.id)              AS nomes,
       array_agg(coalesce(c.cpf_cnpj, '') ORDER BY c.id) AS como_digitado
  FROM clients c
  LEFT JOIN tenants t ON t.id = c.tenant_id
 WHERE c.cpf_cnpj IS NOT NULL
   AND c.deleted_at IS NULL
   AND regexp_replace(c.cpf_cnpj, '[^0-9]', '', 'g') <> ''
 GROUP BY c.tenant_id, t.name, regexp_replace(c.cpf_cnpj, '[^0-9]', '', 'g')
HAVING count(*) > 1
 ORDER BY c.tenant_id, documento
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    args = ap.parse_args()

    url = str(settings.SQLALCHEMY_DATABASE_URI)
    engine = create_engine(url)

    # Imprime o alvo ANTES de consultar — a regra do projeto para qualquer
    # operação de banco é conferir host/porta/banco efetivos.
    with engine.connect() as conn:
        alvo = conn.execute(text(
            "SELECT current_database(), current_user, "
            "inet_server_addr()::text, inet_server_port()"
        )).first()
        if not args.json:
            print(f"Banco: {alvo[0]} · usuário: {alvo[1]} · "
                  f"servidor: {alvo[2] or 'local'}:{alvo[3]}\n")
        linhas = list(conn.execute(text(SQL)))

    if args.json:
        print(json.dumps([{
            "tenant_id": r.tenant_id, "tenant": r.tenant, "documento": r.documento,
            "quantos": r.quantos, "ids": list(r.ids), "nomes": list(r.nomes),
            "como_digitado": list(r.como_digitado),
        } for r in linhas], ensure_ascii=False, indent=2))
        return 1 if linhas else 0

    if not linhas:
        print("Nenhum duplicado por CPF/CNPJ normalizado. "
              "A migration ADR-063 pode ser aplicada.")
        return 0

    print(f"{len(linhas)} grupo(s) de duplicados — a migration ADR-063 vai PARAR "
          "até que sejam resolvidos:\n")
    for r in linhas:
        print(f"  tenant {r.tenant_id} ({r.tenant or '—'}) · documento {r.documento} "
              f"· {r.quantos} cadastros")
        for cid, nome, digitado in zip(r.ids, r.nomes, r.como_digitado, strict=False):
            print(f"      #{cid:<6} {nome or '—':<40} digitado como {digitado!r}")
        print()
    print("Resolver à mão: escolher o cadastro canônico, migrar os vínculos "
          "(processos, imóveis, contratos) e apagar logicamente os demais. "
          "A fusão automática é vetada pela spec (ENT-002).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
