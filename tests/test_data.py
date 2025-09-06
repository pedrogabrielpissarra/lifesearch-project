import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from tempfile import TemporaryDirectory
from lifesearch.data import (
    normalize_name, convert_numpy_types, write_to_cache, read_from_cache,
    fetch_exoplanet_data_api, load_hwc_catalog, load_hzgallery_catalog,
    merge_data_sources, CACHE_DIR
)

class TestData(unittest.TestCase):
    def setUp(self):
        """It should set up a temporary cache directory for tests"""
        self.temp_dir = TemporaryDirectory()
        self.original_cache_dir = CACHE_DIR
        from lifesearch import data
        data.CACHE_DIR = self.temp_dir.name

    def tearDown(self):
        """It should clean up the temporary cache directory and restore original settings"""
        from lifesearch import data
        data.CACHE_DIR = self.original_cache_dir
        self.temp_dir.cleanup()

    def test_normalize_name_basic(self):
        """It should normalize planet names correctly"""
        self.assertEqual(normalize_name(" Kepler-22 b "), "kepler22b")
        self.assertEqual(normalize_name(None), "")
        self.assertEqual(normalize_name("Gliese–581 d"), "gliese581d")

    def test_normalize_name_edge_cases(self):
        """It should handle edge cases in planet name normalization"""
        self.assertEqual(normalize_name("TRAPPIST-1 e!"), "trappist1e")
        self.assertEqual(normalize_name(""), "")
        self.assertEqual(normalize_name(123), "")
        self.assertEqual(normalize_name("Proxima Centauri b (alt)"), "proximacentauribalt")

    def test_convert_numpy_types(self):
        """It should convert numpy types into native Python types"""
        data = {
            "int": np.int64(42),
            "float": np.float32(3.14),
            "bool": np.bool_(True),
            "nan": np.nan
        }
        converted = convert_numpy_types(data)
        self.assertIsInstance(converted["int"], int)
        self.assertIsInstance(converted["float"], float)
        self.assertIsInstance(converted["bool"], bool)
        self.assertIsNone(converted["nan"])

    def test_convert_numpy_types_nested(self):
        """It should handle nested structures with numpy types"""
        data = {"nested": [{"val": np.float64(1.23), "nan": np.nan}]}
        converted = convert_numpy_types(data)
        self.assertIsInstance(converted["nested"][0]["val"], float)
        self.assertIsNone(converted["nested"][0]["nan"])

    def test_cache_write_and_read(self):
        """It should write to cache and read back the same values"""
        slug = "testplanet"
        series = pd.Series({"mass": 1.0, "radius": 1.0})
        write_to_cache(slug, series)
        read_series = read_from_cache(slug)
        self.assertIsInstance(read_series, pd.Series)
        self.assertEqual(read_series["mass"], 1.0)
        self.assertEqual(read_series["radius"], 1.0)

    def test_cache_expiration(self):
        """It should return None for expired cache entries"""
        slug = "expiredplanet"
        cache_file = os.path.join(self.temp_dir.name, f"{slug}.json")
        expired_time = (datetime.now() - timedelta(hours=25)).isoformat()
        data = {"timestamp": expired_time, "data_dict": {"mass": 1.0}}
        with open(cache_file, 'w') as f:
            json.dump(data, f)
        self.assertIsNone(read_from_cache(slug))

    def test_cache_read_invalid_json(self):
        """It should handle invalid JSON in cache files gracefully"""
        slug = "invalidjson"
        cache_file = os.path.join(self.temp_dir.name, f"{slug}.json")
        with open(cache_file, 'w') as f:
            f.write("invalid json")
        self.assertIsNone(read_from_cache(slug))

    def test_merge_data_sources_basic(self):
        """It should merge API, HWC, and HZ data with correct priority"""
        api_data = pd.Series({"pl_name": "Kepler-22 b", "pl_masse": 10})
        hwc_df = pd.DataFrame([{"P_NAME": "Kepler-22 b", "P_MASS": 12}])
        hz_df = pd.DataFrame([{"PLANET": "Kepler-22 b", "OHZIN": 0.5}])
        combined = merge_data_sources(api_data, hwc_df, hz_df, "kepler22b")
        self.assertEqual(combined["pl_masse"], 10)
        self.assertIn("hz_ohzin", combined)

    def test_merge_data_sources_no_api(self):
        """It should merge HWC and HZ data when API data is missing"""
        hwc_df = pd.DataFrame([{"P_NAME": "Kepler-22 b", "P_MASS": 12, "P_ESI": 0.85}])
        hz_df = pd.DataFrame([{"PLANET": "Kepler-22 b", "OHZIN": 0.5}])
        combined = merge_data_sources(None, hwc_df, hz_df, "kepler22b", "Kepler-22 b")
        self.assertEqual(combined["pl_masse"], 12.0)
        self.assertEqual(combined["pl_esi_hwc"], 85.0)
        self.assertEqual(combined["hz_ohzin"], 0.5)
        self.assertEqual(combined["pl_name"], "Kepler-22 b")

    @patch('lifesearch.data.requests.get')
    def test_fetch_exoplanet_data_api(self, mock_get):
        """It should fetch exoplanet data from the API and cache it"""
        mock_response = MagicMock()
        mock_response.text = "pl_name,pl_masse\nKepler-22 b,10"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        data = fetch_exoplanet_data_api("Kepler-22 b")
        self.assertIsInstance(data, pd.Series)
        self.assertEqual(data["pl_masse"], 10)

    @patch('lifesearch.data.requests.get')
    def test_fetch_exoplanet_data_api_failure(self, mock_get):
        """It should handle API fetch failures gracefully"""
        mock_get.side_effect = Exception("API error")
        self.assertIsNone(fetch_exoplanet_data_api("Invalid"))

    @patch('pandas.read_csv')
    def test_load_hwc_catalog(self, mock_read_csv):
        """It should load the HWC catalog correctly"""
        mock_df = pd.DataFrame({"P_NAME": ["Kepler-22 b"]})
        mock_read_csv.return_value = mock_df
        df = load_hwc_catalog("fake_path")
        self.assertEqual(len(df), 1)

    @patch('pandas.read_csv')
    def test_load_hzgallery_catalog(self, mock_read_csv):
        """It should load the HZGallery catalog correctly"""
        mock_df = pd.DataFrame({"PLANET": ["Kepler-22 b"]})
        mock_read_csv.return_value = mock_df
        df = load_hzgallery_catalog("fake_path")
        self.assertEqual(len(df), 1)

    @patch('pandas.read_csv')
    def test_load_hwc_catalog_not_found(self, mock_read_csv):
        """It should return an empty DataFrame if HWC catalog file is not found"""
        mock_read_csv.side_effect = FileNotFoundError
        df = load_hwc_catalog("invalid")
        self.assertTrue(df.empty)

if __name__ == '__main__':
    unittest.main()