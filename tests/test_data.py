import pandas as pd
import numpy as np
import os
from lifesearch.data import (
    normalize_name,
    convert_numpy_types,
    write_to_cache,
    read_from_cache,
    merge_data_sources
)

def test_normalize_name_basic():
    """It should normalize planet names correctly"""
    assert normalize_name(" Kepler-22 b ") == "kepler22b"
    assert normalize_name(None) == ""
    assert normalize_name("Gliese–581 d") == "gliese581d"

def test_convert_numpy_types():
    """It should convert numpy types into native Python types"""
    data = {
        "int": np.int64(42),
        "float": np.float32(3.14),
        "bool": np.bool_(True),
        "nan": np.nan
    }
    converted = convert_numpy_types(data)
    assert isinstance(converted["int"], int)
    assert isinstance(converted["float"], float)
    assert isinstance(converted["bool"], bool)
    assert converted["nan"] is None

def test_cache_write_and_read(tmp_path=".tmp_cache"):
    """It should write to cache and read back the same values"""
    os.makedirs(tmp_path, exist_ok=True)

    from lifesearch import data
    data.CACHE_DIR = tmp_path  # usa pasta temporária para cache

    slug = "testplanet"
    series = pd.Series({"mass": 1.0, "radius": 1.0})

    write_to_cache(slug, series)
    read_series = read_from_cache(slug)

    assert isinstance(read_series, pd.Series)
    assert read_series["mass"] == 1.0
    assert read_series["radius"] == 1.0

def test_merge_data_sources_basic():
    """It should merge API, HWC and HZ data with correct priority"""
    api_data = pd.Series({"pl_name": "Kepler-22 b", "pl_masse": 10})
    hwc_df = pd.DataFrame([{"P_NAME": "Kepler-22 b", "P_MASS": 12}])
    hz_df = pd.DataFrame([{"PLANET": "Kepler-22 b", "OHZIN": 0.5}])

    combined = merge_data_sources(api_data, hwc_df, hz_df, "kepler22b")

    # O valor do API deve ter prioridade sobre o HWC
    assert combined["pl_masse"] == 10
    # Deve incluir dados da HZ
    assert "hz_ohzin" in combined
