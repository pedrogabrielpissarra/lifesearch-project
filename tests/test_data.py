import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
import os
import requests
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

    def test_read_from_cache_missing_timestamp(self):
        """It should log a warning and return None if cache has no timestamp"""
        slug = "notimestamp"
        cache_file = os.path.join(self.temp_dir.name, f"{slug}.json")
        with open(cache_file, "w") as f:
            json.dump({"data_dict": {"mass": 1.0}}, f)
        with self.assertLogs("lifesearch.data", level="WARNING") as cm:
            result = read_from_cache(slug)
            self.assertIsNone(result)
        self.assertTrue(any("no timestamp" in m for m in cm.output))  

    def test_read_from_cache_generic_exception(self):
        """It should handle generic exceptions gracefully"""
        from lifesearch import data
        slug = "genericerror"
        cache_file = os.path.join(self.temp_dir.name, f"{slug}.json")

        # Cria o arquivo real primeiro
        with open(cache_file, "w") as f:
            f.write("{}")

        # Agora sim força erro no open dentro do read_from_cache
        with patch("builtins.open", side_effect=OSError("disk error")):
            with self.assertLogs("lifesearch.data", level="ERROR") as cm:
                result = data.read_from_cache(slug)
                self.assertIsNone(result)
            self.assertTrue(any("Error reading from cache file" in m for m in cm.output))

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

    def test_merge_data_sources_hwc_no_pname(self):
        df = pd.DataFrame({"X": [1]})
        result = merge_data_sources(None, df, None, "kepler22b")
        self.assertIsInstance(result, dict)

    def test_merge_data_sources_hwc_generic_exception(self):
        df = pd.DataFrame({"P_NAME": ["Kepler-22 b"]})
        df.copy = MagicMock(side_effect=RuntimeError("copy fail"))
        result = merge_data_sources(None, df, None, "kepler22b")
        self.assertIsInstance(result, dict)

    def test_merge_data_sources_hz_no_planet(self):
        df = pd.DataFrame({"X": [1]})
        result = merge_data_sources(None, None, df, "kepler22b")
        self.assertIsInstance(result, dict)

    def test_merge_data_sources_hz_no_match(self):
        df = pd.DataFrame({"PLANET": ["Other"]})
        result = merge_data_sources(None, None, df, "kepler22b")
        self.assertIsInstance(result, dict)

    def test_merge_data_sources_hz_conversion_error(self):
        df = pd.DataFrame({"PLANET": ["kepler22b"], "OHZIN": ["not-a-number"]})
        result = merge_data_sources({}, None, df, "kepler22b")
        self.assertIsInstance(result, dict)

    def test_merge_data_sources_hz_generic_exception(self):
        df = pd.DataFrame({"PLANET": ["kepler22b"]})
        df.copy = MagicMock(side_effect=RuntimeError("boom"))
        result = merge_data_sources({}, None, df, "kepler22b")
        self.assertIsInstance(result, dict)

    def test_ensure_cache_ready(self):
        """It should create CACHE_DIR via ensure_cache_ready()"""
        import os
        import lifesearch.data as data
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "cache_test")
            # aponta o CACHE_DIR para um subdiretório temporário
            data.CACHE_DIR = target
            self.assertFalse(os.path.exists(target))
            data.ensure_cache_ready()
            self.assertTrue(os.path.exists(target))

    def test_write_to_cache_invalid_type(self):
        """It should log an error when trying to cache unsupported data type"""
        from lifesearch.data import write_to_cache
        slug = "invalidtype"
        # Passa tipo inválido (list)
        result = write_to_cache(slug, [1, 2, 3])
        # Deve retornar None e não criar arquivo
        cache_file = os.path.join(self.temp_dir.name, f"{slug}.json")
        self.assertFalse(os.path.exists(cache_file))
        self.assertIsNone(result)

    def test_write_to_cache_raises_exception(self):
        """It should handle exceptions during cache writing gracefully"""
        from lifesearch import data
        slug = "errorplanet"

        # Forçar erro: mock do open para lançar exceção
        with patch("builtins.open", side_effect=OSError("disk full")):
            result = data.write_to_cache(slug, {"mass": 1.0})
            self.assertIsNone(result)  # função deve capturar exceção

    def test_write_to_cache_invalid_type_logs(self):
        """It should log an error when trying to cache unsupported data type"""
        from lifesearch.data import write_to_cache
        with self.assertLogs("lifesearch.data", level="ERROR") as cm:
            result = write_to_cache("badslug", [1, 2, 3])  # tipo inválido
            self.assertIsNone(result)
        self.assertTrue(
            any("Unsupported data type for caching" in m for m in cm.output),
            f"Expected 'Unsupported data type for caching' not found in: {cm.output}"
        )

    def test_write_to_cache_raises_exception_logs(self):
        """It should log an error when cache writing raises an exception"""
        from lifesearch import data
        with patch("builtins.open", side_effect=OSError("disk full")):
            with self.assertLogs("lifesearch.data", level="ERROR") as cm:
                result = data.write_to_cache("errorplanet", {"mass": 1.0})
                self.assertIsNone(result)
            self.assertTrue(
                any("Error writing to cache file" in m for m in cm.output),
                f"Expected 'Error writing to cache file' not found in: {cm.output}"
            )

    def test_convert_numpy_types_bool_and_timestamp(self):
        """It should convert numpy bool and pandas Timestamp correctly"""
        from lifesearch.data import convert_numpy_types
        ts = pd.Timestamp("2020-01-01")
        self.assertEqual(convert_numpy_types(np.bool_(True)), True)
        self.assertEqual(convert_numpy_types(ts), ts.isoformat())

    def test_convert_numpy_types_passthrough(self):
        """It should return the original value if type is unsupported"""
        from lifesearch.data import convert_numpy_types
        custom_obj = object()
        result = convert_numpy_types(custom_obj)
        self.assertIs(result, custom_obj)

    def test_convert_numpy_types_series(self):
        """It should convert a pandas Series to a dict"""
        from lifesearch.data import convert_numpy_types
        series = pd.Series({"a": 1, "b": 2})
        result = convert_numpy_types(series)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 2)

    def test_convert_numpy_types_return_data(self):
        """It should return the value unchanged when type is not specially handled"""
        from lifesearch.data import convert_numpy_types
        value = "just a string"
        result = convert_numpy_types(value)
        self.assertEqual(result, value)

    def test_convert_numpy_types_fallback_final_return(self):
        """It should return data unchanged if type is not handled and not dict/list"""
        from lifesearch.data import convert_numpy_types
        value = (1, 2, 3)  # tuple não é tratado
        result = convert_numpy_types(value)
        self.assertEqual(result, value)

    def test_write_to_cache_problematic_data_str_fallback(self):
        """It should handle error when converting problematic_data to str inside exception block"""
        from lifesearch import data

        class BadStr:
            def __str__(self):
                raise ValueError("cannot stringify")

        bad_obj = {"bad": BadStr()}  # Vai explodir no str()

        # Forçar erro externo também (mock do open)
        with patch("builtins.open", side_effect=OSError("disk full")):
            result = data.write_to_cache("badslug", bad_obj)
            self.assertIsNone(result)

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

    @patch("lifesearch.data.requests.get")
    def test_fetch_exoplanet_data_api_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("bad request")
        mock_get.return_value = mock_response
        result = fetch_exoplanet_data_api("Kepler-22 b")
        self.assertIsNone(result)

    @patch("lifesearch.data.requests.get", side_effect=requests.exceptions.ConnectionError("conn error"))
    def test_fetch_exoplanet_data_api_connection_error(self, mock_get):
        result = fetch_exoplanet_data_api("Kepler-22 b")
        self.assertIsNone(result)

    @patch("lifesearch.data.requests.get", side_effect=requests.exceptions.Timeout("timeout"))
    def test_fetch_exoplanet_data_api_timeout(self, mock_get):
        result = fetch_exoplanet_data_api("Kepler-22 b")
        self.assertIsNone(result)

    @patch("lifesearch.data.requests.get", side_effect=requests.exceptions.RequestException("req error"))
    def test_fetch_exoplanet_data_api_request_exception(self, mock_get):
        result = fetch_exoplanet_data_api("Kepler-22 b")
        self.assertIsNone(result)

    @patch("lifesearch.data.pd.read_csv", side_effect=pd.errors.EmptyDataError("no data"))
    @patch("lifesearch.data.requests.get")
    def test_fetch_exoplanet_data_api_empty_data_error(self, mock_get, mock_read_csv):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = "pl_name\n"
        mock_get.return_value = mock_response
        result = fetch_exoplanet_data_api("Kepler-22 b")
        self.assertIsNone(result)

    @patch("lifesearch.data.requests.get", side_effect=RuntimeError("unexpected"))
    def test_fetch_exoplanet_data_api_unexpected_exception(self, mock_get):
        result = fetch_exoplanet_data_api("Kepler-22 b")
        self.assertIsNone(result)

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

    @patch("pandas.read_csv", side_effect=ValueError("bad format"))
    def test_load_hzgallery_catalog_generic_exception(self, mock_read_csv):
        """It should handle generic exceptions gracefully when loading HZGallery"""
        from lifesearch.data import load_hzgallery_catalog
        with self.assertLogs("lifesearch.data", level="ERROR") as cm:
            df = load_hzgallery_catalog("fake_path.csv")
            self.assertTrue(df.empty)
        self.assertTrue(any("Error loading HZGallery data" in m for m in cm.output))

    @patch('pandas.read_csv')
    def test_load_hwc_catalog_not_found(self, mock_read_csv):
        """It should return an empty DataFrame if HWC catalog file is not found"""
        mock_read_csv.side_effect = FileNotFoundError
        df = load_hwc_catalog("invalid")
        self.assertTrue(df.empty)

    @patch("pandas.read_csv", side_effect=ValueError("bad format"))
    def test_load_hwc_catalog_generic_exception(self, mock_read_csv):
        """It should handle generic exceptions gracefully when loading HWC"""
        from lifesearch.data import load_hwc_catalog
        with self.assertLogs("lifesearch.data", level="ERROR") as cm:
            df = load_hwc_catalog("fake_path.csv")
            self.assertTrue(df.empty)
        self.assertTrue(any("Error loading HWC data" in m for m in cm.output))

    @patch("json.load", side_effect=json.JSONDecodeError("msg", "doc", 0))
    def test_read_from_cache_jsondecodeerror(self, mock_json):
        """It should handle JSONDecodeError gracefully"""
        slug = "jsonerror"
        cache_file = os.path.join(self.temp_dir.name, f"{slug}.json")
        with open(cache_file, "w") as f:
            f.write("{}")
        with self.assertLogs("lifesearch.data", level="ERROR") as cm:
            result = read_from_cache(slug)
            self.assertIsNone(result)
        self.assertTrue(any("Error decoding JSON" in m for m in cm.output))


if __name__ == '__main__':
    unittest.main()