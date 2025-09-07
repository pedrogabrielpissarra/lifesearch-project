import pytest
from app import create_app  # Flask app vem de app/__init__.py


@pytest.fixture
def client():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test_secret"
    })
    with app.test_client() as client:
        yield client


class TestRoutes:
    def test_index_get(self, client):
        """GET em /index deve retornar 200 e conter LifeSearch Web"""
        response = client.get("/index")
        assert response.status_code == 200
        assert b"LifeSearch Web" in response.data

    def test_index_post_invalid(self, client):
        """POST em /index sem planetas deve retornar 200 e mensagem de erro"""
        response = client.post("/index", data={"planet_names": ""})
        assert response.status_code == 200
        assert b"Please enter at least one planet name." in response.data

    def test_clear_session(self, client):
        """POST em /api/clear-session deve limpar a sessão"""
        response = client.post("/api/clear-session")
        assert response.status_code == 200
        assert response.json["status"] == "partial session cleared"

    def test_debug_session(self, client):
        """GET em /api/debug-session deve retornar os dados da sessão"""
        response = client.get("/api/debug-session")
        assert response.status_code == 200
        assert "planet_names_list" in response.json
        assert "use_individual_weights" in response.json
        assert "planet_weights" in response.json
