from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.models.user import User


def _ensure_user(
    db,
    *,
    tenant_id: int,
    email: str,
    full_name: str,
    password: str,
    is_superuser: bool = False,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            tenant_id=tenant_id,
            is_active=True,
            is_superuser=is_superuser,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    user.full_name = full_name
    user.hashed_password = get_password_hash(password)
    user.tenant_id = tenant_id
    user.is_active = True
    user.is_superuser = is_superuser
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _ensure_client(
    db,
    *,
    tenant_id: int,
    full_name: str,
    email: str,
    phone: str,
    cpf_cnpj: str,
    notes: str,
) -> Client:
    client = db.query(Client).filter(Client.tenant_id == tenant_id, Client.email == email).first()
    if client is None:
        client = Client(
            tenant_id=tenant_id,
            full_name=full_name,
            email=email,
            phone=phone,
            cpf_cnpj=cpf_cnpj,
            client_type=ClientType.pf,
            status=ClientStatus.active,
            source_channel="portal",
            notes=notes,
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        return client

    client.full_name = full_name
    client.phone = phone
    client.cpf_cnpj = cpf_cnpj
    client.client_type = ClientType.pf
    client.status = ClientStatus.active
    client.source_channel = "portal"
    client.notes = notes
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def _ensure_process(
    db,
    *,
    tenant_id: int,
    client_id: int,
    responsible_user_id: int,
    title: str,
    description: str,
    process_type: str,
) -> Process:
    process = (
        db.query(Process)
        .filter(Process.tenant_id == tenant_id, Process.client_id == client_id, Process.title == title)
        .first()
    )
    if process is None:
        process = Process(
            tenant_id=tenant_id,
            client_id=client_id,
            title=title,
            description=description,
            process_type=process_type,
            status=ProcessStatus.triagem,
            responsible_user_id=responsible_user_id,
            urgency="normal",
        )
        db.add(process)
        db.commit()
        db.refresh(process)
        return process

    process.description = description
    process.process_type = process_type
    process.status = ProcessStatus.triagem
    process.responsible_user_id = responsible_user_id
    process.urgency = "normal"
    db.add(process)
    db.commit()
    db.refresh(process)
    return process


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provisiona um tenant controlado para homologacao de fluxos reais com portal e notificacoes."
    )
    parser.add_argument("--tenant-name", default="Homologacao Documentos SMTP")
    parser.add_argument("--internal-email", required=True)
    parser.add_argument("--portal-email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--client-name", default="Portal Homologacao SMTP")
    parser.add_argument("--phone", default="62999990000")
    parser.add_argument("--cpf-cnpj", default="HOMOLOGDOCSMTP001")
    parser.add_argument("--process-title", default="Homologacao Upload Documento SMTP")
    parser.add_argument(
        "--process-description",
        default="Processo controlado para homologacao do fluxo upload-url/confirm-upload/notificacao_documento.",
    )
    parser.add_argument("--process-type", default="licenciamento")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == args.tenant_name).first()
        if tenant is None:
            tenant = Tenant(name=args.tenant_name)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        internal_user = _ensure_user(
            db,
            tenant_id=tenant.id,
            email=args.internal_email,
            full_name="Interno Homologacao SMTP",
            password=args.password,
        )
        portal_user = _ensure_user(
            db,
            tenant_id=tenant.id,
            email=args.portal_email,
            full_name=args.client_name,
            password=args.password,
        )
        client = _ensure_client(
            db,
            tenant_id=tenant.id,
            full_name=args.client_name,
            email=args.portal_email,
            phone=args.phone,
            cpf_cnpj=args.cpf_cnpj,
            notes="Cliente controlado para homologacao do fluxo de documentos com SMTP real.",
        )
        process = _ensure_process(
            db,
            tenant_id=tenant.id,
            client_id=client.id,
            responsible_user_id=internal_user.id,
            title=args.process_title,
            description=args.process_description,
            process_type=args.process_type,
        )

        print(
            json.dumps(
                {
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "internal_email": internal_user.email,
                    "portal_email": portal_user.email,
                    "password": args.password,
                    "client_id": client.id,
                    "process_id": process.id,
                    "process_title": process.title,
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
