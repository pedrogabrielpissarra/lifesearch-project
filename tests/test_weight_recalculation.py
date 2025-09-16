import pandas as pd
import pytest

from app import create_app
from lifesearch.data import normalize_name
from lifesearch.lifesearch_main import calculate_esi_score, calculate_phi_score


planet_data = {
    'pl_name': 'Kepler-276 c',
    'pl_rade': 2.9,
    'pl_dens': 0.889,
    'pl_eqt': 562.0,
    'classification': 'Neptunian',
    'st_spectype': 'G',
    'st_age': 5.0,
    'pl_orbeccen': 0.1,
}

initial_hab_weights = {
    'Habitable Zone': 0.6234718826405867,
    'Size': 0.5128205128205128,
    'Density': 0.27812499999999996,
}

initial_phi_weights = {
    'Solid Surface': 0.0,
    'Stable Energy': 0.0,
    'Life Compounds': 0.0,
    'Stable Orbit': 0.050625,
}


@pytest.fixture
def client():
    app = create_app()
    app.config.update({"TESTING": True, "SECRET_KEY": "test", "WTF_CSRF_ENABLED": False})
    with app.test_client() as client:
        yield client


def _setup_session(client):
    norm = normalize_name('Kepler-276 c')
    with client.session_transaction() as sess:
        sess['planet_names_list'] = ['Kepler-276 c']
        sess['initial_hab_weights'] = {norm: initial_hab_weights}
        sess['initial_phi_weights'] = {norm: initial_phi_weights}


def _patch_processing(monkeypatch):
    captured = {}

    def mock_process(name, data, weights):
        captured['habitability'] = weights.get('habitability', {}).copy()
        captured['phi'] = weights.get('phi', {}).copy()
        esi, _ = calculate_esi_score(planet_data, captured['habitability'])
        phi, _ = calculate_phi_score(planet_data, captured['phi'])
        return {
            'planet_data_dict': {'pl_name': name, 'classification': planet_data['classification']},
            'scores_for_report': {'ESI': (esi, ''), 'PHI': (phi, '')},
        }

    monkeypatch.setattr('app.routes.process_planet_data', mock_process)
    monkeypatch.setattr('app.routes.fetch_exoplanet_data_api', lambda name: {'pl_name': name})
    monkeypatch.setattr('app.routes.merge_data_sources', lambda api, hwc, hz, norm: api)
    monkeypatch.setattr('app.routes.load_hwc_catalog', lambda path: pd.DataFrame())
    monkeypatch.setattr('app.routes.load_hzgallery_catalog', lambda path: pd.DataFrame())
    return captured


def test_reference_endpoint_returns_baseline_scores_without_deltas(client, monkeypatch):
    _setup_session(client)
    captured = _patch_processing(monkeypatch)

    response = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'weights_are_deltas': True,
        'planet_weights': {}
    }).get_json()

    planet = response['planets'][0]
    expected_esi, _ = calculate_esi_score(planet_data, captured['habitability'])
    expected_phi, _ = calculate_phi_score(planet_data, captured['phi'])
    assert pytest.approx(expected_esi, rel=1e-6) == planet['esi']
    assert pytest.approx(expected_phi, rel=1e-6) == planet['phi']


def test_reference_endpoint_applies_negative_delta(client, monkeypatch):
    _setup_session(client)
    captured = _patch_processing(monkeypatch)

    norm = normalize_name('Kepler-276 c')
    client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'weights_are_deltas': True,
        'planet_weights': {}
    })
    baseline_weights = captured['habitability'].copy()

    delta = -0.2
    response = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'weights_are_deltas': True,
        'planet_weights': {norm: {'habitability': {'Habitable Zone': delta}}}
    }).get_json()

    actual_weights = captured['habitability'].copy()
    assert pytest.approx(baseline_weights['Habitable Zone'] + delta, rel=1e-6) == actual_weights['Habitable Zone']
    expected_esi, _ = calculate_esi_score(planet_data, actual_weights)
    planet = response['planets'][0]
    assert pytest.approx(expected_esi, rel=1e-6) == planet['esi']


def test_save_planet_weights_stores_and_clears_deltas(client):
    _setup_session(client)
    norm = normalize_name('Kepler-276 c')

    delta_payload = {
        'use_individual_weights': True,
        'weights_are_deltas': True,
        'planet_weights': {norm: {'habitability': {'Habitable Zone': -0.12}}}
    }
    response = client.post('/api/save-planet-weights', json=delta_payload).get_json()

    with client.session_transaction() as sess:
        stored = sess['planet_weights'][norm]['habitability']
        assert pytest.approx(-0.12, rel=1e-9) == stored['Habitable Zone']
        assert sess['use_individual_weights'] is True

    expected_actual = initial_hab_weights.copy()
    expected_actual['Habitable Zone'] -= 0.12
    saved_actual = response['saved_weights'][norm]['habitability']
    assert pytest.approx(expected_actual['Habitable Zone'], rel=1e-6) == saved_actual['Habitable Zone']

    reset_payload = {
        'use_individual_weights': True,
        'weights_are_deltas': True,
        'planet_weights': {norm: {'habitability': {}}}
    }
    client.post('/api/save-planet-weights', json=reset_payload)
    with client.session_transaction() as sess:
        assert sess.get('planet_weights') in (None, {})


def test_reference_endpoint_accepts_absolute_payloads(client, monkeypatch):
    _setup_session(client)
    captured = _patch_processing(monkeypatch)

    norm = normalize_name('Kepler-276 c')
    client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'weights_are_deltas': True,
        'planet_weights': {}
    })
    baseline_weights = captured['habitability'].copy()
    absolute_value = baseline_weights['Habitable Zone'] - 0.15
    response = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'weights_are_deltas': False,
        'planet_weights': {norm: {'habitability': {'Habitable Zone': absolute_value}}}
    }).get_json()

    actual_weights = baseline_weights.copy()
    actual_weights['Habitable Zone'] = absolute_value
    expected_esi, _ = calculate_esi_score(planet_data, actual_weights)
    planet = response['planets'][0]
    assert pytest.approx(expected_esi, rel=1e-6) == planet['esi']


def test_reference_endpoint_uses_session_deltas_when_payload_empty(client, monkeypatch):
    _setup_session(client)
    captured = _patch_processing(monkeypatch)

    norm = normalize_name('Kepler-276 c')
    client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'weights_are_deltas': True,
        'planet_weights': {}
    })
    baseline_weights = captured['habitability'].copy()
    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'weights_are_deltas': True,
        'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.1}}}
    })

    response = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'weights_are_deltas': True,
        'planet_weights': {}
    }).get_json()

    actual_weights = captured['habitability'].copy()
    assert pytest.approx(baseline_weights['Habitable Zone'] + 0.1, rel=1e-6) == actual_weights['Habitable Zone']
    expected_esi, _ = calculate_esi_score(planet_data, actual_weights)
    planet = response['planets'][0]
    assert pytest.approx(expected_esi, rel=1e-6) == planet['esi']
