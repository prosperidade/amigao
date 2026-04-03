"""
Script para criar o banco de dados e aplicar migrations oficiais.
Execute com: python -m app.db.init_db
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy_utils import create_database, database_exists

from app.db.session import engine


def _build_alembic_config() -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    versions_dir = repo_root / "alembic" / "versions"
    if not versions_dir.exists() or not any(versions_dir.glob("*.py")):
        raise RuntimeError("Nenhuma migration Alembic encontrada em alembic/versions.")

    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root / "alembic"))
    config.set_main_option("sqlalchemy.url", str(engine.url))
    return config


def init_db() -> None:
    if not database_exists(engine.url):
        create_database(engine.url)
        print(f"✅ Banco de dados criado: {engine.url}")
    else:
        print(f"ℹ️  Banco de dados já existe: {engine.url}")

    command.upgrade(_build_alembic_config(), "head")
    print("✅ Schema atualizado com Alembic até head.")


if __name__ == "__main__":
    init_db()
