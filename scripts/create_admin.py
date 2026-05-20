"""
Cria um superusuário inicial em produção.

Uso (Render Shell):
    python scripts/create_admin.py

O script pede email, nome e senha interativamente (senha mascarada via getpass).
Pode também receber valores via flags ou env vars — útil pra scripted setup.

Defaults:
    EMAIL       admin@regenteambiental.com.br
    FULL_NAME   Administrador
    TENANT_NAME Regente Ambiental

Idempotência:
    - Tenant: cria se não existe; reusa se já tem com mesmo nome.
    - User: ABORTA se já existe um user com o email (não sobrescreve).

Sem dados demo. Diferente de seed.py (que cria 4 usuários + clientes + processos).
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User

DEFAULT_EMAIL = "admin@regenteambiental.com.br"
DEFAULT_FULL_NAME = "Administrador"
DEFAULT_TENANT_NAME = "Regente Ambiental"


def _read_password() -> str:
    """Lê senha do env ADMIN_PASSWORD, ou interativamente com confirmação."""
    env = os.environ.get("ADMIN_PASSWORD", "").strip()
    if env:
        if len(env) < 8:
            sys.exit("ERRO: ADMIN_PASSWORD do env tem menos de 8 chars. Aborta.")
        return env

    while True:
        p1 = getpass.getpass("Senha do admin (min 8 chars, mascarada): ")
        if len(p1) < 8:
            print("Muito curta. Pelo menos 8 chars.")
            continue
        p2 = getpass.getpass("Confirma a senha: ")
        if p1 != p2:
            print("Senhas nao batem. Tenta de novo.")
            continue
        return p1


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria superusuario inicial.")
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", DEFAULT_EMAIL))
    parser.add_argument("--full-name", default=os.environ.get("ADMIN_FULL_NAME", DEFAULT_FULL_NAME))
    parser.add_argument("--tenant", default=os.environ.get("ADMIN_TENANT_NAME", DEFAULT_TENANT_NAME))
    args = parser.parse_args()

    email = args.email.strip().lower()
    full_name = args.full_name.strip()
    tenant_name = args.tenant.strip()

    print(f"Email      : {email}")
    print(f"Full name  : {full_name}")
    print(f"Tenant     : {tenant_name}")

    password = _read_password()

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if not tenant:
            tenant = Tenant(name=tenant_name)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"Tenant criado: id={tenant.id} name={tenant.name!r}")
        else:
            print(f"Tenant ja existe: id={tenant.id} name={tenant.name!r}")

        user = db.query(User).filter(User.email == email).first()
        if user:
            sys.exit(
                f"ABORTADO: user {email!r} ja existe (id={user.id}). "
                "Nada foi alterado. Use o painel de admin pra resetar a senha "
                "ou rode com outro --email."
            )

        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            tenant_id=tenant.id,
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(
            f"Admin criado: id={user.id} email={user.email!r} "
            f"tenant_id={user.tenant_id} superuser={user.is_superuser}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
