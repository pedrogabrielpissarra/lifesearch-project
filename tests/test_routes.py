import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # Desativa CSRF nos testes
    with app.test_client() as client:
        with app.app_context():
            yield client

def test_index_get(client):
    """Deve carregar a página inicial"""
    response = client.get("/")
    assert response.status_code == 200
    assert b"LifeSearch" in response.data  # Procura texto no HTML

def test_index_post_invalid(client):
    """Deve falhar se enviar sem planetas"""
    response = client.post("/", data={"planet_names": "", "parameter_overrides": ""}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Please enter at least one planet name." in response.data

def test_clear_session(client):
    """Testa limpar sessão via API"""
    response = client.post("/api/clear-session")
    assert response.status_code == 200
    assert response.get_json()["status"] == "partial session cleared"

def test_debug_session(client):
    """Testa endpoint de debug"""
    response = client.get("/api/debug-session")
    assert response.status_code == 200
    data = response.get_json()
    assert "planet_names_list" in data
    assert "use_individual_weights" in data
