import pytest
import pandas as pd
from app import create_app

@pytest.fixture
def client(monkeypatch):
    app = create_app()
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test_secret'
    })

    sample_api_data = {
        'pl_name': 'Proxima Cen b',
        'pl_rade': 1.1,
        'pl_dens': 5.5,
        'pl_eqt': 240,
        'pl_orbeccen': 0.1,
        'st_spectype': 'M5V',
        'st_age': 4.8,
        'pl_masse': 1.2
    }

    # Patch external data functions
    monkeypatch.setattr('app.routes.fetch_exoplanet_data_api', lambda name: sample_api_data)
    monkeypatch.setattr('app.routes.load_hwc_catalog', lambda path: pd.DataFrame())
    monkeypatch.setattr('app.routes.load_hzgallery_catalog', lambda path: pd.DataFrame())
    monkeypatch.setattr('app.routes.merge_data_sources', lambda api, hwc, hz, name: sample_api_data)

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['planet_names_list'] = ['Proxima Cen b']
        yield client


def test_configure_reference_phi_value(client):
    response = client.get('/configure')
    assert response.status_code == 200
    assert b'22.50%' in response.data
