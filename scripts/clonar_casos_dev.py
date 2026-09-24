"""Clona casos de um tenant de DEV para um tenant novo e limpo (dívida #281).

Para comparar modelos lado a lado, cada modelo precisa gravar sua leitura num
tenant próprio: pessoa, participação e espólio de uma leitura não podem se
misturar com os de outra. Copia cliente, imóvel, processo e documentos — o
texto extraído, o tipo e o hash —, nada de observação: o tenant nasce sem leitura.

Só em DEV (o alvo é conferido). Uso:
    python scripts/clonar_casos_dev.py --origem 34 --processos 67,68 --nome "Medição #281 gpt-6-luna"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ALVO_DEV = ("127.0.0.1", 15432, "amigao_db")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", type=int, required=True)
    ap.add_argument("--processos", required=True)
    ap.add_argument("--nome", required=True)
    args = ap.parse_args()

    from sqlalchemy.engine import make_url

    from app.core.config import settings
    from app.core.security import get_password_hash
    from app.db.session import SessionLocal
    from app.models.client import Client
    from app.models.document import Document
    from app.models.process import Process
    from app.models.property import Property
    from app.models.tenant import Tenant
    from app.models.user import User

    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if (url.host, url.port, url.database) != ALVO_DEV:
        raise SystemExit(f"ABORTADO: alvo {(url.host, url.port, url.database)} não é o dev {ALVO_DEV}")

    with SessionLocal() as db:
        tenant = Tenant(name=args.nome)
        db.add(tenant)
        db.flush()
        user = User(tenant_id=tenant.id, email=f"medicao-281-{uuid4().hex[:10]}@example.com",
                    hashed_password=get_password_hash(uuid4().hex), is_active=True)
        db.add(user)
        db.flush()
        mapa = {}
        for pid in [int(x) for x in args.processos.split(",")]:
            src = db.get(Process, pid)
            assert src is not None and src.tenant_id == args.origem, f"processo {pid} não é do tenant {args.origem}"
            sc, sp = db.get(Client, src.client_id), db.get(Property, src.property_id)
            client = Client(tenant_id=tenant.id, full_name=sc.full_name, cpf_cnpj=sc.cpf_cnpj,
                            client_type=sc.client_type, legal_name=sc.legal_name)
            db.add(client)
            db.flush()
            prop = Property(tenant_id=tenant.id, client_id=client.id, name=sp.name, state=sp.state,
                            municipality=sp.municipality)
            db.add(prop)
            db.flush()
            proc = Process(tenant_id=tenant.id, client_id=client.id, property_id=prop.id, title=src.title,
                           process_type=src.process_type, status=src.status, macroetapa=src.macroetapa)
            db.add(proc)
            db.flush()
            docs = db.query(Document).filter(Document.tenant_id == args.origem, Document.process_id == pid,
                                             Document.deleted_at.is_(None)).order_by(Document.id).all()
            ids = []
            for d in docs:
                novo = Document(tenant_id=tenant.id, process_id=proc.id, filename=d.filename,
                                original_file_name=d.original_file_name, content_type=d.content_type,
                                storage_key=f"{d.storage_key}#clone-{uuid4().hex[:8]}",
                                document_type=d.document_type, extracted_text=d.extracted_text,
                                checksum_sha256=d.checksum_sha256, ocr_status=d.ocr_status, source=d.source)
                db.add(novo)
                db.flush()
                ids.append((d.id, novo.id))
            mapa[pid] = {"processo": proc.id, "documentos": ids}
        db.commit()
        print(f"tenant={tenant.id} usuario={user.id}")
        for pid, m in mapa.items():
            print(f"  origem {pid} -> processo {m['processo']} | documentos {m['documentos']}")


if __name__ == "__main__":
    main()
