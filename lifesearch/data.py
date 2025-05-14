import pandas as pd
import requests
import logging
from io import StringIO
import os
import json
from datetime import datetime, timedelta
import re
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = "/home/ubuntu/lifesearch/cache"
CACHE_EXPIRATION_HOURS = 24  # Cache entries expire after 24 hours

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

ensure_dir(CACHE_DIR) # Ensure cache directory exists at startup

# --- NORMALIZE NAMES FOR COMPARISON ---
def normalize_name(name):
    normalized = str(name).lower().strip()
    normalized = re.sub(r'[^a-z0-9\s-]', '', normalized) # Keep spaces and hyphens
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

# --- CACHE HELPER FUNCTIONS ---
def get_cache_filepath(planet_name_slug):
    return os.path.join(CACHE_DIR, f"{planet_name_slug}.json")

def convert_numpy_types(data):
    if isinstance(data, pd.Series):
        data = data.to_dict()
    elif not isinstance(data, dict):
        logger.warning(f"convert_numpy_types received non-dict/non-Series data: {type(data)}")
        return data # Or raise error

    cleaned_data = {}
    for key, value in data.items():
        if pd.isna(value):  # Handles np.nan, pd.NaT, None
            cleaned_data[key] = None
        elif isinstance(value, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            cleaned_data[key] = int(value)
        elif isinstance(value, (np.floating, np.float64, np.float32, np.float16)):
            cleaned_data[key] = float(value)
        elif isinstance(value, np.bool_):
            cleaned_data[key] = bool(value)
        elif isinstance(value, pd.Timestamp):
            cleaned_data[key] = value.isoformat()
        elif isinstance(value, (list, dict)):
             # Potentially recurse if nested structures can contain numpy types
             # For now, assume shallow structures or that internal lists/dicts are clean
            cleaned_data[key] = value 
        else:
            cleaned_data[key] = value  # Assume it's already JSON serializable
    return cleaned_data

def write_to_cache(planet_name_slug, data_series):
    cache_file = get_cache_filepath(planet_name_slug)
    data_to_cache_dict = {}
    try:
        if isinstance(data_series, pd.Series):
            data_to_cache_dict = convert_numpy_types(data_series.to_dict())
        elif isinstance(data_series, dict):
            data_to_cache_dict = convert_numpy_types(data_series.copy())
        else:
            logger.error(f"Unsupported data type for caching for {planet_name_slug}: {type(data_series)}")
            return

        cache_content = {
            "timestamp": datetime.now().isoformat(),
            "data_dict": data_to_cache_dict
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_content, f, indent=4)
        logger.info(f"Data for {planet_name_slug} written to cache: {cache_file}")
    except Exception as e:
        problematic_data_str = "Error converting problematic_data to string"
        try:
            problematic_data_str = str(data_to_cache_dict if data_to_cache_dict else data_series)
        except:
            pass
        logger.error(f"Error writing to cache file {cache_file} for {planet_name_slug}: {e}. Problematic data snippet: {problematic_data_str[:500]}", exc_info=True)

def read_from_cache(planet_name_slug):
    cache_file = get_cache_filepath(planet_name_slug)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            timestamp_str = cached_data.get("timestamp")
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str)
                if datetime.now() - timestamp < timedelta(hours=CACHE_EXPIRATION_HOURS):
                    cached_data_dict = cached_data.get('data_dict')
                    if cached_data_dict is not None:
                        logger.info(f"Cache hit for {planet_name_slug}. Returning cached data as pd.Series.")
                        return pd.Series(cached_data_dict)
                    else:
                        logger.warning(f"Cache for {planet_name_slug} missing 'data_dict' key.")
                        return None
                else:
                    logger.info(f"Cache expired for {planet_name_slug}.")
            else:
                logger.warning(f"Cache found for {planet_name_slug} but no timestamp.")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from cache file: {cache_file}", exc_info=True)
        except Exception as e:
            logger.error(f"Error reading from cache file {cache_file}: {e}", exc_info=True)
    return None

# --- FETCH EXOPLANET DATA FROM NASA EXOPLANET ARCHIVE API (with Caching) ---
def fetch_exoplanet_data_api(planet_name):
    planet_name_slug = normalize_name(planet_name).replace(" ", "_").replace("-", "_")
    cached_data_series = read_from_cache(planet_name_slug)
    if cached_data_series is not None:
        return cached_data_series

    logger.info(f"Cache miss for {planet_name}. Fetching from API.")
    base_url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
    # Ensure planet_name in query is exact as expected by API, usually not normalized for query itself
    adql_query_string = f"select * from pscomppars where pl_name = '{planet_name}'"
    encoded_query = requests.utils.quote(adql_query_string)
    request_url = f"{base_url}?query={encoded_query}&format=csv"
    logger.info(f"Fetching data for {planet_name} from NASA Exoplanet Archive API: {request_url}")
    
    try:
        response = requests.get(request_url, timeout=30)
        response.raise_for_status()
        csv_data = response.text
        if not csv_data or csv_data.strip() == "" or "<!DOCTYPE html>" in csv_data.lower() or "ERROR" in csv_data[:200].upper():
            logger.warning(f"No valid data or error page returned for {planet_name} from API. Response snippet: {csv_data[:200]}")
            return None
            
        df = pd.read_csv(StringIO(csv_data))
        if df.empty:
            logger.warning(f"No data found for exoplanet: {planet_name} in the archive. Query: {adql_query_string}")
            return None
        
        data_series = df.iloc[0]
        logger.info(f"Successfully fetched data for {planet_name}.")
        write_to_cache(planet_name_slug, data_series.copy()) # Write a copy to cache
        return data_series
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred while fetching data for {planet_name}: {http_err} - URL: {request_url}")
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error occurred while fetching data for {planet_name}: {conn_err} - URL: {request_url}")
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error occurred while fetching data for {planet_name}: {timeout_err} - URL: {request_url}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"An error occurred during the request for {planet_name}: {req_err} - URL: {request_url}")
    except pd.errors.EmptyDataError:
        logger.warning(f"No columns to parse from API response for {planet_name}. Query: {adql_query_string}")
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching data for {planet_name}: {e} - URL: {request_url}", exc_info=True)
    return None

# --- LOAD AND CLEAN HWC DATA ---
def load_hwc_catalog(filepath="/home/ubuntu/lifesearch/data/hwc.csv"):
    try:
        df = pd.read_csv(filepath)
        logger.info(f"Loaded PHL @ UPR ARECIBO -> HWC DATA - {filepath} with {len(df)} planets")
        return df
    except FileNotFoundError:
        logger.error(f"HWC catalog file not found at {filepath}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading HWC data from {filepath}: {e}", exc_info=True)
        return pd.DataFrame()

# --- LOAD HZGALLERY DATA ---
def load_hzgallery_catalog(filepath="/home/ubuntu/lifesearch/data/table-hzgallery.csv"):
    try:
        df = pd.read_csv(filepath)
        logger.info(f"Loaded HABITABLE ZONE GALLERY (HZgallery) - {filepath} with {len(df)} planets")
        return df
    except FileNotFoundError:
        logger.error(f"HZGallery catalog file not found at {filepath}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading HZGallery data from {filepath}: {e}", exc_info=True)
        return pd.DataFrame()

# --- MERGE DATA SOURCES ---
def merge_data_sources(api_data, hwc_df=None, hz_gallery_df=None, planet_name_for_match=None, original_planet_name_query=None):
    logger.debug(f"Starting merge_data_sources for: {planet_name_for_match} (original query: {original_planet_name_query})")
    if api_data is not None:
        if isinstance(api_data, pd.Series):
            combined_data = api_data.to_dict()
            logger.debug(f"API data for {planet_name_for_match} (Series) converted to dict.")
        elif isinstance(api_data, dict):
            combined_data = api_data.copy()
            logger.debug(f"API data for {planet_name_for_match} is already a dict.")
        else:
            logger.warning(f"api_data for {planet_name_for_match} is of unexpected type: {type(api_data)}. Initializing empty dict.")
            combined_data = {}
    else:
        combined_data = {}
        logger.info(f"API data is None for {planet_name_for_match}. Starting with an empty dataset.")

    # Ensure pl_name is set, prioritize original query name if API name is missing
    if pd.isna(combined_data.get("pl_name")):
        name_to_set = original_planet_name_query if original_planet_name_query else planet_name_for_match
        if name_to_set:
            combined_data["pl_name"] = name_to_set
            logger.debug(f"pl_name was missing, set to: {name_to_set}")
        else:
            logger.warning(f"Cannot set pl_name for {planet_name_for_match} as both original and normalized names are missing.")

    # HWC Fallback and Augmentation
    if hwc_df is not None and not hwc_df.empty and planet_name_for_match:
        try:
            if 'P_NAME' in hwc_df.columns:
                hwc_df_copy = hwc_df.copy()
                hwc_df_copy['P_NAME_NORM'] = hwc_df_copy['P_NAME'].apply(lambda x: normalize_name(str(x)))
                hwc_planet_data_rows = hwc_df_copy[hwc_df_copy['P_NAME_NORM'] == planet_name_for_match]

                if not hwc_planet_data_rows.empty:
                    hwc_row = hwc_planet_data_rows.iloc[0]
                    logger.info(f"Found matching HWC data for {planet_name_for_match}.")
                    hwc_to_standard_map = {
                        'P_MASS': ('pl_masse', float),
                        'P_RADIUS': ('pl_rade', float),
                        'P_PERIOD': ('pl_orbper', float),
                        'P_SEMI_MAJOR_AXIS': ('pl_orbsmax', float),
                        'P_ECCENTRICITY': ('pl_orbeccen', float),
                        'P_SURFACE_TEMP_C': ('pl_eqt', lambda x: float(x) + 273.15 if pd.notna(x) and str(x).strip() != "" else None),
                        'P_ESI': ('pl_esi_hwc', lambda x: float(x) * 100 if pd.notna(x) and str(x).strip() != "" else None),
                        'S_AGE': ('st_age', float)
                    }
                    for hwc_key, (standard_key, converter) in hwc_to_standard_map.items():
                        if hwc_key in hwc_row and pd.notna(hwc_row[hwc_key]) and str(hwc_row[hwc_key]).strip() != "":
                            current_val_in_combined = combined_data.get(standard_key)
                            # Prioritize HWC ESI separately, for others, fill if missing in API data
                            if standard_key == 'pl_esi_hwc':
                                try:
                                    converted_value = converter(hwc_row[hwc_key])
                                    if pd.notna(converted_value):
                                        combined_data[standard_key] = converted_value
                                        logger.debug(f"Stored HWC ESI as '{standard_key}': {converted_value} for {planet_name_for_match}")
                                except Exception as e_conv:
                                    logger.warning(f"Could not convert HWC value for {hwc_key} ('{hwc_row[hwc_key]}') to {standard_key}: {e_conv}")
                            elif pd.isna(current_val_in_combined) or str(current_val_in_combined).strip() == "":
                                try:
                                    converted_value = converter(hwc_row[hwc_key])
                                    if pd.notna(converted_value):
                                        combined_data[standard_key] = converted_value
                                        logger.debug(f"Populated '{standard_key}' from HWC '{hwc_key}': {converted_value} for {planet_name_for_match}")
                                except Exception as e_conv:
                                    logger.warning(f"Could not convert HWC value for {hwc_key} ('{hwc_row[hwc_key]}') to {standard_key}: {e_conv}")
                    if 'P_HABITABLE' in hwc_row and pd.notna(hwc_row['P_HABITABLE']):
                        phi_raw = float(hwc_row['P_HABITABLE'])
                        if phi_raw == 0: combined_data['hwc_phi_category'] = 0.0
                        elif phi_raw == 1: combined_data['hwc_phi_category'] = 0.5
                        else: combined_data['hwc_phi_category'] = 1.0
                        logger.debug(f"Set 'hwc_phi_category' from HWC P_HABITABLE: {combined_data['hwc_phi_category']} for {planet_name_for_match}")
                else: logger.info(f"No matching HWC data found for {planet_name_for_match}.")
            else: logger.warning("P_NAME column not found in HWC data.")
        except Exception as e:
            logger.error(f"Error merging HWC data for {planet_name_for_match}: {e}", exc_info=True)

    # HZGallery Augmentation
    if hz_gallery_df is not None and not hz_gallery_df.empty and planet_name_for_match:
        try:
            if 'PLANET' in hz_gallery_df.columns:
                hz_df_copy = hz_gallery_df.copy()
                hz_df_copy['PLANET_NORM'] = hz_df_copy['PLANET'].apply(lambda x: normalize_name(str(x)))
                hz_planet_data_rows = hz_df_copy[hz_df_copy['PLANET_NORM'] == planet_name_for_match]
                if not hz_planet_data_rows.empty:
                    hz_row = hz_planet_data_rows.iloc[0]
                    logger.info(f"Found matching HZGallery data for {planet_name_for_match}.")
                    hz_mapping = {
                        'OHZIN': ('hz_ohzin', float), 'CHZIN': ('hz_chzin', float),
                        'CHZOUT': ('hz_chzout', float), 'OHZOUT': ('hz_ohzout', float),
                        'TEQA': ('hz_teqa', float) # HZGallery's Teq, pl_eqt is preferred
                    }
                    for hz_key, (standard_key, converter) in hz_mapping.items():
                        if hz_key in hz_row and pd.notna(hz_row[hz_key]) and str(hz_row[hz_key]).strip() != "":
                            if pd.isna(combined_data.get(standard_key)) or str(combined_data.get(standard_key)).strip() == "":
                                try:
                                    converted_value = converter(hz_row[hz_key])
                                    if pd.notna(converted_value):
                                        combined_data[standard_key] = converted_value
                                        logger.debug(f"Populated '{standard_key}' from HZGallery '{hz_key}': {converted_value} for {planet_name_for_match}")
                                except Exception as e_conv:
                                    logger.warning(f"Could not convert HZGallery value for {hz_key} ('{hz_row[hz_key]}') to {standard_key}: {e_conv}")
                else: logger.info(f"No matching HZGallery data found for {planet_name_for_match}.")
            else: logger.warning("PLANET column not found in HZGallery data.")
        except Exception as e:
            logger.error(f"Error merging HZGallery data for {planet_name_for_match}: {e}", exc_info=True)
    
    logger.debug(f"Final combined_data keys for {planet_name_for_match} after merge: {list(combined_data.keys())}")
    return combined_data

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(threadName)s - %(message)s')
    # Test Caching
    # test_series = pd.Series({'name': 'Test Planet', 'mass': np.float64(1.0), 'radius': 1, 'is_habitable': np.bool_(True), 'discovery_date': pd.Timestamp('2024-01-01')})
    # write_to_cache('test_planet_cache', test_series)
    # cached_s = read_from_cache('test_planet_cache')
    # print("Cached Series:\n", cached_s)

    # Test fetch and merge
    planet_name_to_test = "Kepler-452 b"
    print(f"\n--- Testing with {planet_name_to_test} ---")
    api_data_test = fetch_exoplanet_data_api(planet_name_to_test)
    if api_data_test is not None:
        print(f"API Data for {planet_name_to_test} (first 5 entries from Series):")
        print(api_data_test.head())
        hwc_test_df = load_hwc_catalog()
        hzg_test_df = load_hzgallery_catalog()
        merged_data_dict = merge_data_sources(api_data_test, hwc_test_df, hzg_test_df, normalize_name(planet_name_to_test), planet_name_to_test)
        print(f"\nMerged data for {planet_name_to_test} (dict sample):")
        for k, v in list(merged_data_dict.items())[:10]: # Print first 10 items
            print(f"  {k}: {v}")
        print(f"  pl_masse: {merged_data_dict.get('pl_masse')}")
        print(f"  pl_rade: {merged_data_dict.get('pl_rade')}")
        print(f"  pl_eqt: {merged_data_dict.get('pl_eqt')}")
        print(f"  pl_esi_hwc: {merged_data_dict.get('pl_esi_hwc')}")

    else:
        print(f"Failed to fetch API data for {planet_name_to_test}.")

