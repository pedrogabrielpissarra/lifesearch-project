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
    def mock_process(name, data, weights):
        esi, _ = calculate_esi_score(planet_data, weights.get('habitability', {}))
        phi, _ = calculate_phi_score(planet_data, weights.get('phi', {}))
        return {
            'planet_data_dict': {'pl_name': name, 'classification': planet_data['classification']},
            'scores_for_report': {'ESI': (esi, ''), 'PHI': (phi, '')},
        }

    monkeypatch.setattr('app.routes.process_planet_data', mock_process)
    monkeypatch.setattr('app.routes.fetch_exoplanet_data_api', lambda name: {'pl_name': name})
    monkeypatch.setattr('app.routes.merge_data_sources', lambda api, hwc, hz, norm: api)
    monkeypatch.setattr('app.routes.load_hwc_catalog', lambda path: pd.DataFrame())
    monkeypatch.setattr('app.routes.load_hzgallery_catalog', lambda path: pd.DataFrame())


def test_snake_case_weight_updates_reduce_esi(client, monkeypatch):
    _setup_session(client)
    _patch_processing(monkeypatch)

    # baseline using initial weights in snake_case
    payload_high = {
        'use_individual_weights': True,
        'planet_weights': {
            'Kepler-276 c': {
                'habitability': {
                    'habitable_zone': initial_hab_weights['Habitable Zone'],
                    'size': initial_hab_weights['Size'],
                    'density': initial_hab_weights['Density'],
                }
            }
        },
    }
    resp1 = client.post('/api/planets/reference_values', json=payload_high)
    base_esi = resp1.get_json()['planets'][0]['esi']

    payload_low = {
        'use_individual_weights': True,
        'planet_weights': {
            'Kepler-276 c': {
                'habitability': {
                    'habitable_zone': 0.36,
                    'size': initial_hab_weights['Size'],
                    'density': initial_hab_weights['Density'],
                }
            }
        },
    }
    resp2 = client.post('/api/planets/reference_values', json=payload_low)
    new_esi = resp2.get_json()['planets'][0]['esi']
    assert new_esi < base_esi


def test_save_planet_weights_canonicalizes_keys(client):
    norm = normalize_name('Kepler-276 c')
    with client.session_transaction() as sess:
        sess['initial_hab_weights'] = {norm: initial_hab_weights}
        sess['initial_phi_weights'] = {norm: initial_phi_weights}

    data = {
        'use_individual_weights': True,
        'planet_weights': {
            'Kepler-276 c': {
                'habitability': {'habitable_zone': 0.5},
            }
        },
    }
    client.post('/api/save-planet-weights', json=data)

    with client.session_transaction() as sess:
        stored = sess['planet_weights'][norm]['habitability']
        assert 'Habitable Zone' in stored
        assert 'habitable_zone' not in stored
