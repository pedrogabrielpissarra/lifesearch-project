import pandas as pd
import numpy as np
import logging
import math

logger = logging.getLogger(__name__)

# --- Helper Functions ---
def get_color_for_percentage(value, high_is_good=True):
    """Determines a hex color code based on a percentage value.
    
    Args:
        value (float or None): The percentage value (0-100).
        high_is_good (bool): True if higher values are better, False if lower values are better.
    
    Returns:
        str: Hex color code string. Grey for N/A or invalid values.
    """
    if pd.isna(value) or value is None:
        return "#757575"  # Grey for N/A
    try:
        value = float(value)
    except (ValueError, TypeError): # pragma: no cover
        return "#757575" # pragma: no cover
        
    if high_is_good:
        if value >= 80:
            return "#4CAF50"  # Green
        elif value >= 60:
            return "#8BC34A"  # Light Green
        elif value >= 40:
            return "#FFC107"  # Amber
        elif value >= 20:
            return "#FF9800"  # Orange
        else:
            return "#F44336"  # Red
    else: # Low is good
        if value <= 10:
            return "#4CAF50"
        elif value <= 25:
            return "#8BC34A"
        elif value <= 50:
            return "#FFC107"
        elif value <= 75:
            return "#FF9800"
        else:
            return "#F44336"

def format_value(value, precision=2, default_na="N/A"):
    """Helper to format numerical values or return N/A."""
    if pd.isna(value) or value is None:
        return default_na
    try:
        return f"{float(value):.{precision}f}"
    except (ValueError, TypeError):
        logger.debug(f"format_value: Could not convert {value} to float.")
        return default_na

def calculate_travel_times(distance_ly):
    """Calculates estimated travel times to a celestial body at various speeds.
    
    Args:
        distance_ly (float or None): The distance to the celestial body in light-years.
    
    Returns:
        dict: A dictionary containing travel time scenarios and their estimated durations.
              Returns "N/A" for times if distance is invalid.
    """
    logger.debug(f"Calculating travel times for distance: {distance_ly} ly")
    travel_info = {
        "scenario_1_label": "Current tech (~0.0057% c)", "scenario_1_time": "N/A",
        "scenario_2_label": "20% speed of light", "scenario_2_time": "N/A",
        "scenario_3_label": "Near light speed (0.9999c)", "scenario_3_time": "N/A"
    }
    if pd.isna(distance_ly) or not isinstance(distance_ly, (int, float)) or distance_ly <= 0:
        logger.debug("Travel times: Distance is N/A or invalid.")
        return travel_info
    
    speeds = {
        "Current tech (~0.0057% c)": 0.000057,
        "20% speed of light": 0.20,
        "Near light speed (0.9999c)": 0.9999
    }
    i = 1
    for label, v_c in speeds.items():
        if v_c > 0:
            time_years = distance_ly / v_c
            travel_info[f"scenario_{i}_time"] = f"{time_years:.1f} years"
            logger.debug(f"Travel time for {label}: {travel_info[f'scenario_{i}_time']}")
        i += 1
    return travel_info

def classify_planet(mass_earth, radius_earth, temp_k):
    """Classifies a planet based on its mass, radius, and temperature.
    
    Estimates mass from radius if mass is missing, using simplified power laws.
    Assigns a mass class (e.g., Terran, Jovian) and a temperature class
    (e.g., Mesoplanet, Psychroplanet).
    
    Args:
        mass_earth (float or None): Planet's mass in Earth masses.
        radius_earth (float or None): Planet's radius in Earth radii.
        temp_k (float or None): Planet's equilibrium temperature in Kelvin.
    
    Returns:
        str: A string combining the mass class and temperature class.
    """
    logger.debug(f"Classifying planet with Mass: {mass_earth}, Radius: {radius_earth}, Temp: {temp_k}")
    # Estimate mass from radius if mass is missing (simplified)
    if pd.isna(mass_earth) and pd.notna(radius_earth) and radius_earth > 0:
        if radius_earth < 1.5: # Rocky
            mass_earth = (radius_earth / 1.0)**(1/0.3) # Simplified from R ~ M^0.3
            logger.debug(f"Estimated mass for rocky planet: {mass_earth}")
        else: # Gaseous
            mass_earth = (radius_earth / 1.0)**(1/0.5) # Simplified from R ~ M^0.5
            logger.debug(f"Estimated mass for gaseous planet: {mass_earth}")
    
    if pd.isna(mass_earth) or mass_earth <= 0:
        mass_class = "Unknown Mass Class"
    elif mass_earth < 0.00001: mass_class = "Asteroidan"
    elif mass_earth < 0.1: mass_class = "Mercurian"
    elif mass_earth < 0.5: mass_class = "Subterran"
    elif mass_earth < 2: mass_class = "Terran"
    elif mass_earth < 10: mass_class = "Superterran"
    elif mass_earth < 50: mass_class = "Neptunian"
    elif mass_earth < 5000: mass_class = "Jovian"
    else: mass_class = "Unknown Mass Class" # pragma: no cover
    logger.debug(f"Mass class: {mass_class}")

    if pd.isna(temp_k) or temp_k < 0:
        temp_class = "Unknown Temperature Class"
    elif temp_k < 170: temp_class = "Hypopsychroplanet (Very Cold)" 
    elif temp_k < 220: temp_class = "Psychroplanet (Cold)"
    elif temp_k < 273: temp_class = "Mesoplanet (Temperate 1)"
    elif temp_k < 323: temp_class = "Mesoplanet (Temperate 2 - Optimal for Earth Life)"
    elif temp_k < 373: temp_class = "Thermoplanet (Warm)" # pragma: no cover
    else: temp_class = "Hyperthermoplanet (Hot)" # pragma: no cover
    logger.debug(f"Temperature class: {temp_class}")
    
    final_classification = f"{mass_class} | {temp_class}"
    logger.debug(f"Final classification: {final_classification}")
    return final_classification

# --- SEPHI Calculation  ---
def calculate_sephi(planet_mass, planet_radius, orbital_period, stellar_mass, stellar_radius, stellar_teff, system_age, planet_density_val, planet_name_for_log):
    """Calculates the Standard Exoplanet Habitability Index (SEPHI) and its components.
    
    SEPHI is based on four components (L1-L4) representing factors like
    surface conditions, escape velocity, habitable zone position, and potential
    for a magnetic field.
    
    Args:
        planet_mass (float or None): Planet mass in Earth masses.
        planet_radius (float or None): Planet radius in Earth radii.
        orbital_period (float or None): Planet orbital period in days.
        stellar_mass (float or None): Host star mass in Solar masses.
        stellar_radius (float or None): Host star radius in Solar radii.
        stellar_teff (float or None): Host star effective temperature in Kelvin.
        system_age (float or None): System age in Gyr.
        planet_density_val (float or None): Planet density in g/cm^3.
        planet_name_for_log (str): Name of the planet for logging purposes.
    
    Returns:
        tuple: (SEPHI_score, L1, L2, L3, L4) all as percentages, or
               (None, None, None, None, None) if core parameters are missing/invalid.
    """
    logger.debug(f"Calculating SEPHI for {planet_name_for_log} with inputs: pm={planet_mass}, pr={planet_radius}, po={orbital_period}, sm={stellar_mass}, sr={stellar_radius}, st={stellar_teff}, sa={system_age}, pdens={planet_density_val}")
    params_to_check = [planet_mass, planet_radius, orbital_period, stellar_mass, stellar_radius, stellar_teff, system_age]
    param_names = ["pl_masse", "pl_rade", "pl_orbper", "st_mass", "st_rad", "st_teff", "st_age"]
    converted_params = {}
    for name, p_val in zip(param_names, params_to_check):
        if isinstance(p_val, str) and p_val.strip() == "": converted_params[name] = None
        else:
            try: converted_params[name] = float(p_val) if p_val is not None and not pd.isna(p_val) else None
            except ValueError: converted_params[name] = None # pragma: no cover
    
    pm, pr, po, sm, sr, st, sa = (converted_params["pl_masse"], converted_params["pl_rade"], converted_params["pl_orbper"], 
                                   converted_params["st_mass"], converted_params["st_rad"], converted_params["st_teff"], converted_params["st_age"])
    pdens = float(planet_density_val) if planet_density_val is not None and not pd.isna(planet_density_val) else None
    logger.debug(f"SEPHI Converted Params: pm={pm}, pr={pr}, po={po}, sm={sm}, sr={sr}, st={st}, sa={sa}, pdens={pdens}")

    if any(p is None for p in [pm, pr, po, sm, sr, st, sa]):
        logger.warning(f"SEPHI calculation skipped for {planet_name_for_log} due to missing core parameters after conversion.")
        return None, None, None, None, None
    # Check for non-positive after ensuring not None
    non_positive_check = [p for p in [pm, pr, po, sm, sr, st, sa] if p is not None and p <= 0]
    if non_positive_check:
        logger.warning(f"SEPHI calculation skipped for {planet_name_for_log} due to non-positive core parameters: {non_positive_check}")
        return None, None, None, None, None

    mu_1_mp = pm ** 0.27
    mu_2_mp = pm ** 0.5
    sigma_1_mp = (mu_2_mp - mu_1_mp) / 3 if (mu_2_mp - mu_1_mp) != 0 else 0.1
    if sigma_1_mp == 0: sigma_1_mp = 0.1 # Avoid division by zero
    if pr <= mu_1_mp: L1 = 1.0
    elif mu_1_mp < pr < mu_2_mp: L1 = math.exp(-0.5 * ((pr - mu_1_mp) / sigma_1_mp) ** 2)
    else: L1 = 0.0 # pragma: no cover

    earth_mass_ref, earth_radius_ref = 1.0, 1.0 # Earth units
    earth_g = earth_mass_ref / (earth_radius_ref ** 2)
    earth_v_e = math.sqrt(earth_g * earth_radius_ref)
    planet_g = pm / (pr ** 2)
    v_e = math.sqrt(planet_g * pr)
    v_e_relative = v_e / earth_v_e if earth_v_e > 0 else 0
    sigma_21, sigma_22 = (1.0 - 0.0) / 3, (8.66 - 1.0) / 3 # Assuming sigma can"t be zero
    if sigma_21 == 0: sigma_21 = 0.1
    if sigma_22 == 0: sigma_22 = 0.1
    if v_e_relative < 1.0: L2 = math.exp(-0.5 * ((v_e_relative - 1.0) / sigma_21) ** 2)
    else: L2 = math.exp(-0.5 * ((v_e_relative - 1.0) / sigma_22) ** 2)
    
    solar_teff_ref = 5778 # K
    stellar_luminosity = (sr ** 2) * ((st / solar_teff_ref) ** 4) # L_star / L_sun
    G_const, solar_mass_kg_ref = 6.67430e-11, 1.989e30
    stellar_mass_kg = sm * solar_mass_kg_ref
    orbital_period_seconds = po * 86400
    a_meters = ((G_const * stellar_mass_kg * (orbital_period_seconds ** 2)) / (4 * math.pi ** 2)) ** (1/3)
    au_per_meter_val = 6.68459e-12
    semi_major_axis = a_meters * au_per_meter_val # in AU
    t_eff_diff = st - 5780
    s_eff_sun_rv, a_rv, b_rv, c_rv, d_rv = 1.766, 1.335e-4, 3.151e-9, -3.348e-12, 5.733e-16
    s_eff_rv = s_eff_sun_rv + a_rv*t_eff_diff + b_rv*(t_eff_diff**2) + c_rv*(t_eff_diff**3) + d_rv*(t_eff_diff**4)
    d1 = math.sqrt(stellar_luminosity / s_eff_rv) * 0.68 if s_eff_rv > 0 else 0
    s_eff_sun_rg, a_rg, b_rg, c_rg, d_rg = 1.038, 1.246e-4, 2.874e-9, -3.06e-12, 5.279e-16
    s_eff_rg = s_eff_sun_rg + a_rg*t_eff_diff + b_rg*(t_eff_diff**2) + c_rg*(t_eff_diff**3) + d_rg*(t_eff_diff**4)
    d2_hz = math.sqrt(stellar_luminosity / s_eff_rg) if s_eff_rg > 0 else 0
    s_eff_sun_mg, a_mg, b_mg, c_mg, d_mg = 0.3438, 5.894e-5, 1.628e-9, -1.698e-12, 2.92e-16
    s_eff_mg = s_eff_sun_mg + a_mg*t_eff_diff + b_mg*(t_eff_diff**2) + c_mg*(t_eff_diff**3) + d_mg*(t_eff_diff**4)
    d3_hz = math.sqrt(stellar_luminosity / s_eff_mg) if s_eff_mg > 0 else 0
    s_eff_sun_em, a_em, b_em, c_em, d_em = 0.3179, 5.451e-5, 1.526e-9, -1.598e-12, 2.747e-16
    s_eff_em = s_eff_sun_em + a_em*t_eff_diff + b_em*(t_eff_diff**2) + c_em*(t_eff_diff**3) + d_em*(t_eff_diff**4)
    d4 = math.sqrt(stellar_luminosity / s_eff_em) * 1.35 if s_eff_em > 0 else 0
    mu_31, sigma_31 = d2_hz, (d2_hz - d1) / 3 if (d2_hz - d1) != 0 else 0.1
    mu_32, sigma_32 = d3_hz, (d4 - d3_hz) / 3 if (d4 - d3_hz) != 0 else 0.1
    if sigma_31 == 0: sigma_31 = 0.1
    if sigma_32 == 0: sigma_32 = 0.1
    if d2_hz <= semi_major_axis <= d3_hz: L3 = 1.0
    elif semi_major_axis < d2_hz: L3 = 0.0 if semi_major_axis < d1 else math.exp(-0.5 * ((semi_major_axis - mu_31) / sigma_31) ** 2)
    else: L3 = 0.0 if semi_major_axis > d4 else math.exp(-0.5 * ((semi_major_axis - mu_32) / sigma_32) ** 2)

    earth_density_ref = 5.51 # g/cm^3
    planet_density_actual = pdens if pdens is not None else (earth_density_ref * (pm / (pr ** 3)) if pr > 0 and pm is not None else earth_density_ref)
    t_gyr_norm = sa / 10.0 if sa is not None else 0.5 # Assuming 0.5 if age is unknown
    a_lock = (sm ** (1/3)) * ((planet_density_actual / earth_density_ref) ** (-1/3)) * (t_gyr_norm ** (1/6)) * 0.06 if earth_density_ref > 0 else 0
    is_tidally_locked = semi_major_axis <= a_lock
    beta_1_val = pr
    if L1 > 0.5:
        rho_0n, r_0n, F_n = 1.0, beta_1_val, beta_1_val
        alpha_val = 0.05 if is_tidally_locked else 1.0
    else:
        if pr <= 5.0: rho_0n, r_0n, F_n = 0.45, 1.8 * beta_1_val, 4 * beta_1_val
        elif pr <= 15.0: rho_0n, r_0n, F_n = 0.18, 4.8 * beta_1_val, 20 * beta_1_val
        else: rho_0n, r_0n, F_n = 0.16, 16 * beta_1_val, 100 * beta_1_val # pragma: no cover
        alpha_val = 1.0
    M_n_val = alpha_val * (rho_0n ** 0.5) * (r_0n ** (10/3)) * (F_n ** (1/3))
    mu_4, sigma_4 = 1.0, (1.0 - 0.0) / 3
    if sigma_4 == 0: sigma_4 = 0.1
    L4 = 1.0 if M_n_val >= 1.0 else math.exp(-0.5 * ((M_n_val - mu_4) / sigma_4) ** 2)

    sephi_val = (L1 * L2 * L3 * L4) ** (1/4) if L1*L2*L3*L4 > 0 else 0.0
    logger.info(f"SEPHI for {planet_name_for_log}: {sephi_val*100:.2f} (L1:{L1*100:.1f}, L2:{L2*100:.1f}, L3:{L3*100:.1f}, L4:{L4*100:.1f})")
    return sephi_val * 100, L1 * 100, L2 * 100, L3 * 100, L4 * 100

# --- Core Calculation Functions ---
def calculate_esi_score(planet_data, weights):
    """Calculates the Earth Similarity Index (ESI) for a planet.

    The ESI is derived directly from user-defined slider weights for
    radius, density, and equilibrium temperature.

    Args:
        planet_data (dict): Dictionary containing planet parameters like
                            'pl_rade', 'pl_dens', 'pl_eqt'.
        weights (dict): Dictionary of weights for 'Size', 'Density',
                        and 'Habitable Zone' (temperature). Each weight
                        ranges from 0.0 to 1.0 and directly contributes
                        to the ESI.

    Returns:
        tuple: (float ESI_score (0-100), str color_code_for_ESI).
               Returns 0.0 if no valid components are found.
    """
    logger.debug(f"Calculating ESI for planet: {planet_data.get('pl_name', 'Unknown')}")
    esi_factors_map = {
        "pl_rade": weights.get("Size", 0.0),
        "pl_dens": weights.get("Density", 0.0),
        "pl_eqt": weights.get("Habitable Zone", 0.0)
    }

    esi_components = []
    num_params = 0

    # Cada peso do slider é usado diretamente como componente do ESI
    for param_key, weight_val in esi_factors_map.items():
        logger.debug(f"ESI param: {param_key}, Weight: {weight_val}")
        esi_components.append(weight_val)
        num_params += 1
        logger.debug(f"ESI component for {param_key}: {weight_val}")

    if not esi_components or num_params == 0:
        logger.warning("Nenhum componente ESI válido encontrado.")
        return 0.0, get_color_for_percentage(0.0)

    final_esi = (sum(esi_components) / num_params) * 100
    logger.info(f"ESI final para {planet_data.get('pl_name', 'Unknown')}: {final_esi}")

    return round(final_esi, 2), get_color_for_percentage(final_esi)

def calculate_sph_score(planet_data, weights):
    """Calculates the Standard Primary Habitability (SPH) score for a planet.
    
    The SPH is primarily based on the planet's equilibrium temperature (pl_eqt)
    and its suitability for Earth-like life (water in liquid state).
    The 'weights' argument is present for consistency but not directly used
    in the current SPH calculation logic.
    
    Args:
        planet_data (dict): Dictionary containing planet parameters,
                            especially 'pl_eqt' (equilibrium temperature in K).
        weights (dict): (Currently unused by this function but kept for API consistency).
    
    Returns:
        tuple: (float SPH_score (0-100), str color_code_for_SPH).
               Returns 0.0 if temperature is N/A.
    """
    logger.debug(f"Calculating SPH for planet: {planet_data.get('pl_name', 'Unknown')}")
    temp_k = planet_data.get("pl_eqt")
    score = 0.0
    if pd.notna(temp_k):
        try:
            temp_k_fl = float(temp_k)
            logger.debug(f"SPH temp_k_fl: {temp_k_fl}")
            if 273.15 <= temp_k_fl <= 323.15:
                mid_optimal = (273.15 + 323.15) / 2
                score = 70 + (1 - abs(temp_k_fl - mid_optimal) / (mid_optimal - 273.15)) * 30
            elif (250 <= temp_k_fl < 273.15) or (323.15 < temp_k_fl <= 373.15):
                score = 40
            else: score = 10
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not convert SPH temp_k to float: {temp_k}. Error: {e}")
            return 0.0, get_color_for_percentage(0.0)
    else:
        logger.debug("SPH temp_k is N/A.")
        return 0.0, get_color_for_percentage(0.0)
    final_sph = max(0, min(score, 100))
    logger.info(f"Final SPH for {planet_data.get('pl_name', 'Unknown')}: {final_sph}")
    return round(final_sph, 2), get_color_for_percentage(final_sph)

def calculate_phi_score(planet_data, phi_weights):
    """Calculates a Planetary Habitability Index (PHI) score.

    Each PHI factor ("Solid Surface", "Stable Energy", "Life Compounds",
    "Stable Orbit") is represented directly by a slider weight in
    ``phi_weights``. The average of these weights is scaled to a
    percentage.

    Args:
        planet_data (dict): Dictionary containing planet and star parameters.
                           Currently unused but kept for API consistency.
        phi_weights (dict): Dictionary of weights for PHI factors. Each weight
                            ranges from 0.0 to 0.25.

    Returns:
        tuple: (float PHI_score (0-100), str color_code_for_PHI).
               Returns 0.0 if no valid components are found.
    """
    logger.debug(f"Calculating PHI for planet: {planet_data.get('pl_name', 'Unknown')}")

    phi_components = []
    expected_factors = ["Solid Surface", "Stable Energy", "Life Compounds", "Stable Orbit"]

    for factor_name in expected_factors:
        weight_val = phi_weights.get(factor_name, 0.0)
        logger.debug(f"Processando fator PHI: {factor_name}, peso: {weight_val}")
        phi_components.append(weight_val)

    if not phi_components:
        logger.warning("Nenhum componente PHI válido encontrado.")
        return 0.0, get_color_for_percentage(0.0)

    final_phi = (sum(phi_components) / len(phi_components)) * 400
    final_phi = max(0.0, min(final_phi, 100.0))

    logger.info(f"PHI final para {planet_data.get('pl_name', 'Unknown')}: {final_phi}")

    return round(final_phi, 2), get_color_for_percentage(final_phi)


def sliders_phi(planet_data):
    """Calcula os pesos iniciais para os sliders de PHI.

    Args:
        planet_data (dict): Dicionário contendo dados do planeta.

    Returns:
        dict: Dicionário com pesos iniciais para os sliders de PHI.
    """
    phi_factors = {
        "Solid Surface": 0.0,
        "Stable Energy": 0.0,
        "Life Compounds": 0.0,
        "Stable Orbit": 0.0
    }

    # Avaliação automática de "Solid Surface"
    if "Terran" in planet_data.get("classification", "") or "Superterran" in planet_data.get("classification", ""):
        phi_factors["Solid Surface"] = 0.8

    # Avaliação automática de "Stable Energy"
    st_spectype = planet_data.get("st_spectype", "")
    st_age = planet_data.get("st_age")
    if isinstance(st_spectype, str) and (st_spectype.startswith("G") or st_spectype.startswith("K")) and pd.notna(st_age):
        try:
            st_age_float = float(st_age.strip()) if isinstance(st_age, str) else float(st_age)
            if 1.0 < st_age_float < 8.0:
                phi_factors["Stable Energy"] = 0.7
        except (ValueError, TypeError, AttributeError):
            pass

    # Avaliação automática de "Stable Orbit"
    pl_orbeccen = planet_data.get("pl_orbeccen")
    if pd.notna(pl_orbeccen):
        try:
            pl_orbeccen_float = float(pl_orbeccen.strip()) if isinstance(pl_orbeccen, str) else float(pl_orbeccen)
            if pl_orbeccen_float < 0.2:
                phi_factors["Stable Orbit"] = 0.9
        except (ValueError, TypeError, AttributeError):
            pass

    # Converter os fatores base para a faixa de 0.0 a 0.25 para os sliders
    initial_phi_weights = {}
    for factor_name, factor_score in phi_factors.items():
        initial_phi_weights[factor_name] = factor_score * 0.25

    return initial_phi_weights


def reference_values_slider(planet_data):
    """Calcula valores de referência para ESI e PHI.

    Args:
        planet_data (dict): Dicionário contendo dados do planeta.

    Returns:
        tuple: (esi_val, phi_val) como percentuais.
    """
    earth_params = {"pl_rade": 1.0, "pl_dens": 5.51, "pl_eqt": 255.0}
    esi_similarities = []

    for param_key, earth_val in earth_params.items():
        planet_val = planet_data.get(param_key)
        if pd.notna(planet_val) and pd.notna(earth_val) and earth_val != 0:
            try:
                planet_val_fl = float(planet_val)
                earth_val_fl = float(earth_val)
                similarity = 1.0 - abs((planet_val_fl - earth_val_fl) / (planet_val_fl + earth_val_fl))
                if similarity < 0:
                    similarity = 0.0
                esi_similarities.append(similarity)
            except (ValueError, TypeError):
                pass

    esi_val = 0.0
    if esi_similarities:
        esi_val = (sum(esi_similarities) / len(esi_similarities)) * 100

    initial_phi_weights = sliders_phi(planet_data)
    phi_components = list(initial_phi_weights.values())
    phi_val = 0.0
    if phi_components:
        phi_val = (sum(phi_components) / len(phi_components)) * 400
        phi_val = max(0.0, min(phi_val, 100.0))

    return round(esi_val, 2), round(phi_val, 2)

# --- Habiitability Score Calculation Function - Lifersearch Project ---
def calculate_detailed_habitability_scores(planet_data_dict, hz_data_tuple, weights_config):
    """Calculates a dictionary of detailed habitability scores for a planet.
    
    Scores cover aspects like Size, Density, Mass, Atmosphere Potential,
    Liquid Water Potential, Habitable Zone Position, Host Star Type,
    System Age, Star Metallicity, and Orbital Eccentricity.
    The 'weights_config' argument is present for consistency but not
    directly used for individual score calculations here.
    
    Args:
        planet_data_dict (dict): Dictionary of planet and stellar parameters.
        hz_data_tuple (tuple): Tuple containing habitable zone boundaries
                               (ohz_in, chz_in, chz_out, ohz_out, teqa) or None.
        weights_config (dict): (Currently unused by this function but kept for API consistency).
    
    Returns:
        dict: A dictionary where keys are score names (e.g., "Size") and
              values are tuples of (score_value, color_code).
    """
    logger.debug(f"Calculating detailed scores for: {planet_data_dict.get('pl_name', 'Unknown')}")
    scores = {}
    def to_float_or_none(val):
        if pd.isna(val) or val is None: return None
        try: return float(val)
        except (ValueError, TypeError): # pragma: no cover
            logger.debug(f"Detailed scores: Could not convert {val} to float.") # pragma: no cover
            return None # pragma: no cover

    radius = to_float_or_none(planet_data_dict.get("pl_rade"))
    mass = to_float_or_none(planet_data_dict.get("pl_masse"))
    density = to_float_or_none(planet_data_dict.get("pl_dens"))
    temp_eq = to_float_or_none(planet_data_dict.get("pl_eqt"))
    classification = planet_data_dict.get("classification", "Unknown")
    orbit_dist_au = to_float_or_none(planet_data_dict.get("pl_orbsmax"))
    st_lum_log = to_float_or_none(planet_data_dict.get("st_lum"))
    st_spectype = planet_data_dict.get("st_spectype", "")
    st_age_gyr = to_float_or_none(planet_data_dict.get("st_age"))
    st_met_dex = to_float_or_none(planet_data_dict.get("st_met"))
    pl_orbeccen_val = to_float_or_none(planet_data_dict.get("pl_orbeccen"))
    logger.debug(f"Detailed scores inputs: r={radius}, m={mass}, d={density}, T={temp_eq}, class={classification}, orb_dist={orbit_dist_au}, lum={st_lum_log}, spec={st_spectype}, age={st_age_gyr}, met={st_met_dex}, ecc={pl_orbeccen_val}")

    score_val = 0
    if radius is not None:
        if "Terran" in classification and 0.8 <= radius <= 1.5: score_val = 100
        elif (("Mini-Terran" in classification or "Subterran" in classification) and 0.5 <= radius < 0.8) or \
             ("Terran" in classification and 1.5 < radius <= 2.0) or \
             ("Superterran" in classification and radius <= 2.5): score_val = 90
        elif ("Superterran" in classification and 2.5 < radius <= 4.5) or \
             ("Neptunian" in classification and radius <= 5.0): score_val = 70
        else: score_val = 30
    scores["Size"] = (score_val, get_color_for_percentage(score_val)); logger.debug(f"Size score: {scores['Size']}")

    score_val = 0
    if density is not None:
        if "Terran" in classification and 4.5 <= density <= 6.5: score_val = 100
        elif (
            (("Terran" in classification or "Superterran" in classification) and (3.0 <= density < 4.5)) or
            (("Terran" in classification or "Superterran" in classification) and (6.5 < density <= 8.0))
        ): score_val = 90
        elif (("Mini-Terran" in classification or "Subterran" in classification or "Superterran" in classification) and (density < 3.0 or density > 8.0)): score_val = 70
        else: score_val = 50
    scores["Density"] = (score_val, get_color_for_percentage(score_val)); logger.debug(f"Density score: {scores['Density']}")

    score_val = 0
    if mass is not None:
        if "Terran" in classification and 0.8 <= mass <= 1.5: score_val = 100
        elif (("Mini-Terran" in classification or "Subterran" in classification) and 0.1 <= mass < 0.8) or \
             ("Terran" in classification and 1.5 < mass <= 2.0) or \
             ("Superterran" in classification and mass <= 5.0): score_val = 90
        elif ("Superterran" in classification and 5.0 < mass <= 10.0) or \
             ("Neptunian" in classification and mass <= 20.0): score_val = 70
        else: score_val = 30
    scores["Mass"] = (score_val, get_color_for_percentage(score_val)); logger.debug(f"Mass score: {scores['Mass']}")

    atm_score, water_score = 0, 0
    if temp_eq is not None:
        if 273.15 < temp_eq <= 373.15: atm_score, water_score = 90, 90
        elif (200 <= temp_eq <= 273.15) or (373.15 < temp_eq <= 450): atm_score, water_score = 50, 50
        else: atm_score, water_score = 20, 20
    scores["Atmosphere Potential"] = (atm_score, get_color_for_percentage(atm_score)); logger.debug(f"Atmosphere score: {scores['Atmosphere Potential']}")
    scores["Liquid Water Potential"] = (water_score, get_color_for_percentage(water_score)); logger.debug(f"Water score: {scores['Liquid Water Potential']}")

    hz_score = 0
    if hz_data_tuple and len(hz_data_tuple) == 5 and orbit_dist_au is not None:
        ohz_in, chz_in, chz_out, ohz_out, _ = map(to_float_or_none, hz_data_tuple)
        if all(v is not None for v in [ohz_in, chz_in, chz_out, ohz_out]):
            if chz_in <= orbit_dist_au <= chz_out: hz_score = 95
            elif ohz_in <= orbit_dist_au < chz_in or chz_out < orbit_dist_au <= ohz_out: hz_score = 65 # pragma: no cover
            else: hz_score = 20 # pragma: no cover
        else: hz_score = 15
    elif st_lum_log is not None and orbit_dist_au is not None:
        lum_linear = 10**st_lum_log
        hz_in_calc = math.sqrt(lum_linear / 1.1)
        hz_out_calc = math.sqrt(lum_linear / 0.53)
        if hz_in_calc <= orbit_dist_au <= hz_out_calc: hz_score = 80
        else: hz_score = 25
    else: hz_score = 10
    scores["Habitable Zone Position"] = (hz_score, get_color_for_percentage(hz_score)); logger.debug(f"HZ Position score: {scores['Habitable Zone Position']}")

    star_score = 0
    if isinstance(st_spectype, str) and st_spectype:
        if st_spectype.startswith("G"): star_score = 95
        elif st_spectype.startswith("K"): star_score = 85
        elif st_spectype.startswith("F"): star_score = 70
        elif st_spectype.startswith("M"): star_score = 60
        else: star_score = 30
    scores["Host Star Type"] = (star_score, get_color_for_percentage(star_score)); logger.debug(f"Star Type score: {scores['Host Star Type']}")

    age_score = 0
    if st_age_gyr is not None:
        if 1.0 <= st_age_gyr <= 8.0: age_score = 90
        elif 0.5 <= st_age_gyr < 1.0 or 8.0 < st_age_gyr <= 10.0: age_score = 60
        else: age_score = 30
    scores["System Age"] = (age_score, get_color_for_percentage(age_score)); logger.debug(f"System Age score: {scores['System Age']}")
    
    met_score = 0
    if st_met_dex is not None:
        if -0.5 <= st_met_dex <= 0.5 : met_score = 90
        elif -1.0 <= st_met_dex < -0.5 or 0.5 < st_met_dex <= 1.0: met_score = 60
        else: met_score = 30
    scores["Star Metallicity"] = (met_score, get_color_for_percentage(met_score)); logger.debug(f"Metallicity score: {scores['Star Metallicity']}")

    ecc_score = 0
    if pl_orbeccen_val is not None:
        if pl_orbeccen_val <= 0.1: ecc_score = 95
        elif pl_orbeccen_val <= 0.3: ecc_score = 70
        elif pl_orbeccen_val <= 0.5: ecc_score = 40
        else: ecc_score = 10
    scores["Orbital Eccentricity"] = (ecc_score, get_color_for_percentage(ecc_score, high_is_good=False)); logger.debug(f"Eccentricity score: {scores['Orbital Eccentricity']}")
    logger.debug(f"All detailed scores calculated: {scores}")
    return scores

# --- Main Data Processing Function ---
def process_planet_data(planet_name, combined_data, weights_config):
    """Processes raw planet data to calculate various metrics and prepare for reporting.
    
    This function orchestrates calls to:
    - classify_planet
    - calculate_travel_times
    - calculate_esi_score, calculate_sph_score, calculate_phi_score
    - calculate_detailed_habitability_scores
    - calculate_sephi
    It also formats data for display (e.g., star info, orbit info).
    
    Args:
        planet_name (str): The name of the planet.
        combined_data (pd.Series or dict): Combined data for the planet from various sources.
        weights_config (dict): Configuration for weights used in ESI, SPH, PHI calculations.
    
    Returns:
        dict: A comprehensive dictionary containing:
              - "planet_data_dict": The processed and enriched planet data.
              - "scores_for_report": Main habitability scores (ESI, SPH, PHI, detailed).
              - "sephi_scores_for_report": SEPHI scores.
              - "hz_data_tuple": Habitable zone data.
              - "star_data_for_plot": Data for plotting star information.
              - "classification_display": Planet classification string.
              - "travel_curiosities": Travel time estimations.
              - "star_info": Formatted stellar parameters.
              - "orbit_info": Formatted orbital parameters.
    """
    logger.info(f"Processing data for planet: {planet_name}")
    logger.debug(f"Initial combined_data for {planet_name}:\n{combined_data}")

    # Conditional conversion to dict
    if hasattr(combined_data, 'to_dict'):
        planet_data_dict = combined_data.to_dict()
        logger.debug(f"Converted combined_data (Series) to dict for {planet_name}.")
    elif isinstance(combined_data, dict):
        planet_data_dict = combined_data.copy()
        logger.debug(f"Copied combined_data (already dict) for {planet_name}.")
    else:
        logger.warning(f"Unexpected type for combined_data: {type(combined_data)} for {planet_name}. Proceeding with an empty dict.")
        planet_data_dict = {}

    logger.debug(f"Type of planet_data_dict for {planet_name}: {type(planet_data_dict)}")
    logger.debug(f"Keys in planet_data_dict for {planet_name}: {list(planet_data_dict.keys()) if isinstance(planet_data_dict, dict) else 'Not a dict'}")

    # Log specific values being accessed
    keys_to_log = [
        "pl_name", "pl_rade", "pl_masse", "pl_dens", "pl_eqt", "st_teff", "st_rad", 
        "st_lum", "sy_dist", "pl_orbper", "pl_orbsmax", "st_spectype", "st_age", "pl_orbeccen"
    ]
    for key in keys_to_log:
        value = planet_data_dict.get(key)
        logger.debug(f"Value for key 	'{key}'	 in planet_data_dict for {planet_name}: 	'{value}'	 (Type: {type(value)})")

    if "pl_name" not in planet_data_dict or pd.isna(planet_data_dict.get("pl_name")):
        planet_data_dict["pl_name"] = planet_name
    logger.debug(f"Final planet_data_dict['pl_name'] for {planet_name}: {planet_data_dict.get('pl_name')}")

    classification_display = classify_planet(
        planet_data_dict.get("pl_masse"), 
        planet_data_dict.get("pl_rade"), 
        planet_data_dict.get("pl_eqt")
    )
    planet_data_dict["classification"] = classification_display
    logger.debug(f"Classification for {planet_name}: {classification_display}")

    sy_dist_pc = planet_data_dict.get("sy_dist") # Distance in parsecs
    sy_dist_ly = None
    if pd.notna(sy_dist_pc):
        try: sy_dist_ly = float(sy_dist_pc) * 3.26156
        except (ValueError, TypeError): sy_dist_ly = None
    logger.debug(f"Distance for {planet_name}: {sy_dist_ly} ly (from {sy_dist_pc} pc)")
    travel_curiosities_dict = calculate_travel_times(sy_dist_ly)
    planet_data_dict["travel_curiosities"] = travel_curiosities_dict
    logger.debug(f"Travel curiosities for {planet_name}: {travel_curiosities_dict}")

    star_info_dict = {
        "name": format_value(planet_data_dict.get("hostname"), default_na="N/A"),
        "type": format_value(planet_data_dict.get("st_spectype"), default_na="N/A"),
        "temperature_k": format_value(planet_data_dict.get("st_teff"), precision=0),
        "radius_solar": format_value(planet_data_dict.get("st_rad")),
        "mass_solar": format_value(planet_data_dict.get("st_mass")),
        "luminosity_log_solar": format_value(planet_data_dict.get("st_lum"), precision=3),
        "age_gyr": format_value(planet_data_dict.get("st_age")),
        "metallicity_dex": format_value(planet_data_dict.get("st_met")),
        "distance_ly": format_value(sy_dist_ly) 
    }
    planet_data_dict["star_info"] = star_info_dict
    logger.debug(f"Star info for {planet_name}: {star_info_dict}")

    orbit_info_dict = {
        "semi_major_axis_au": format_value(planet_data_dict.get("pl_orbsmax")),
        "eccentricity": format_value(planet_data_dict.get("pl_orbeccen"), precision=3),
        "period_days": format_value(planet_data_dict.get("pl_orbper")),
        "inclination_deg": format_value(planet_data_dict.get("pl_orbincl")),
        "distance_from_star_au": format_value(planet_data_dict.get("pl_orbsmax"))
    }
    planet_data_dict["orbit_info"] = orbit_info_dict
    logger.debug(f"Orbit info for {planet_name}: {orbit_info_dict}")

    hz_data_tuple = (
        planet_data_dict.get("hz_ohzin"), planet_data_dict.get("hz_chzin"), 
        planet_data_dict.get("hz_chzout"), planet_data_dict.get("hz_ohzout"),
        planet_data_dict.get("hz_teqa")
    )
    logger.debug(f"HZ data tuple for {planet_name}: {hz_data_tuple}")

    star_data_for_plot = {"st_lum": planet_data_dict.get("st_lum")}
    logger.debug(f"Star data for plot for {planet_name}: {star_data_for_plot}")
    esi_val, esi_color = calculate_esi_score(planet_data_dict, weights_config.get("habitability", {}))
    sph_val, sph_color = calculate_sph_score(planet_data_dict, weights_config.get("habitability", {}))
    phi_val, phi_color = calculate_phi_score(planet_data_dict, weights_config.get("phi", {}))
    scores_for_report = {"ESI": (esi_val, esi_color), "SPH": (sph_val, sph_color), "PHI": (phi_val, phi_color)}
    logger.debug(f"Basic scores for {planet_name}: {scores_for_report}")

    detailed_scores = calculate_detailed_habitability_scores(planet_data_dict, hz_data_tuple, weights_config)
    scores_for_report.update(detailed_scores)
    logger.debug(f"All scores (basic + detailed) for {planet_name}: {scores_for_report}")

    sephi_main, l1, l2, l3, l4 = calculate_sephi(
        planet_data_dict.get("pl_masse"), planet_data_dict.get("pl_rade"), 
        planet_data_dict.get("pl_orbper"), planet_data_dict.get("st_mass"), 
        planet_data_dict.get("st_rad"), planet_data_dict.get("st_teff"), 
        planet_data_dict.get("st_age"), planet_data_dict.get("pl_dens"),
        planet_data_dict.get("pl_name", planet_name)
    )
    sephi_scores_for_report = {}
    if sephi_main is not None:
        sephi_scores_for_report["SEPHI"] = (round(sephi_main,2), get_color_for_percentage(sephi_main))
        sephi_scores_for_report["L1 (Surface)"] = (round(l1,1), get_color_for_percentage(l1))
        sephi_scores_for_report["L2 (Escape Velocity)"] = (round(l2,1), get_color_for_percentage(l2))
        sephi_scores_for_report["L3 (Habitable Zone)"] = (round(l3,1), get_color_for_percentage(l3))
        sephi_scores_for_report["L4 (Magnetic Field)"] = (round(l4,1), get_color_for_percentage(l4))
    else:
        sephi_scores_for_report["SEPHI"] = ("N/A", get_color_for_percentage(None))
        for i in range(1,5): sephi_scores_for_report[f"L{i}"] = ("N/A", get_color_for_percentage(None))
    logger.debug(f"SEPHI scores for {planet_name}: {sephi_scores_for_report}")
    
    # Add formatted direct values to planet_data_dict for easier template access if needed
    # This ensures that if a template directly accesses e.g. {{ planet_info.pl_rade }},
    # it gets a formatted value or N/A, but keeps numerical fields as floats for calculations.
    fields_to_format_directly = [
        "pl_rade", "pl_masse", "pl_dens", "pl_eqt", "pl_orbper", "pl_orbsmax", 
        "sy_dist", "st_teff", "st_rad", "st_mass", "st_lum",
        "discoverymethod", "disc_year", "disc_facility"
    ]
    # Keep these fields as floats for calculations
    numerical_fields_to_preserve = ["pl_orbeccen", "st_age", "st_met"]
    for field in fields_to_format_directly:
        precision = 3 if field in ["st_lum", "st_met"] else 2
        if field == "st_teff" or field == "disc_year": precision = 0
        planet_data_dict[field] = format_value(planet_data_dict.get(field), precision=precision)
    for field in numerical_fields_to_preserve:
        try:
            value = planet_data_dict.get(field)
            planet_data_dict[field] = float(value) if pd.notna(value) else None
        except (ValueError, TypeError):
            planet_data_dict[field] = None
    for field in fields_to_format_directly:
        precision = 3 if field in ["pl_orbeccen", "st_lum", "st_met"] else 2
        if field == "st_teff" or field == "disc_year": precision = 0
        planet_data_dict[field] = format_value(planet_data_dict.get(field), precision=precision)

    logger.info(f"Finished processing data for {planet_name}. Final planet_data_dict keys: {list(planet_data_dict.keys())}")
    return {
        "planet_data_dict": planet_data_dict,
        "scores_for_report": scores_for_report,
        "sephi_scores_for_report": sephi_scores_for_report,
        "hz_data_tuple": hz_data_tuple,
        "star_data_for_plot": star_data_for_plot,
        "classification_display": planet_data_dict.get("classification"), # Make it directly accessible
        "travel_curiosities": planet_data_dict.get("travel_curiosities"), # Make it directly accessible
        "star_info": planet_data_dict.get("star_info"), # Make it directly accessible
        "orbit_info": planet_data_dict.get("orbit_info") # Make it directly accessible
    }

