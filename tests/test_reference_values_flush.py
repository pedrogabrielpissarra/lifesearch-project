import pytest
from app import create_app
from lifesearch.data import normalize_name
from lifesearch.lifesearch_main import calculate_esi_score
import pandas as pd

planet_data = {
    'pl_name': 'Kepler-829 b',
    'pl_rade': 2.9,
    'pl_dens': 0.889,
    'pl_eqt': 562.0,
    'classification': 'Neptunian',
}

initial_hab_weights = {
    'Habitable Zone': 0.4586330935251799,
    'Size': 0.6430868167202572,
    'Density': 0.7020023557126032,
}

@pytest.fixture
def client():
    app = create_app()
    app.config.update({"TESTING": True, "SECRET_KEY": "test", "WTF_CSRF_ENABLED": False})
    with app.test_client() as client:
        yield client


def _setup_session(client, monkeypatch):
    def mock_process(name, data, weights):
        esi, _ = calculate_esi_score(planet_data, weights.get('habitability', {}))
        return {
            'planet_data_dict': {'pl_name': name, 'classification': planet_data['classification']},
            'scores_for_report': {'ESI': (esi, ''), 'PHI': (0.0, '')},
        }

    monkeypatch.setattr('app.routes.process_planet_data', mock_process)
    monkeypatch.setattr('app.routes.fetch_exoplanet_data_api', lambda name: {'pl_name': name})
    monkeypatch.setattr('app.routes.merge_data_sources', lambda api, hwc, hz, norm: api)
    monkeypatch.setattr('app.routes.load_hwc_catalog', lambda path: pd.DataFrame())
    monkeypatch.setattr('app.routes.load_hzgallery_catalog', lambda path: pd.DataFrame())

    norm = normalize_name('Kepler-829 b')
    client.post('/api/save-planets-to-session', json={'planet_names': ['Kepler-829 b']})
    with client.session_transaction() as sess:
        sess['initial_hab_weights'] = {norm: initial_hab_weights}
        sess['initial_phi_weights'] = {norm: {}}
    return norm


def test_reference_values_flushes_without_saving(client, monkeypatch):
    norm = _setup_session(client, monkeypatch)

    resp_base = client.post(
        '/api/planets/reference_values',
        json={'use_individual_weights': True,
              'planet_weights': {norm: {'habitability': initial_hab_weights}}}
    ).get_json()
    esi_base = resp_base['planets'][0]['esi']

    updates = {
        'Habitable Zone': 0.18,
        'Size': initial_hab_weights['Size'],
        'Density': initial_hab_weights['Density'],
    }
    resp_after = client.post(
        '/api/planets/reference_values',
        json={'use_individual_weights': True,
              'planet_weights': {norm: {'habitability': updates}}}
    ).get_json()
    esi_after = resp_after['planets'][0]['esi']

    expected_after, _ = calculate_esi_score(planet_data, updates)
    assert esi_after < esi_base
    assert pytest.approx(expected_after, rel=1e-6) == esi_after

    resp_again = client.post(
        '/api/planets/reference_values',
        json={'use_individual_weights': True,
              'planet_weights': {norm: {'habitability': updates}}}
    ).get_json()
    esi_again = resp_again['planets'][0]['esi']
    assert pytest.approx(esi_after, rel=1e-6) == esi_again
