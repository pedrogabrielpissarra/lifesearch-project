import pytest
from lifesearch.lifesearch_main import calculate_esi_score, calculate_phi_score
from app import create_app
from lifesearch.data import normalize_name
import pandas as pd

planet_data = {
    'pl_name': 'Kepler-221 d',
    'pl_rade': 2.73,
    'pl_dens': 0.388275,
    'pl_eqt': 2520.0,
    'classification': 'Superterran',
    'st_spectype': 'F',
    'st_age': 5.0,
    'pl_orbeccen': 0.1,
}

initial_hab_weights = {
    'Habitable Zone': 0.0,
    'Size': 0.5361930294906166,
    'Density': 0.28081123244929806,
}

initial_phi_weights = {
    'Solid Surface': 0.0,
    'Stable Energy': 0.0,
    'Life Compounds': 0.0,
    'Stable Orbit': 0.0,
}

@pytest.fixture
def client():
    app = create_app()
    app.config.update({"TESTING": True, "SECRET_KEY": "test", "WTF_CSRF_ENABLED": False})
    with app.test_client() as client:
        yield client

def _setup(client, monkeypatch):
    def mock_process(name, data, weights):
        esi, _ = calculate_esi_score(planet_data, weights.get('habitability', {}))
        phi, _ = calculate_phi_score(planet_data, weights.get('phi', {}))
        return {
            'planet_data_dict': {'pl_name': name, 'classification': planet_data['classification']},
            'scores_for_report': {'ESI': (esi, ''), 'PHI': (phi, '')}
        }

    monkeypatch.setattr('app.routes.process_planet_data', mock_process)
    monkeypatch.setattr('app.routes.fetch_exoplanet_data_api', lambda name: {'pl_name': name})
    monkeypatch.setattr('app.routes.merge_data_sources', lambda api, hwc, hz, norm: api)
    monkeypatch.setattr('app.routes.load_hwc_catalog', lambda path: pd.DataFrame())
    monkeypatch.setattr('app.routes.load_hzgallery_catalog', lambda path: pd.DataFrame())

    norm = normalize_name('Kepler-221 d')
    client.post('/api/save-planets-to-session', json={'planet_names': ['Kepler-221 d']})
    with client.session_transaction() as sess:
        sess['initial_hab_weights'] = {norm: initial_hab_weights}
        sess['initial_phi_weights'] = {norm: initial_phi_weights}
    return norm


def test_baseline_matches_reference_values_kepler_221d(client, monkeypatch):
    norm = _setup(client, monkeypatch)
    payload = {
        'use_individual_weights': True,
        'planet_weights': {norm: {'habitability': initial_hab_weights, 'phi': initial_phi_weights}}
    }
    client.post('/api/save-planet-weights', json=payload)
    resp = client.post('/api/planets/reference_values', json=payload).get_json()
    planet = resp['planets'][0]
    assert pytest.approx(44.81, abs=0.5) == planet['esi']
    assert pytest.approx(42.5, abs=0.5) == planet['phi']


def test_decreasing_size_should_not_accumulate(client, monkeypatch):
    norm = _setup(client, monkeypatch)
    base_payload = {'use_individual_weights': True, 'planet_weights': {norm: {'habitability': initial_hab_weights}}}
    client.post('/api/save-planet-weights', json=base_payload)
    esi_base = client.post('/api/planets/reference_values', json=base_payload).get_json()['planets'][0]['esi']

    client.post('/api/save-planet-weights', json={'use_individual_weights': True,
                                                 'planet_weights': {norm: {'habitability': {'Size': 0.30}}}})
    resp = client.post('/api/planets/reference_values', json={'use_individual_weights': True,
                                                             'planet_weights': {norm: {'habitability': {'Size': 0.30}}}}).get_json()
    esi_new = resp['planets'][0]['esi']
    assert esi_new < esi_base
    assert 0.0 <= esi_new <= 100.0


def test_decreasing_density_should_not_accumulate(client, monkeypatch):
    norm = _setup(client, monkeypatch)
    base_payload = {'use_individual_weights': True, 'planet_weights': {norm: {'habitability': initial_hab_weights}}}
    client.post('/api/save-planet-weights', json=base_payload)
    esi_base = client.post('/api/planets/reference_values', json=base_payload).get_json()['planets'][0]['esi']

    client.post('/api/save-planet-weights', json={'use_individual_weights': True,
                                                 'planet_weights': {norm: {'habitability': {'Density': 0.10}}}})
    resp = client.post('/api/planets/reference_values', json={'use_individual_weights': True,
                                                             'planet_weights': {norm: {'habitability': {'Density': 0.10}}}}).get_json()
    esi_new = resp['planets'][0]['esi']
    assert esi_new < esi_base
    assert 0.0 <= esi_new <= 100.0


def test_hz_zero_triggers_full_flush_then_changes_behave(client, monkeypatch):
    norm = _setup(client, monkeypatch)
    client.post('/api/save-planet-weights', json={'use_individual_weights': True,
                                                 'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.5,
                                                                                            'Size': initial_hab_weights['Size'],
                                                                                            'Density': initial_hab_weights['Density']}}}})
    client.post('/api/save-planet-weights', json={'use_individual_weights': True,
                                                 'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.0}}}})
    resp = client.post('/api/planets/reference_values', json={'use_individual_weights': True,
                                                             'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.0}}}}).get_json()
    esi_after_flush = resp['planets'][0]['esi']
    assert pytest.approx(44.81, abs=0.5) == esi_after_flush

    client.post('/api/save-planet-weights', json={'use_individual_weights': True,
                                                 'planet_weights': {norm: {'habitability': {'Size': 0.30}}}})
    resp2 = client.post('/api/planets/reference_values', json={'use_individual_weights': True,
                                                              'planet_weights': {norm: {'habitability': {'Size': 0.30}}}}).get_json()
    esi_after_size = resp2['planets'][0]['esi']
    assert esi_after_size < esi_after_flush


def test_increasing_weights_is_monotonic_but_must_not_exceed_100(client, monkeypatch):
    norm = _setup(client, monkeypatch)
    low_payload = {'use_individual_weights': True,
                   'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.0, 'Size': 0.20, 'Density': 0.20}}}}
    client.post('/api/save-planet-weights', json=low_payload)
    esi_low = client.post('/api/planets/reference_values', json=low_payload).get_json()['planets'][0]['esi']

    high_payload = {'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {'Size': 0.95, 'Density': 0.95}}}}
    client.post('/api/save-planet-weights', json=high_payload)
    esi_high = client.post('/api/planets/reference_values', json=high_payload).get_json()['planets'][0]['esi']

    assert esi_low < esi_high
    assert 0.0 <= esi_high <= 100.0
