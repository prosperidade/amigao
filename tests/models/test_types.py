"""
Testes do type decorator EncryptedString (ADR-014).

Usa um modelo de teste isolado sobre SQLite in-memory (EncryptedString.impl =
String, portável). Confirma que o ORM entrega plaintext mas o banco guarda
ciphertext, e que None faz round-trip.
"""

import pytest
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.encryption import get_fernet
from app.models.types import EncryptedString

Base = declarative_base()


class _SecretRow(Base):
    __tablename__ = "secret_row_under_test"

    id = Column(Integer, primary_key=True)
    label = Column(String(50), nullable=False)
    secret = Column(EncryptedString(256), nullable=True)


@pytest.fixture
def session():
    get_fernet.cache_clear()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    try:
        yield sess
    finally:
        sess.close()
        engine.dispose()
        get_fernet.cache_clear()


def test_orm_entrega_plaintext(session):
    session.add(_SecretRow(id=1, label="api-key", secret="sk-segredo-do-consultor"))
    session.commit()
    session.expire_all()  # força reload do banco

    row = session.get(_SecretRow, 1)
    assert row.secret == "sk-segredo-do-consultor"


def test_banco_guarda_ciphertext(session):
    plaintext = "sk-segredo-do-consultor"
    session.add(_SecretRow(id=1, label="api-key", secret=plaintext))
    session.commit()

    # Query SQL crua: o valor persistido NÃO pode ser o plaintext.
    raw = session.execute(
        text("SELECT secret FROM secret_row_under_test WHERE id = 1")
    ).scalar_one()
    assert raw != plaintext
    assert plaintext not in raw
    # E é decriptável de volta ao plaintext.
    from app.core.encryption import decrypt_str

    assert decrypt_str(raw) == plaintext


def test_none_round_trip(session):
    session.add(_SecretRow(id=1, label="sem-segredo", secret=None))
    session.commit()
    session.expire_all()

    row = session.get(_SecretRow, 1)
    assert row.secret is None

    raw = session.execute(
        text("SELECT secret FROM secret_row_under_test WHERE id = 1")
    ).scalar_one()
    assert raw is None
