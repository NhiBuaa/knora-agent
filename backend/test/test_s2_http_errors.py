"""Lexical operational failures retain the approved public unavailable status."""

from fastapi.testclient import TestClient

from knora import main
from knora.domain.errors import KnoraError


def test_lexical_unavailable_is_503_without_citation_or_empty_answer():
    app = main.create_app()

    @app.get("/s2-error-probe")
    def fail():
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    response = TestClient(app).get("/s2-error-probe")
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "LEXICAL_RETRIEVAL_UNAVAILABLE"}}
