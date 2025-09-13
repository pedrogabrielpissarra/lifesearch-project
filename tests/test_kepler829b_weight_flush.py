import pytest
from lifesearch.lifesearch_main import calculate_esi_score
from app import create_app
from lifesearch.data import normalize_name
import pandas as pd

# Planet data used for deterministic ESI calculations
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
    """Prepare session and monkeypatch data fetchers for tests."""
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


def test_reducing_habitable_zone_should_reduce_esi(client, monkeypatch):
    norm = _setup_session(client, monkeypatch)

    # Measure baseline ESI using initial weights
    resp_base = client.post(
        '/api/planets/reference_values',
        json={'use_individual_weights': True,
              'planet_weights': {norm: {'habitability': initial_hab_weights}}}
    ).get_json()
    esi_base = resp_base['planets'][0]['esi']

    # Apply lower Habitable Zone weight
    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.18}}}
    })
    resp_after = client.post(
        '/api/planets/reference_values',
        json={'use_individual_weights': True,
              'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.18}}}}
    ).get_json()
    esi_after = resp_after['planets'][0]['esi']

    expected_after, _ = calculate_esi_score(
        planet_data,
        {'Habitable Zone': 0.18, 'Size': initial_hab_weights['Size'], 'Density': initial_hab_weights['Density']},
    )
    assert esi_after < esi_base
    assert pytest.approx(expected_after, rel=1e-6) == esi_after
    assert 0.0 <= esi_after <= 100.0


def test_same_values_applied_twice_must_not_accumulate(client, monkeypatch):
    norm = _setup_session(client, monkeypatch)

    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.18}}}
    })
    resp_first = client.post(
        '/api/planets/reference_values',
        json={'use_individual_weights': True,
              'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.18}}}}
    ).get_json()
    esi_first = resp_first['planets'][0]['esi']

    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.18}}}
    })
    resp_second = client.post(
        '/api/planets/reference_values',
        json={'use_individual_weights': True,
              'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.18}}}}
    ).get_json()
    esi_second = resp_second['planets'][0]['esi']

    expected, _ = calculate_esi_score(
        planet_data,
        {'Habitable Zone': 0.18, 'Size': initial_hab_weights['Size'], 'Density': initial_hab_weights['Density']},
    )
    assert pytest.approx(expected, rel=1e-6) == esi_first
    assert pytest.approx(expected, rel=1e-6) == esi_second
    assert pytest.approx(esi_first, rel=1e-6) == esi_second
    assert 0.0 <= esi_second <= 100.0
