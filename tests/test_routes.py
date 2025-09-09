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

    def test_default_weights_do_not_change_reference(self, client, monkeypatch):
        from lifesearch.data import normalize_name

        def mock_process_planet_data(name, combined, weights):
            return {
                'planet_data_dict': {'pl_name': name, 'classification': 'Class'},
                'scores_for_report': {'ESI': (86.76, ''), 'PHI': (60.0, '')}
            }

        monkeypatch.setattr('app.routes.process_planet_data', mock_process_planet_data)
        monkeypatch.setattr('app.routes.fetch_exoplanet_data_api', lambda name: {'pl_name': name})
        monkeypatch.setattr('app.routes.merge_data_sources', lambda api, hwc, hz, norm: api)

        client.post('/api/save-planets-to-session', json={'planet_names': ['Kepler-452 b']})

        norm_name = normalize_name('Kepler-452 b')
        with client.session_transaction() as sess:
            sess['initial_hab_weights'] = {norm_name: {'Size': 1.0, 'Density': 1.0, 'Habitable Zone': 1.0}}
            sess['initial_phi_weights'] = {norm_name: {'Solid Surface': 0.25, 'Stable Energy': 0.25, 'Life Compounds': 0.25, 'Stable Orbit': 0.25}}

        base = client.get('/api/planets/reference_values').json['planets'][0]

        save_payload = {
            'use_individual_weights': True,
            'planet_weights': {
                'Kepler-452 b': {
                    'habitability': {'Size': 1.0, 'Density': 1.0, 'Habitable Zone': 1.0},
                    'phi': {'Solid Surface': 0.25, 'Stable Energy': 0.25, 'Life Compounds': 0.25, 'Stable Orbit': 0.25}
                }
            }
        }
        client.post('/api/save-planet-weights', json=save_payload)

        after = client.post('/api/planets/reference_values', json={'use_individual_weights': False, 'planet_weights': {}}).json['planets'][0]

        assert base == after
        with client.session_transaction() as sess:
            assert sess.get('planet_weights') in (None, {})
