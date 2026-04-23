"""Sprint -1 C — search_legislation: filtro de demand_type."""

from __future__ import annotations

from app.models.legislation import LegislationDocument
from app.services.legislation_service import search_legislation


def _seed_doc(
    db,
    *,
    title: str,
    identifier: str,
    scope: str = "federal",
    uf: str | None = None,
    demand_types: list[str] | None,
    full_text: str = "Texto fictício de prova.",
) -> LegislationDocument:
    doc = LegislationDocument(
        title=title,
        identifier=identifier,
        source_type="lei",
        scope=scope,
        uf=uf,
        full_text=full_text,
        token_count=len(full_text) // 4,
        status="indexed",
        demand_types=demand_types,
    )
    db.add(doc)
    db.flush()
    return doc


def test_demand_type_filter_returns_only_matching_docs(db_session):
    """Doc A tem 'car' no array, Doc B tem 'licenciamento', Doc C tem NULL.

    Query com demand_type='car' deve retornar só A.
    """
    doc_a = _seed_doc(db_session, title="Doc A CAR", identifier="A",
                      demand_types=["car", "retificacao_car"])
    _seed_doc(db_session, title="Doc B Licenciamento", identifier="B",
              demand_types=["licenciamento"])
    _seed_doc(db_session, title="Doc C Genérico", identifier="C",
              demand_types=None)

    results = search_legislation(db_session, demand_type="car")

    assert len(results) == 1
    assert results[0].id == doc_a.id


def test_no_demand_type_returns_all_docs_including_null(db_session):
    """Sem filtro de demand_type, retorna A, B e C (docs com demand_types=NULL entram)."""
    doc_a = _seed_doc(db_session, title="Doc A CAR", identifier="A",
                      demand_types=["car", "retificacao_car"])
    doc_b = _seed_doc(db_session, title="Doc B Licenciamento", identifier="B",
                      demand_types=["licenciamento"])
    doc_c = _seed_doc(db_session, title="Doc C Genérico", identifier="C",
                      demand_types=None)

    results = search_legislation(db_session)

    ids = {r.id for r in results}
    assert ids == {doc_a.id, doc_b.id, doc_c.id}


def test_demand_type_filter_ignores_docs_with_null_demand_types(db_session):
    """Bug cosmético: doc 'genérico' (demand_types=NULL) NÃO deve aparecer quando
    há especializado para a demanda. Regra documentada na Sprint -1 C."""
    _seed_doc(db_session, title="Doc Genérico", identifier="GEN", demand_types=None)
    doc_esp = _seed_doc(db_session, title="Doc PRAD", identifier="PRAD",
                        demand_types=["compensacao"])

    results = search_legislation(db_session, demand_type="compensacao")

    assert len(results) == 1
    assert results[0].id == doc_esp.id


def test_demand_type_combined_with_uf_filter(db_session):
    """Filtros UF e demand_type convivem."""
    doc_go_car = _seed_doc(db_session, title="Lei GO CAR", identifier="GO-1",
                           scope="estadual", uf="GO",
                           demand_types=["car"])
    _seed_doc(db_session, title="Lei MT CAR", identifier="MT-1",
              scope="estadual", uf="MT",
              demand_types=["car"])
    _seed_doc(db_session, title="Lei GO Licenciamento", identifier="GO-2",
              scope="estadual", uf="GO",
              demand_types=["licenciamento"])
    doc_federal_car = _seed_doc(db_session, title="Código Florestal",
                                identifier="Lei 12.651/2012",
                                scope="federal", uf=None,
                                demand_types=["car", "retificacao_car"])

    results = search_legislation(db_session, uf="GO", demand_type="car")

    ids = {r.id for r in results}
    # Deve incluir GO/car + federal/car, excluir MT/car e GO/licenciamento
    assert ids == {doc_go_car.id, doc_federal_car.id}
