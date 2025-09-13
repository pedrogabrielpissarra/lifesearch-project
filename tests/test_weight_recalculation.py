import pytest
from lifesearch.lifesearch_main import calculate_esi_score, calculate_phi_score
from app import create_app
from lifesearch.data import normalize_name
import pandas as pd

@pytest.fixture
def client():
    app = create_app()
    app.config.update({"TESTING": True, "SECRET_KEY": "test", "WTF_CSRF_ENABLED": False})
    with app.test_client() as client:
        yield client

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


def test_esi_decreases_when_weight_decreases():
    base_esi, _ = calculate_esi_score(planet_data, initial_hab_weights)
    new_weights = initial_hab_weights.copy()
    new_weights['Habitable Zone'] = 0.36
    new_esi, _ = calculate_esi_score(planet_data, new_weights)
    assert new_esi < base_esi


def test_esi_returns_to_default_when_weights_reset():
    base_esi, _ = calculate_esi_score(planet_data, initial_hab_weights)
    zero_weights = {k: 0.0 for k in initial_hab_weights}
    zero_esi, _ = calculate_esi_score(planet_data, zero_weights)
    reset_esi, _ = calculate_esi_score(planet_data, initial_hab_weights)
    assert pytest.approx(base_esi, rel=1e-6) == reset_esi
    assert zero_esi < base_esi


def test_phi_increases_proportionally():
    base_phi, _ = calculate_phi_score(planet_data, initial_phi_weights)
    increased = initial_phi_weights.copy()
    increased['Stable Orbit'] = 0.06
    new_phi, _ = calculate_phi_score(planet_data, increased)
    base_esi, _ = calculate_esi_score(planet_data, initial_hab_weights)
    assert base_phi < new_phi < 50.0
    esi_after, _ = calculate_esi_score(planet_data, initial_hab_weights)
    assert pytest.approx(base_esi, rel=1e-6) == esi_after


def test_reference_values_merge_initial_weights(client, monkeypatch):
    def mock_process(name, data, weights):
        esi, _ = calculate_esi_score(planet_data, weights.get('habitability', {}))
        phi, _ = calculate_phi_score(planet_data, weights.get('phi', {}))
        return {'planet_data_dict': {'pl_name': name, 'classification': planet_data['classification']},
                'scores_for_report': {'ESI': (esi, ''), 'PHI': (phi, '')}}

    monkeypatch.setattr('app.routes.process_planet_data', mock_process)
    monkeypatch.setattr('app.routes.fetch_exoplanet_data_api', lambda name: {'pl_name': name})
    monkeypatch.setattr('app.routes.merge_data_sources', lambda api, hwc, hz, norm: api)
    monkeypatch.setattr('app.routes.load_hwc_catalog', lambda path: pd.DataFrame())
    monkeypatch.setattr('app.routes.load_hzgallery_catalog', lambda path: pd.DataFrame())

    norm = normalize_name('Kepler-276 c')
    client.post('/api/save-planets-to-session', json={'planet_names': ['Kepler-276 c']})
    with client.session_transaction() as sess:
        sess['initial_hab_weights'] = {norm: initial_hab_weights}
        sess['initial_phi_weights'] = {norm: initial_phi_weights}

    payload = {'use_individual_weights': True,
               'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.36}}}}
    resp = client.post('/api/planets/reference_values', json=payload).get_json()
    esi_val = resp['planets'][0]['esi']
    expected_esi, _ = calculate_esi_score(planet_data, {'Habitable Zone': 0.36})
    assert pytest.approx(expected_esi, rel=1e-6) == esi_val


def test_esi_recalculation_resets_previous_value(client, monkeypatch):
    def mock_process(name, data, weights):
        esi, _ = calculate_esi_score(planet_data, weights.get('habitability', {}))
        phi, _ = calculate_phi_score(planet_data, weights.get('phi', {}))
        return {'planet_data_dict': {'pl_name': name, 'classification': planet_data['classification']},
                'scores_for_report': {'ESI': (esi, ''), 'PHI': (phi, '')}}

    monkeypatch.setattr('app.routes.process_planet_data', mock_process)
    monkeypatch.setattr('app.routes.fetch_exoplanet_data_api', lambda name: {'pl_name': name})
    monkeypatch.setattr('app.routes.merge_data_sources', lambda api, hwc, hz, norm: api)
    monkeypatch.setattr('app.routes.load_hwc_catalog', lambda path: pd.DataFrame())
    monkeypatch.setattr('app.routes.load_hzgallery_catalog', lambda path: pd.DataFrame())

    norm = normalize_name('Kepler-276 c')
    client.post('/api/save-planets-to-session', json={'planet_names': ['Kepler-276 c']})
    with client.session_transaction() as sess:
        sess['initial_hab_weights'] = {norm: initial_hab_weights}
        sess['initial_phi_weights'] = {norm: initial_phi_weights}

    # Save baseline zero weights
    zero_payload = {'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {k: 0.0 for k in initial_hab_weights}}}}
    client.post('/api/save-planet-weights', json=zero_payload)

    # First update to 0.5
    client.post('/api/save-planet-weights', json={'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.5}}}})
    resp = client.post('/api/planets/reference_values', json={'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.5}}}}).get_json()
    esi_first = resp['planets'][0]['esi']
    expected_first, _ = calculate_esi_score(planet_data, {'Habitable Zone': 0.5, 'Size': 0.0, 'Density': 0.0})
    assert pytest.approx(expected_first, rel=1e-6) == esi_first

    # Second update to 0.3 should override previous value
    client.post('/api/save-planet-weights', json={'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.3}}}})
    resp = client.post('/api/planets/reference_values', json={'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.3}}}}).get_json()
    esi_second = resp['planets'][0]['esi']
    expected_second, _ = calculate_esi_score(planet_data, {'Habitable Zone': 0.3, 'Size': 0.0, 'Density': 0.0})
    assert pytest.approx(expected_second, rel=1e-6) == esi_second
    assert esi_second < esi_first


def test_esi_restores_correct_value_without_manual_reset(client, monkeypatch):
    def mock_process(name, data, weights):
        esi, _ = calculate_esi_score(planet_data, weights.get('habitability', {}))
        phi, _ = calculate_phi_score(planet_data, weights.get('phi', {}))
        return {'planet_data_dict': {'pl_name': name, 'classification': planet_data['classification']},
                'scores_for_report': {'ESI': (esi, ''), 'PHI': (phi, '')}}

    monkeypatch.setattr('app.routes.process_planet_data', mock_process)
    monkeypatch.setattr('app.routes.fetch_exoplanet_data_api', lambda name: {'pl_name': name})
    monkeypatch.setattr('app.routes.merge_data_sources', lambda api, hwc, hz, norm: api)
    monkeypatch.setattr('app.routes.load_hwc_catalog', lambda path: pd.DataFrame())
    monkeypatch.setattr('app.routes.load_hzgallery_catalog', lambda path: pd.DataFrame())

    norm = normalize_name('Kepler-276 c')
    client.post('/api/save-planets-to-session', json={'planet_names': ['Kepler-276 c']})
    with client.session_transaction() as sess:
        sess['initial_hab_weights'] = {norm: initial_hab_weights}
        sess['initial_phi_weights'] = {norm: initial_phi_weights}

    zero_payload = {'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {k: 0.0 for k in initial_hab_weights}}}}
    client.post('/api/save-planet-weights', json=zero_payload)

    client.post('/api/save-planet-weights', json={'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.5}}}})

    # Now set Habitable Zone back to 0 without resending other sliders
    client.post('/api/save-planet-weights', json={'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.0}}}})
    resp = client.post('/api/planets/reference_values', json={'use_individual_weights': True,
                    'planet_weights': {norm: {'habitability': {'Habitable Zone': 0.0}}}}).get_json()
    esi_final = resp['planets'][0]['esi']
    base_expected, _ = calculate_esi_score(planet_data, {'Habitable Zone': 0.0, 'Size': 0.0, 'Density': 0.0})
    assert pytest.approx(base_expected, rel=1e-6) == esi_final


def _setup_reference(client, monkeypatch):
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

    norm = normalize_name('Kepler-276 c')
    client.post('/api/save-planets-to-session', json={'planet_names': ['Kepler-276 c']})
    with client.session_transaction() as sess:
        sess['initial_hab_weights'] = {norm: initial_hab_weights}
        sess['initial_phi_weights'] = {norm: initial_phi_weights}
    return norm


def test_flush_values_before_recalculate(client, monkeypatch):
    norm = _setup_reference(client, monkeypatch)

    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'phi': {'Stable Orbit': 0.56}}}
    })
    resp1 = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'phi': {'Stable Orbit': 0.56}}}
    }).get_json()
    phi_first = resp1['planets'][0]['phi']
    expected_first, _ = calculate_phi_score(planet_data, {'Stable Orbit': 0.56})
    assert pytest.approx(expected_first, rel=1e-6) == phi_first

    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'phi': {'Stable Orbit': 0.86}}}
    })
    resp2 = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'phi': {'Stable Orbit': 0.86}}}
    }).get_json()
    phi_second = resp2['planets'][0]['phi']
    expected_second, _ = calculate_phi_score(planet_data, {'Stable Orbit': 0.86})
    assert pytest.approx(expected_second, rel=1e-6) == phi_second
    assert phi_second != phi_first


def test_reposition_instead_of_accumulate(client, monkeypatch):
    norm = _setup_reference(client, monkeypatch)

    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'phi': {'Stable Orbit': 0.2}}}
    })
    resp1 = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'phi': {'Stable Orbit': 0.2}}}
    }).get_json()
    phi_low = resp1['planets'][0]['phi']

    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'phi': {'Stable Orbit': 0.8}}}
    })
    resp2 = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'phi': {'Stable Orbit': 0.8}}}
    }).get_json()
    phi_high = resp2['planets'][0]['phi']

    assert phi_high > phi_low
    assert phi_high <= 100.0


def test_reduce_weight_recalculates_instead_of_accumulating(client, monkeypatch):
    norm = _setup_reference(client, monkeypatch)

    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'habitability': {'Density': 0.97}}}
    })
    resp1 = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'habitability': {'Density': 0.97}}}
    }).get_json()
    first_esi = resp1['planets'][0]['esi']

    client.post('/api/save-planet-weights', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'habitability': {'Density': 0.50}}}
    })
    resp2 = client.post('/api/planets/reference_values', json={
        'use_individual_weights': True,
        'planet_weights': {norm: {'habitability': {'Density': 0.50}}}
    }).get_json()
    second_esi = resp2['planets'][0]['esi']

    assert second_esi < first_esi
