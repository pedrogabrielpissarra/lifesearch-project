import pytest
from unittest.mock import patch
from lifesearch.data import load_hwc_catalog, load_hzgallery_catalog
from app.routes import prepare_planet_dataset


@pytest.fixture
def mock_catalogs(tmp_path):
    hwc_path = tmp_path / "hwc.csv"
    hz_path = tmp_path / "table-hzgallery.csv"
    hwc_path.write_text("pl_name,stellar_type\nKepler-22 b,G2V")
    hz_path.write_text("pl_name,hz_status\nKepler-22 b,In HZ")
    return str(hwc_path), str(hz_path)


def test_prepare_planet_dataset_prefers_api(mock_catalogs):
    """Ensures API data is used when available."""
    hwc_path, hz_path = mock_catalogs
    hwc_df = load_hwc_catalog(hwc_path)
    hz_df = load_hzgallery_catalog(hz_path)

    api_data = {"pl_name": "Kepler-22 b", "st_teff": 5518}

    normalized, combined = prepare_planet_dataset("Kepler-22 b", api_data, hwc_df, hz_df, logger=None)

    # Must use API first
    assert normalized.lower() == "kepler22b"
    assert "st_teff" in combined
    assert combined["st_teff"] == 5518


def test_prepare_planet_dataset_fallback_if_api_missing(mock_catalogs):
    """Ensures fallback is used when API data is None."""
    hwc_path, hz_path = mock_catalogs
    hwc_df = load_hwc_catalog(hwc_path)
    hz_df = load_hzgallery_catalog(hz_path)

    with patch("app.routes.fetch_exoplanet_data_api", return_value=None):
        normalized, combined = prepare_planet_dataset("Kepler-22 b", None, hwc_df, hz_df, logger=None)

    assert normalized.lower() == "kepler22b"
    assert combined is not None
    assert "pl_name" in combined
