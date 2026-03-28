"""
Script para criar o banco de dados e tabelas iniciais.
Execute com: python -m app.db.init_db
"""
from sqlalchemy_utils import database_exists, create_database
from app.db.session import engine
from app.models.base import Base
import app.models.tenant
import app.models.user
import app.models.client
import app.models.process


def init_db():
    if not database_exists(engine.url):
        create_database(engine.url)
        print(f"✅ Banco de dados criado: {engine.url}")
    else:
        print(f"ℹ️  Banco de dados já existe: {engine.url}")
    
    Base.metadata.create_all(bind=engine)
    print("✅ Tabelas criadas com sucesso!")


if __name__ == "__main__":
    init_db()
