import asyncio
from app.db.session import SessionLocal
from app.models.user import User
from app.models.tenant import Tenant
from app.core.security import get_password_hash

def seed():
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == "Amigão Headquarters").first()
        if not tenant:
            tenant = Tenant(name="Amigão Headquarters")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        user = db.query(User).filter(User.email == "admin@amigao.com").first()
        if not user:
            user = User(
                email="admin@amigao.com",
                full_name="Administrador Global",
                hashed_password=get_password_hash("admin123"),
                tenant_id=tenant.id,
                is_active=True,
                is_superuser=True
            )
            db.add(user)
            db.commit()
            print("User admin@amigao.com created!")
        else:
            print("User already exists.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
