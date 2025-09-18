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
    except (ValueError, TypeError):
        return "#757575"
        
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
    else: mass_class = "Unknown Mass Class"
    logger.debug(f"Mass class: {mass_class}")

    if pd.isna(temp_k) or temp_k < 0:
        temp_class = "Unknown Temperature Class"
    elif temp_k < 170: temp_class = "Hypopsychroplanet (Very Cold)"
    elif temp_k < 220: temp_class = "Psychroplanet (Cold)"
    elif temp_k < 273: temp_class = "Mesoplanet (Temperate 1)"
    elif temp_k < 323: temp_class = "Mesoplanet (Temperate 2 - Optimal for Earth Life)"
    elif temp_k < 373: temp_class = "Thermoplanet (Warm)"
    else: temp_class = "Hyperthermoplanet (Hot)"
    logger.debug(f"Temperature class: {temp_class}")
    
    final_classification = f"{mass_class} | {temp_class}"
    logger.debug(f"Final classification: {final_classification}")
    return final_classification


# --- SEPHI Calculation (adapted from lifesearch11.py) ---
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
            except ValueError: converted_params[name] = None
    
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
    else: L1 = 0.0

    earth_mass_ref, earth_radius_ref = 1.0, 1.0 # Earth units
    earth_g = earth_mass_ref / (earth_radius_ref ** 2)
    earth_v_e = math.sqrt(earth_g * earth_radius_ref)
    planet_g = pm / (pr ** 2)
    v_e = math.sqrt(planet_g * pr)
    v_e_relative = v_e / earth_v_e if earth_v_e > 0 else 0
    sigma_21, sigma_22 = (1.0 - 0.0) / 3, (8.66 - 1.0) / 3 # Assuming sigma can't be zero
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
        else: rho_0n, r_0n, F_n = 0.16, 16 * beta_1_val, 100 * beta_1_val
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
    
    The ESI measures similarity to Earth based on radius, density, and
    equilibrium temperature, weighted by the provided weights.
    
    Args:
        planet_data (dict): Dictionary containing planet parameters like
                            'pl_rade', 'pl_dens', 'pl_eqt'.
        weights (dict): Dictionary of weights for 'Size', 'Density',
                        and 'Habitable Zone' (temperature).
    
    Returns:
        tuple: (float ESI_score (0-100), str color_code_for_ESI).
               Returns 0.0 if no valid components are found.
    """
    logger.debug(f"Calculating ESI for planet: {planet_data.get('pl_name', 'Unknown')}")
    
    esi_components = []
    num_params = 0

    # Iterate over all possible ESI factors and use the weight if provided, else 0.0
    # The weights dictionary is expected to contain the *actual* values from the sliders.
    # If a weight is not explicitly set (i.e., it's still at its default), it should be treated as 0.
    # The `weights.get(key, 0.0)` handles this by providing 0.0 if the key is missing.
    esi_factors = ["Size", "Density", "Habitable Zone"]
    for factor in esi_factors:
        weight_val = weights.get(factor, 0.0)
        esi_components.append(weight_val)
        num_params += 1
        logger.debug(f"ESI component for {factor}: {weight_val}")

    if not esi_components or num_params == 0:
        logger.warning("Nenhum componente ESI válido encontrado.")
        return 0.0, get_color_for_percentage(0.0)

    # The final ESI is the average of the components (slider values) multiplied by 100
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

    if pd.isna(temp_k) or temp_k < 0:
        logger.warning(f"SPH calculation skipped for {planet_data.get('pl_name', 'Unknown')} due to missing or invalid temperature.")
        return 0.0, get_color_for_percentage(0.0)

    # Optimal temperature for Earth-like life is around 288K (15C)
    # We can use a Gaussian-like function or a simple linear drop-off
    # For simplicity, let's use a range and assign scores.
    if 273 <= temp_k <= 373: # Within habitable range
        score = 100.0 - (abs(temp_k - 288) / 100.0) * 100.0 # Closer to 288K is better
        if score < 0: score = 0.0
    else:
        score = 0.0

    logger.info(f"SPH final para {planet_data.get('pl_name', 'Unknown')}: {score}")
    return round(score, 2), get_color_for_percentage(score)

def calculate_phi_score(planet_data, weights):
    """Calculates the Planetary Habitability Index (PHI) for a planet.
    
    PHI is based on four main factors: Solid Surface, Stable Energy, Life Compounds,
    and Stable Orbit. Each factor's contribution is determined by the provided weights.
    
    Args:
        planet_data (dict): Dictionary containing planet parameters.
        weights (dict): Dictionary of weights for PHI factors.
    
    Returns:
        tuple: (float PHI_score (0-100), str color_code_for_PHI).
               Returns 0.0 if no valid components are found.
    """
    logger.debug(f"Calculating PHI for planet: {planet_data.get('pl_name', 'Unknown')}")
    
    phi_components = []
    num_factors = 0

    # Iterate over all possible PHI factors and use the weight if provided, else 0.0.
    # The weights dictionary is expected to contain the *actual* values from the sliders.
    # If a weight is not explicitly set (i.e., it's still at its default), it should be treated as 0.
    # The `weights.get(key, 0.0)` handles this by providing 0.0 if the key is missing.
    phi_factors = ["Solid Surface", "Stable Energy", "Life Compounds", "Stable Orbit"]
    for factor in phi_factors:
        weight_val = weights.get(factor, 0.0)
        phi_components.append(weight_val)
        num_factors += 1
        logger.debug(f"PHI component for {factor}: {weight_val}")

    if not phi_components or num_factors == 0:
        logger.warning("Nenhum componente PHI válido encontrado.")
        return 0.0, get_color_for_percentage(0.0)

    # The final PHI is the average of the components (slider values) multiplied by 100
    final_phi = (sum(phi_components) / num_factors) * 100
    logger.info(f"PHI final para {planet_data.get('pl_name', 'Unknown')}: {final_phi}")
    
    return round(final_phi, 2), get_color_for_percentage(final_phi)

def process_planet_data(planet_name, combined_data, weights):
    """Processes a single planet's data to calculate various habitability scores.

    Args:
        planet_name (str): The name of the planet.
        combined_data (dict): A dictionary containing all available data for the planet.
        weights (dict): A dictionary containing 'habitability' and 'phi' weights.

    Returns:
        dict: A dictionary containing processed planet data, scores, SEPHI components,
              habitable zone data, and star information.
    """
    logger.info(f"Processing data for planet: {planet_name}")

    # Extract relevant parameters for calculations
    pl_name = combined_data.get("pl_name", planet_name)
    pl_rade = combined_data.get("pl_rade")
    pl_masse = combined_data.get("pl_masse")
    pl_dens = combined_data.get("pl_dens")
    pl_eqt = combined_data.get("pl_eqt")
    pl_orbper = combined_data.get("pl_orbper")
    pl_orbeccen = combined_data.get("pl_orbeccen")
    st_mass = combined_data.get("st_mass")
    st_rad = combined_data.get("st_rad")
    st_teff = combined_data.get("st_teff")
    st_age = combined_data.get("st_age")
    st_spectype = combined_data.get("st_spectype")
    sy_dist = combined_data.get("sy_dist")

    # Ensure numerical types for calculations
    try:
        pl_rade = float(pl_rade) if pd.notna(pl_rade) else None
        pl_masse = float(pl_masse) if pd.notna(pl_masse) else None
        pl_dens = float(pl_dens) if pd.notna(pl_dens) else None
        pl_eqt = float(pl_eqt) if pd.notna(pl_eqt) else None
        pl_orbper = float(pl_orbper) if pd.notna(pl_orbper) else None
        pl_orbeccen = float(pl_orbeccen) if pd.notna(pl_orbeccen) else None
        st_mass = float(st_mass) if pd.notna(st_mass) else None
        st_rad = float(st_rad) if pd.notna(st_rad) else None
        st_teff = float(st_teff) if pd.notna(st_teff) else None
        st_age = float(st_age) if pd.notna(st_age) else None
        sy_dist = float(sy_dist) if pd.notna(sy_dist) else None
    except ValueError as e:
        logger.error(f"Error converting planet parameters to float for {pl_name}: {e}")
        return None

    # Calculate ESI, SPH, PHI
    esi_score, esi_color = calculate_esi_score(combined_data, weights.get("habitability", {}))
    sph_score, sph_color = calculate_sph_score(combined_data, weights.get("habitability", {}))
    phi_score, phi_color = calculate_phi_score(combined_data, weights.get("phi", {}))

    # Calculate SEPHI components
    sephi_score, L1, L2, L3, L4 = calculate_sephi(
        pl_masse, pl_rade, pl_orbper, st_mass, st_rad, st_teff, st_age, pl_dens, pl_name
    )

    # Classify planet
    classification = classify_planet(pl_masse, pl_rade, pl_eqt)

    # Prepare data for report
    planet_data_dict = {
        "pl_name": pl_name,
        "pl_rade": format_value(pl_rade),
        "pl_masse": format_value(pl_masse),
        "pl_dens": format_value(pl_dens),
        "pl_eqt": format_value(pl_eqt, precision=1),
        "pl_orbper": format_value(pl_orbper, precision=1),
        "pl_orbeccen": format_value(pl_orbeccen, precision=3),
        "sy_dist": format_value(sy_dist, precision=2),
        "st_spectype": st_spectype if pd.notna(st_spectype) else "N/A",
        "st_age": format_value(st_age, precision=2),
        "classification": classification,
        "hostname": combined_data.get("hostname", "N/A"),
        "discovery_year": combined_data.get("disc_year", "N/A"),
        "detection_type": combined_data.get("discoverymethod", "N/A"),
        "updated_date": combined_data.get("rowupdate", "N/A"),
        "url": combined_data.get("url", "#"),
        "description": combined_data.get("description", "No description available.")
    }

    scores_for_report = {
        "ESI": (esi_score, esi_color),
        "SPH": (sph_score, sph_color),
        "PHI": (phi_score, phi_color)
    }

    sephi_scores_for_report = {
        "SEPHI": (sephi_score, get_color_for_percentage(sephi_score)) if sephi_score is not None else (0.0, get_color_for_percentage(0.0)),
        "L1": (L1, get_color_for_percentage(L1)) if L1 is not None else (0.0, get_color_for_percentage(0.0)),
        "L2": (L2, get_color_for_percentage(L2)) if L2 is not None else (0.0, get_color_for_percentage(0.0)),
        "L3": (L3, get_color_for_percentage(L3)) if L3 is not None else (0.0, get_color_for_percentage(0.0)),
        "L4": (L4, get_color_for_percentage(L4)) if L4 is not None else (0.0, get_color_for_percentage(0.0))
    }

    star_info = {
        "st_mass": format_value(st_mass, precision=2),
        "st_rad": format_value(st_rad, precision=2),
        "st_teff": format_value(st_teff, precision=0),
        "st_age": format_value(st_age, precision=2),
        "st_spectype": st_spectype if pd.notna(st_spectype) else "N/A"
    }

    # Habitable Zone data for plotting
    hz_data_tuple = (st_teff, st_rad, st_mass, pl_orbper, pl_orbeccen) # Pass as tuple

    travel_times = calculate_travel_times(sy_dist)

    return {
        "planet_data_dict": planet_data_dict,
        "scores_for_report": scores_for_report,
        "sephi_scores_for_report": sephi_scores_for_report,
        "hz_data_tuple": hz_data_tuple,
        "star_info": star_info,
        "travel_times": travel_times
    }

def sliders_phi(planet_data):
    """Calculates the initial values for PHI sliders based on planet data.

    This function should return values that reflect the planet's inherent
    characteristics for each PHI factor, ranging from 0.0 to 1.0.
    If a characteristic is not applicable or unknown, it should default to 0.0.

    Args:
        planet_data (dict): Dictionary containing planet parameters.

    Returns:
        dict: A dictionary with PHI factors as keys and their calculated initial
              slider values (0.0 to 1.0) as values.
    """
    # Initialize all PHI factors to 0.0 by default
    phi_values = {
        "Solid Surface": 0.0,
        "Stable Energy": 0.0,
        "Life Compounds": 0.0,
        "Stable Orbit": 0.0
    }

    # Example logic for Solid Surface (based on planet type/mass/radius)
    # This is a placeholder; actual logic should be more robust.
    # For demonstration, let's assume rocky planets have a higher solid surface score.
    pl_rade = planet_data.get("pl_rade")
    pl_masse = planet_data.get("pl_masse")

    if pl_rade is not None and pl_masse is not None:
        # Simple heuristic: if radius and mass are within Earth-like range, assume solid surface
        if 0.5 < pl_rade < 2.0 and 0.1 < pl_masse < 10.0:
            phi_values["Solid Surface"] = 1.0  # High likelihood of solid surface
        elif 0.1 < pl_rade < 0.5 or 2.0 <= pl_rade < 5.0:
            phi_values["Solid Surface"] = 0.5  # Moderate likelihood
        else:
            phi_values["Solid Surface"] = 0.0  # Low likelihood (e.g., gas giant or very small/large)
    
    # Example logic for Stable Energy (based on stellar type/luminosity/orbital period)
    # This is a placeholder; actual logic should be more robust.
    st_teff = planet_data.get("st_teff")
    pl_orbper = planet_data.get("pl_orbper")
    if st_teff is not None and pl_orbper is not None:
        # Simple heuristic: if star is sun-like and orbital period is reasonable
        if 4000 < st_teff < 7000 and 50 < pl_orbper < 500:
            phi_values["Stable Energy"] = 1.0
        else:
            phi_values["Stable Energy"] = 0.5

    # Example logic for Life Compounds (presence of water, atmosphere, etc.)
    # This is a placeholder; actual logic should be more robust.
    # If you have data on water presence (e.g., 'has_water'), use it.
    # For this example, we'll just set a default.
    phi_values["Life Compounds"] = 0.75 # Placeholder

    # Example logic for Stable Orbit (eccentricity, presence of other large bodies)
    # This is a placeholder; actual logic should be more robust.
    pl_orbeccen = planet_data.get("pl_orbeccen")
    if pl_orbeccen is not None:
        if pl_orbeccen < 0.1: # Low eccentricity
            phi_values["Stable Orbit"] = 1.0
        elif 0.1 <= pl_orbeccen < 0.5:
            phi_values["Stable Orbit"] = 0.5
        else:
            phi_values["Stable Orbit"] = 0.0

    return phi_values

def reference_values_slider(planet_data):
    """Calculates reference ESI and PHI values for a planet using its inherent properties.

    This function should *not* use any user-configured weights. It should reflect
    the planet's natural habitability scores based on its physical characteristics.

    Args:
        planet_data (dict): Dictionary containing planet parameters.

    Returns:
        tuple: (float ESI_score (0-100), float PHI_score (0-100)).
    """
    logger.debug(f"Calculating reference ESI/PHI for planet: {planet_data.get('pl_name', 'Unknown')}")

    # Calculate ESI based on inherent properties (e.g., similarity to Earth's fundamental properties)
    # This is a simplified example. A real ESI calculation would be more complex.
    esi_score = 0.0
    pl_rade = planet_data.get("pl_rade")
    pl_dens = planet_data.get("pl_dens")
    pl_eqt = planet_data.get("pl_eqt")

    # Simple ESI calculation based on proximity to Earth's values (0-1 scale for each factor)
    # Radius similarity
    if pl_rade is not None:
        s_r = 1.0 - abs(pl_rade - 1.0) / (pl_rade + 1.0) # Earth radius = 1.0
        if s_r < 0: s_r = 0.0
    else: s_r = 0.0

    # Density similarity
    if pl_dens is not None:
        s_d = 1.0 - abs(pl_dens - 5.51) / (pl_dens + 5.51) # Earth density = 5.51 g/cm^3
        if s_d < 0: s_d = 0.0
    else: s_d = 0.0

    # Temperature similarity (using a habitable range, e.g., 273K to 373K)
    if pl_eqt is not None:
        # Optimal temperature for Earth-like life is around 288K (15C)
        # We can use a Gaussian-like function or a simple linear drop-off
        # For simplicity, let's use a range and assign scores.
        if 273 <= pl_eqt <= 373: # Within habitable range
            s_t = 1.0 - abs(pl_eqt - 288) / 100.0 # Closer to 288K is better
            if s_t < 0: s_t = 0.0
        else:
            s_t = 0.0
    else: s_t = 0.0

    # Average the similarities to get a basic ESI (0-1 scale)
    esi_components = [s_r, s_d, s_t]
    if len(esi_components) > 0:
        esi_score = (sum(esi_components) / len(esi_components)) * 100
    else:
        esi_score = 0.0

    # Calculate PHI based on inherent properties (e.g., using sliders_phi output directly)
    # The sliders_phi function already calculates values from 0.0 to 1.0 based on planet data.
    phi_initial_values = sliders_phi(planet_data)
    phi_score = 0.0
    if phi_initial_values:
        phi_score = (sum(phi_initial_values.values()) / len(phi_initial_values)) * 100

    logger.info(f"Reference ESI: {esi_score:.2f}%, Reference PHI: {phi_score:.2f}%")
    return round(esi_score, 2), round(phi_score, 2)


