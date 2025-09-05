import matplotlib
matplotlib.use("Agg")  # Set non-interactive backend for matplotlib

import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape # Import select_autoescape
import json  # For logging context and SAVING DATA
import traceback  # For explicit error printing
import time 

logger = logging.getLogger(__name__)

# Helper function to create output directories if they don"t exist
def ensure_dir(directory):
    """Ensures that a directory exists, creating it if necessary.
    
    Logs the creation of the directory if it did not already exist.
    
    Args:
        directory (str): The path to the directory to check/create.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def get_color_for_percentage(percentage):
    """Determines a hex color code based on a percentage value for reports.
    
    Colors are based on Bootstrap-like alert levels (success, warning, danger)
    and shades in between.
    
    Args:
        percentage (float or None): The percentage value. Handles None, NaN,
                                    and unconvertible values by returning grey.
    
    Returns:
        str: Hex color code string (e.g., "#28a745" for green, "#808080" for grey/N/A).
    """
    if percentage is None or pd.isna(percentage):
        return "#808080"  # Grey for N/A
    try:
        percentage = float(percentage)
    except (ValueError, TypeError):
        return "#808080"  # Grey for invalid

    if percentage >= 80:
        return "#28a745"  # Green (Bootstrap success)
    elif percentage >= 60:
        return "#90ee90"  # Light Green (PaleGreen)
    elif percentage >= 40:
        return "#ffc107"  # Amber (Bootstrap warning)
    elif percentage >= 20:
        return "#fd7e14"  # Orange (Bootstrap orange)
    else:
        return "#dc3545"  # Red (Bootstrap danger)

# Corrected formatting for potentially string numeric values
def format_float_field(value, precision=".2f"):
    """Formats a value as a float string with specified precision, or returns "N/A".
    
    Handles pandas NaN, None, "N/A" strings, or empty strings by returning "N/A".
    Attempts to convert the value to a float before formatting. If conversion fails,
    the original string representation is returned.
    
    Args:
        value (any): The value to format.
        precision (str): The precision format string for the float (e.g., ".2f").
    
    Returns:
        str: The formatted float string, "N/A", or the original string value if
             conversion to float fails.
    """
    if pd.isna(value) or value == "N/A" or str(value).strip() == "":
        return "N/A"
    try:
        return f"{float(str(value)):{precision}}"
    except (ValueError, TypeError):
        return str(value)  # Return as string if conversion fails

# Novas funções auxiliares:
def get_score_description(scores_dict, field_name, classification):
    score_info = get_score_info(scores_dict, field_name)
    score = score_info["score"]
    if score >= 80:
        desc = "Likely"
    elif score >= 50:
        desc = "Possible"
    else:
        desc = "Unlikely"
    return {
        "score": score,
        "color": score_info["color"],
        "text": desc
    }

def get_score_description_bio(scores_dict, field_name, pl_eqt):
    score_info = get_score_info(scores_dict, field_name)
    score = score_info["score"]
    try:
        temp = float(pl_eqt) if pl_eqt is not None else None
        if temp and temp > 1000:
            desc = "Unlikely (Too Hot)"
        elif score >= 60:
            desc = "Likely"
        elif score >= 30:
            desc = "Possible"
        else:
            desc = "Unlikely"
    except:
        desc = "Unlikely"
    return {
        "score": score,
        "color": score_info["color"],
        "text": desc
    }

def get_score_description_moons(scores_dict, field_name, classification, planet_data):
    score_info = get_score_info(scores_dict, field_name)
    score = score_info["score"]
    mass = to_float_or_none(planet_data.get("pl_masse"))
    pl_orbsmax = to_float_or_none(planet_data.get("pl_orbsmax"))
    if "Neptunian" in classification or "Jovian" in classification:
        desc = "Likely"
    elif "Terran" in classification or "Superterran" in classification:
        if mass is not None and mass > 0.5 and pl_orbsmax is not None and pl_orbsmax > 1:
            desc = "Highly Possible"
        elif mass is not None and mass > 0.5:
            desc = "Possible"
        else:
            desc = "Unlikely"
    else:
        desc = "Unlikely"
    return {
        "score": score,
        "color": score_info["color"],
        "text": desc
    }

def to_float_or_none(val):
    if pd.isna(val) or val is None: return None
    try: return float(val)
    except (ValueError, TypeError): return None


# --- Plotting Functions ---
def plot_habitable_zone(planet_data, star_data, hz_limits, output_path, planet_name_slug):
    """Generates and saves a plot of the habitable zone for a given planet.
    
    Visualizes the optimistic and conservative habitable zones relative to the
    planet's orbital semi-major axis. The plot is saved as a PNG file.
    It can calculate HZ limits based on stellar luminosity if not provided.
    
    Args:
        planet_data (dict): Dictionary containing planet parameters like 'pl_orbsmax', 'pl_name'.
        star_data (dict): Dictionary containing stellar parameters like 'st_lum'.
        hz_limits (tuple or None): Tuple of (ohz_in, chz_in, chz_out, ohz_out, teqa_hz_flag)
                                   or None if limits need to be calculated.
        output_path (str): The directory where the plot will be saved.
        planet_name_slug (str): A slugified version of the planet name, used for the filename.
    
    Returns:
        str or None: The filename of the saved plot (e.g., "planet_slug_hz.png") if successful,
                     None otherwise.
    """
    ensure_dir(output_path)
    plot_filename = f"{planet_name_slug}_hz.png"
    full_plot_path = os.path.join(output_path, plot_filename)
    logger.debug(f"Attempting to plot habitable zone for {planet_name_slug} to {full_plot_path}")

    try:
        fig, ax = plt.subplots(figsize=(10, 2))
        ohz_in, chz_in, chz_out, ohz_out, _ = (None, None, None, None, None) if hz_limits is None else hz_limits
        
        st_lum_val = star_data.get("st_lum")  # Expecting log(L/Lsun)
        L_star_L_sun = None
        if pd.notna(st_lum_val):
            try:
                L_star_L_sun = 10**float(st_lum_val)
            except (ValueError, TypeError):
                L_star_L_sun = None

        ohz_in_plot, chz_in_plot, chz_out_plot, ohz_out_plot = ohz_in, chz_in, chz_out, ohz_out

        if L_star_L_sun is not None:
            conservative_inner_limit = (0.95 * np.sqrt(L_star_L_sun))
            conservative_outer_limit = (1.67 * np.sqrt(L_star_L_sun))
            optimistic_inner_limit = (0.75 * np.sqrt(L_star_L_sun))
            optimistic_outer_limit = (2.0 * np.sqrt(L_star_L_sun))

            chz_in_plot = chz_in if pd.notna(chz_in) else conservative_inner_limit
            chz_out_plot = chz_out if pd.notna(chz_out) else conservative_outer_limit
            ohz_in_plot = ohz_in if pd.notna(ohz_in) else optimistic_inner_limit
            ohz_out_plot = ohz_out if pd.notna(ohz_out) else optimistic_outer_limit
        
        if pd.notna(ohz_in_plot) and pd.notna(ohz_out_plot):
            ax.axvspan(ohz_in_plot, ohz_out_plot, alpha=0.3, color="palegreen", label="Optimistic HZ")
        if pd.notna(chz_in_plot) and pd.notna(chz_out_plot):
            ax.axvspan(chz_in_plot, chz_out_plot, alpha=0.5, color="green", label="Conservative HZ")
        
        pl_orbsmax = planet_data.get("pl_orbsmax")
        pl_orbsmax_fl = None
        if pd.notna(pl_orbsmax):
            try:
                pl_orbsmax_fl = float(pl_orbsmax)
            except (ValueError, TypeError):
                pass
        
        if pl_orbsmax_fl is not None:
            planet_name_value = planet_data.get("pl_name", planet_name_slug)
            orbit_details = f"({pl_orbsmax_fl:.2f} AU)"
            label_text = f"{planet_name_value} {orbit_details}"
            ax.plot(pl_orbsmax_fl, 0, "o", markersize=10, color="blue", label=label_text)
        else:
            logger.warning(f"Orbital semi-major axis (pl_orbsmax) not available or not float for {planet_name_slug}.")

        ax.set_yticks([])
        ax.set_xlabel("Distance from Star (AU)")
        planet_name_value = planet_data.get("pl_name", planet_name_slug)
        title_text = f"Habitable Zone for {planet_name_value}"
        ax.set_title(title_text)
        
        x_values = [val for val in [ohz_in_plot, ohz_out_plot, chz_in_plot, chz_out_plot, pl_orbsmax_fl] if pd.notna(val)]
        if x_values:
            min_x = min(x_values) * 0.8
            max_x = max(x_values) * 1.2
            if min_x == max_x:
                min_x -= 0.5
                max_x += 0.5
            ax.set_xlim(min_x, max_x)
        else:
            ax.set_xlim(0, 2)

        ax.legend(loc="upper right")
        plt.tight_layout()
        plt.savefig(full_plot_path)
        plt.close(fig)
        logger.info(f"Habitable zone plot saved to {full_plot_path}")
        return plot_filename
    except Exception as e:
        logger.error(f"Error generating habitable zone plot for {planet_name_slug}: {e}", exc_info=True)
        traceback.print_exc()
        return None

def plot_scores_comparison(scores_data, output_path, planet_name_slug):
    """Generates and saves a horizontal bar chart comparing various habitability scores.
    
    The plot displays scores as percentages with color-coded bars.
    It filters out non-numeric or invalid score data.
    
    Args:
        scores_data (dict): A dictionary where keys are score names and values are
                            tuples, typically (score_value, color_code, ...).
                            Only the score_value (first element) and optionally
                            color_code (second element) are used.
        output_path (str): The directory where the plot will be saved.
        planet_name_slug (str): A slugified version of the planet name, used for the filename.
    
    Returns:
        str or None: The filename of the saved plot (e.g., "planet_slug_scores.png")
                     if successful, None otherwise.
    """
    ensure_dir(output_path)
    plot_filename = f"{planet_name_slug}_scores.png"
    full_plot_path = os.path.join(output_path, plot_filename)

    if not scores_data or not isinstance(scores_data, dict):
        logger.warning(f"No valid scores data (must be a dict) provided for {planet_name_slug}.")
        return None

    try:
        valid_scores_data = {}
        for k, v_tuple in scores_data.items():
            if isinstance(v_tuple, tuple) and len(v_tuple) > 0 and pd.notna(v_tuple[0]):
                try:
                    float_val = float(v_tuple[0])
                    valid_scores_data[k] = (float_val, v_tuple[1] if len(v_tuple) > 1 else get_color_for_percentage(float_val))
                except (ValueError, TypeError):
                    logger.debug(f"Could not convert score value {v_tuple[0]} for {k} to float.")
        
        if not valid_scores_data:
            logger.warning(f"No valid numeric scores to plot for {planet_name_slug} after filtering.")
            return None

        labels = list(valid_scores_data.keys())
        values = [valid_scores_data[k][0] for k in labels]
        colors = [valid_scores_data[k][1] for k in labels]

        fig, ax = plt.subplots(figsize=(10, max(6, len(labels) * 0.5)))
        bars = ax.barh(labels, values, color=colors)
        ax.set_xlabel("Score (%)")
        ax.set_title(f"Habitability Scores for {planet_name_slug}")
        ax.set_xlim(0, 100)

        for bar in bars:
            width = bar.get_width()
            ax.text(width + 1, bar.get_y() + bar.get_height()/2., f"{width:.1f}%")

        plt.tight_layout()
        plt.savefig(full_plot_path)
        plt.close(fig)
        logger.info(f"Scores comparison plot saved to {full_plot_path}")
        return plot_filename
    except Exception as e:
        logger.error(f"Error generating scores comparison plot for {planet_name_slug}: {e}", exc_info=True)
        traceback.print_exc()
        return None

# --- HTML Report Generation ---
def generate_planet_report_html(planet_data_dict, scores, sephi_scores, plots, template_env, output_dir, planet_name_slug):
    """Generates an individual HTML report for a planet.
    
    Uses a Jinja2 template ("report_template.html") to render the planet's data,
    habitability scores (general and SEPHI), and links to generated plots.
    
    Args:
        planet_data_dict (dict): Dictionary containing detailed data for the planet.
        scores (dict): Dictionary of general habitability scores and their display colors.
        sephi_scores (dict): Dictionary of SEPHI scores and their display colors.
        plots (dict): Dictionary of plot filenames to be included in the report.
        template_env (jinja2.Environment): The Jinja2 template environment.
        output_dir (str): The directory where the HTML report will be saved.
        planet_name_slug (str): A slugified version of the planet name, used for the filename.
    
    Returns:
        str or None: The full path to the generated HTML report file if successful,
                     None otherwise.
    """
    ensure_dir(output_dir)
    report_filename = f"{planet_name_slug}_report.html"
    full_report_path = os.path.join(output_dir, report_filename)
    logger.debug(f"Generating individual report for {planet_name_slug} to {full_report_path}")
    try:
        template = template_env.get_template("report_template.html")
        
        transformed_scores_list = []
        if isinstance(scores, dict):
            for field, data_tuple in scores.items():
                if isinstance(data_tuple, tuple) and len(data_tuple) >= 2 and pd.notna(data_tuple[0]):
                    transformed_scores_list.append({"field": field, "value": data_tuple[0], "color": data_tuple[1]})
        
        transformed_sephi_scores_list = []
        if isinstance(sephi_scores, dict):
            for field, data_tuple in sephi_scores.items():
                if isinstance(data_tuple, tuple) and len(data_tuple) >= 2 and pd.notna(data_tuple[0]):
                    transformed_sephi_scores_list.append({"field": field, "value": data_tuple[0], "color": data_tuple[1]})

        star_info_for_template = {
            "name": planet_data_dict.get("hostname", "N/A"),
            "type": planet_data_dict.get("st_spectype", "N/A"),
            "temperature_k": format_float_field(planet_data_dict.get("st_teff"), ".0f"),
            "radius_solar": format_float_field(planet_data_dict.get("st_rad")),
            "mass_solar": format_float_field(planet_data_dict.get("st_mass")),
            "luminosity_log_solar": format_float_field(planet_data_dict.get("st_lum")),
            "age_gyr": format_float_field(planet_data_dict.get("st_age")),
            "metallicity_dex": format_float_field(planet_data_dict.get("st_metfe"))
        }
        sy_dist_pc = planet_data_dict.get("sy_dist")
        if pd.notna(sy_dist_pc):
            try:
                star_info_for_template["distance_ly"] = f"{float(str(sy_dist_pc)) * 3.26156:.2f}"
            except (ValueError, TypeError):
                star_info_for_template["distance_ly"] = "N/A"
        else:
            star_info_for_template["distance_ly"] = "N/A"

        orbit_info_for_template = {
            "semi_major_axis_au": format_float_field(planet_data_dict.get("pl_orbsmax")),
            "period_days": format_float_field(planet_data_dict.get("pl_orbper")),
            "eccentricity": format_float_field(planet_data_dict.get("pl_orbeccen")),
            "inclination_deg": format_float_field(planet_data_dict.get("pl_orbincl"))
        }
        
        travel_curiosities_for_template = {}
        dist_pc_for_travel = planet_data_dict.get("sy_dist")
        if pd.notna(dist_pc_for_travel):
            try:
                dist_ly_f = float(str(dist_pc_for_travel)) * 3.26156
                travel_curiosities_for_template["distance_ly"] = f"{dist_ly_f:.2f}" # Added for individual report
                travel_curiosities_for_template["scenario_1_label"] = "Current Tech (e.g., Parker Solar Probe ~170 km/s)"
                travel_curiosities_for_template["scenario_1_time"] = f"{dist_ly_f * (299792.458 / 170) / 1000:.1f} thousand years" # Corrected speed of light
                travel_curiosities_for_template["scenario_2_label"] = "Future Tech (20% speed of light)"
                travel_curiosities_for_template["scenario_2_time"] = f"{dist_ly_f / 0.2:.1f} years"
                travel_curiosities_for_template["scenario_3_label"] = "Relativistic (99% speed of light)"
                travel_curiosities_for_template["scenario_3_time"] = f"{dist_ly_f / 0.99:.1f} years"
            except (ValueError, TypeError):
                logger.warning(f"Could not calculate travel times for {planet_name_slug} due to distance conversion error.")
                travel_curiosities_for_template["distance_ly"] = "N/A"
                travel_curiosities_for_template["scenario_1_time"] = "N/A"
                travel_curiosities_for_template["scenario_2_time"] = "N/A"
                travel_curiosities_for_template["scenario_3_time"] = "N/A"
        else:
            travel_curiosities_for_template["distance_ly"] = "N/A"
            travel_curiosities_for_template["scenario_1_time"] = "N/A"
            travel_curiosities_for_template["scenario_2_time"] = "N/A"
            travel_curiosities_for_template["scenario_3_time"] = "N/A"

        context = {
            "planet_data": planet_data_dict, 
            "planet_info": planet_data_dict, 
            "orbit_info": orbit_info_for_template,
            "star_info": star_info_for_template,
            "travel_curiosities": travel_curiosities_for_template,
            "classification_display": planet_data_dict.get("classification_final_display", planet_data_dict.get("classification", "N/A")),
            "scores": transformed_scores_list, 
            "sephi_scores": transformed_sephi_scores_list, 
            "plots": plots, 
            "datetime": datetime
        }

        html_content = template.render(context)
        with open(full_report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"HTML report for {planet_name_slug} saved to {full_report_path}")
        return full_report_path
    except Exception as e:
        logger.error(f"Error generating HTML report for {planet_name_slug}: {e}", exc_info=True)
        traceback.print_exc()
        return None
    

def enrich_atmosphere_water_magnetic_moons(data, classification):
    """Estimates potential scores and descriptions for atmosphere, water, magnetic activity, and moons.
    
    Calculations are based on planet's equilibrium temperature (pl_eqt), mass (pl_masse),
    star's spectral type (st_spectype), and the planet's general classification.
    Temperature is calculated if not directly available.
    
    Args:
        data (dict): Dictionary containing planet data (e.g., 'pl_eqt', 'st_teff', 'st_rad',
                     'pl_orbsmax', 'pl_masse', 'st_spectype').
        classification (str): The general classification of the planet (e.g., "Terran", "Superterran").
    
    Returns:
        dict: A dictionary containing scores (0-100) and descriptive strings for:
              - 'atmosphere_potential_score', 'atmosphere_potential_desc'
              - 'liquid_water_potential_score', 'liquid_water_potential_desc'
              - 'magnetic_activity_score', 'magnetic_activity_desc'
              - 'presence_of_moons_score', 'presence_of_moons_desc'
    """
    temp_str = data.get("pl_eqt")  # Obter como string ou None
    temp = None  # Inicializar temp numérico

    if temp_str is not None:
        try:
            temp = float(temp_str)  # Tentar converter para float
        except (ValueError, TypeError):
            logger.warning(f"Não foi possível converter pl_eqt '{temp_str}' para float. Tentando recalcular ou usar valor padrão.")
            temp = None  # Garantir que temp seja None se a conversão falhar

    if temp is None:  # Se era None inicialmente ou a conversão falhou
        # Tentar calcular a temperatura
        st_teff_str = data.get("st_teff")
        st_rad_str = data.get("st_rad")
        pl_orbsmax_str = data.get("pl_orbsmax")
        albedo = 0.3
        
        st_teff_num, st_rad_num, pl_orbsmax_num = None, None, None
        try:
            if st_teff_str is not None: st_teff_num = float(st_teff_str)
            if st_rad_str is not None: st_rad_num = float(st_rad_str)
            if pl_orbsmax_str is not None: pl_orbsmax_num = float(pl_orbsmax_str)
        except (ValueError, TypeError):
            logger.warning(f"Não foi possível converter parâmetros da estrela para cálculo da temperatura para o planeta {data.get('pl_name', 'Desconhecido')}.")
            # Deixar como None, o bloco seguinte tratará isso

        if st_teff_num is not None and st_rad_num is not None and pl_orbsmax_num is not None and pl_orbsmax_num > 0:
            temp = st_teff_num * ((st_rad_num / (2 * pl_orbsmax_num)) ** 0.5) * ((1 - albedo) ** 0.25)
            logger.info(f"Temperatura calculada para {data.get('pl_name', 'Desconhecido')}: {temp:.2f} K")
        else:
            logger.warning(f"Não foi possível calcular a temperatura para {data.get('pl_name', 'Desconhecido')}, usando valor padrão de 278 K.")
            temp = 278  # Valor padrão se o cálculo não for possível

    # Garantir que temp seja um número neste ponto para as comparações
    if temp is None: # Esta condição não deve ser atingida se o padrão for definido
        logger.error(f"Temperatura inesperadamente None para {data.get('pl_name', 'Desconhecido')} após todas as verificações. Usando 278K.")
        temp = 278

    # Scores numéricos
    # Agora 'temp' é um float e a comparação funcionará
    if 273 < temp <= 373:
        atmosphere_score = 90
        water_score = 90
    elif 200 <= temp <= 273 or 373 < temp <= 450:
        atmosphere_score = 50
        water_score = 50
    else:
        atmosphere_score = 20
        water_score = 20

    # Descrições
    atmosphere_desc = "Likely" if 273 < temp <= 373 else "Possible" if 200 <= temp <= 273 or 373 < temp <= 450 else "Unlikely"
    water_desc = atmosphere_desc

    # Magnetic Activity (Score)
    mass_str = data.get("pl_masse") 
    mass = None
    if mass_str is not None:
        try:
            mass = float(mass_str)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert mass '{mass_str}' to float for planet {data.get('pl_name', 'Unknown')}")
            
    st_spectype = data.get("st_spectype")
    magnetic_desc = "Low" # Default
    magnetic_score = 10.0 # Default
    star_type_condition_met = False

    if isinstance(st_spectype, str) and st_spectype.strip(): # Verifica se é uma string não vazia
        if st_spectype.startswith("G") or st_spectype.startswith("K"):
         star_type_condition_met = True

    if mass is not None:
        if mass > 1 and ("Terran" in classification or "Superterran" in classification):
            magnetic_score = 80
            if st_spectype and st_spectype.startswith("K"): # Checar se st_spectype não é None
                magnetic_score = 90
        elif mass < 0.5:
            magnetic_score = 40
        # else: magnetic_score remains 60 or is set by st_spectype below
    elif st_spectype: # Checar se st_spectype não é None
        if st_spectype.startswith("M"):
            magnetic_score = 40
        elif st_spectype.startswith("G") or st_spectype.startswith("K"):
            magnetic_score = 80
    # else: magnetic_score remains 60 (default)

    # Magnetic Activity (Description)
    magnetic_desc = "Low" # Default
    if (mass is not None and mass > 1 and ("Terran" in classification or "Superterran" in classification)) or \
       (st_spectype and (st_spectype.startswith("G") or st_spectype.startswith("K"))):
        magnetic_desc = "High"
    elif mass is not None and mass >= 0.5:
        magnetic_desc = "Moderate"

    # Presence of Moons (Score & Description)
    if "Terran" in classification or "Superterran" in classification:
        moons_score = 80
        moons_desc = "Possible"
    else:
        moons_score = 30
        moons_desc = "Unlikely"

    return {
        "atmosphere_potential_score": atmosphere_score,
        "liquid_water_potential_score": water_score,
        "magnetic_activity_score": magnetic_score,
        "presence_of_moons_score": moons_score,
        "atmosphere_potential_desc": atmosphere_desc,
        "liquid_water_potential_desc": water_desc,
        "magnetic_activity_desc": magnetic_desc,
        "presence_of_moons_desc": moons_desc,
    }

def get_score_info(scores_dict, field_name):
    """Extracts score information from a scores dictionary.
    
    Args:
        scores_dict (dict): Dictionary of scores.
        field_name (str): Name of the field to extract.
    
    Returns:
        dict: Dictionary with score, color, and text.
    """
    default_numeric_score = 0.0
    default_color = "#808080"
    default_text = "N/A"

    if not isinstance(scores_dict, dict):
        logger.warning(f"scores_dict is not a dict for field '{field_name}'. Using default score info.")
        return {"score": default_numeric_score, "color": default_color, "text": default_text}
    
    # Verificar se o campo existe como objeto
    if isinstance(scores_dict.get(field_name), dict):
        score_dict = scores_dict.get(field_name)
        return {
            "score": score_dict.get("score", default_numeric_score),
            "color": score_dict.get("color", default_color),
            "text": score_dict.get("text", default_text)
        }
    
    # Verificar se o campo existe como tupla
    score_tuple = scores_dict.get(field_name)
    
    if not isinstance(score_tuple, tuple) or len(score_tuple) < 1 or pd.isna(score_tuple[0]):
        if not (isinstance(score_tuple, tuple) and len(score_tuple) >= 1 and pd.isna(score_tuple[0])):
            logger.debug(f"Invalid or missing score_tuple for field '{field_name}'. score_tuple: {score_tuple}. Using default score info.")
        return {"score": default_numeric_score, "color": default_color, "text": default_text}

    raw_score_value = score_tuple[0]
    numeric_val_for_format = default_numeric_score

    try:
        numeric_val_for_format = float(raw_score_value)
    except (ValueError, TypeError):
        logger.warning(f"Score value '{raw_score_value}' for field '{field_name}' is not a valid number. Defaulting numeric component to {default_numeric_score} for formatting.")
    
    color_val = default_color
    if len(score_tuple) > 1 and score_tuple[1] is not None and isinstance(score_tuple[1], str) and score_tuple[1].startswith("#"):
        color_val = score_tuple[1]
    else:
        color_val = get_color_for_percentage(numeric_val_for_format)

    text_val = str(raw_score_value)
    if len(score_tuple) > 2 and score_tuple[2] is not None and str(score_tuple[2]).strip():
        text_val = str(score_tuple[2])
    
    return {
        "score": numeric_val_for_format,
        "color": color_val,
        "text": text_val
    }


def _prepare_data_for_aggregated_reports(all_planets_report_data, output_dir):
    logger.info(f"Starting _prepare_data_for_aggregated_reports with {len(all_planets_report_data)} planets")
    
    # Salvar os dados de entrada para depuração
    debug_input_path = os.path.join(output_dir, "debug_input_all_planets_report_data_AGGREGATED_INPUT.json")
    try:
        with open(debug_input_path, "w", encoding="utf-8") as f_debug:
            json.dump(all_planets_report_data, f_debug, indent=2, default=str)
        logger.info(f"Saved input for _prepare_data_for_aggregated_reports to {debug_input_path}")
    except Exception as e_debug:
        logger.error(f"Could not save input for debugging: {e_debug}")

    def safe_get(dictionary, key, default="N/A"):
        if dictionary is None:
            return default
        value = dictionary.get(key)
        if pd.isna(value) or value is None or str(value).strip().lower() == "n/a":
            return default
        return value
    
    def find_key_insensitive(dictionary, target_key):
        if dictionary is None:
            return None
        for key in dictionary.keys():
            if key.lower() == target_key.lower():
                return dictionary[key]
        return None

    def get_score_info(scores_dict, field_name):
        default_numeric_score = 0.0
        default_color = "#808080"
        default_text = "N/A"

        if not isinstance(scores_dict, dict):
            logger.warning(f"scores_dict is not a dict for field '{field_name}'. Using default score info.")
            return {"score": default_numeric_score, "color": default_color, "text": default_text}
        
        score_tuple = scores_dict.get(field_name)
        
        if not isinstance(score_tuple, tuple) or len(score_tuple) < 1 or pd.isna(score_tuple[0]):
            if not (isinstance(score_tuple, tuple) and len(score_tuple) >= 1 and pd.isna(score_tuple[0])):
                logger.debug(f"Invalid or missing score_tuple for field '{field_name}'. score_tuple: {score_tuple}. Using default score info.")
            return {"score": default_numeric_score, "color": default_color, "text": default_text}

        raw_score_value = score_tuple[0]
        numeric_val_for_format = default_numeric_score

        try:
            numeric_val_for_format = float(raw_score_value)
        except (ValueError, TypeError):
            logger.warning(f"Score value '{raw_score_value}' for field '{field_name}' is not a valid number. Defaulting numeric component to {default_numeric_score} for formatting.")
        
        color_val = default_color
        if len(score_tuple) > 1 and score_tuple[1] is not None and isinstance(score_tuple[1], str) and score_tuple[1].startswith("#"):
            color_val = score_tuple[1]
        else:
            color_val = get_color_for_percentage(numeric_val_for_format)

        text_val = str(raw_score_value)
        if len(score_tuple) > 2 and score_tuple[2] is not None and str(score_tuple[2]).strip():
            text_val = str(score_tuple[2])
        
        return {
            "score": numeric_val_for_format,
            "color": color_val,
            "text": text_val
        }

    processed_data_list = []
    
    for p_data in all_planets_report_data:
        planet_raw_TAP_data = p_data.get("planet_data_dict", {})
        if not planet_raw_TAP_data:
            logger.warning("Skipping planet with no raw data dictionary")
            continue
        
        planet_name = safe_get(planet_raw_TAP_data, "pl_name", "Unknown Planet")
        planet_name_for_log = planet_name
        
        logger.info(f"Processing {planet_name_for_log} for aggregated reports")
        
        # Logar todas as chaves disponíveis em planet_raw_TAP_data para depuração
        logger.debug(f"Available keys in planet_raw_TAP_data for {planet_name_for_log}: {list(planet_raw_TAP_data.keys())}")
        
        # Obter scores e dados
        scores_processed = p_data.get("scores_for_report", {})
        sephi_processed = p_data.get("sephi_scores_for_report", {})
        hz_data_tuple_raw = p_data.get("hz_data_tuple")

        # Obter classificação
        classification_text = safe_get(planet_raw_TAP_data, "classification", "Unknown")
        if "classification_final_display" in planet_raw_TAP_data:
            classification_text = safe_get(planet_raw_TAP_data, "classification_final_display", classification_text)

        enriched_details = enrich_atmosphere_water_magnetic_moons(planet_raw_TAP_data, classification_text)

        # --- NOVO CÁLCULO PARA STELLAR ACTIVITY SCORE ---
        st_age_str = planet_raw_TAP_data.get("st_age")
        # Default para "Low" (atividade real alta, score de favorabilidade baixo = 30%)
        # se st_age não for fornecido, for inválido, ou <= 2 Gyr.
        stellar_activity_score_val = 30.0 
        stellar_activity_desc_for_log = "Low (default or <= 2 Gyr)"

        if st_age_str is not None:
            try:
                st_age_float = float(st_age_str)
                if st_age_float > 5: # Estrela mais velha -> atividade real BAIXA -> BOM -> Score Alto
                    stellar_activity_score_val = 90.0
                    stellar_activity_desc_for_log = "High (age > 5 Gyr)"
                elif st_age_float > 2: # Estrela meia-idade -> atividade real MODERADA -> OK -> Score Médio
                    stellar_activity_score_val = 60.0
                    stellar_activity_desc_for_log = "Moderate (age 2-5 Gyr)"
                # else: st_age_float <= 2 (Estrela jovem -> atividade real ALTA -> RUIM -> Score Baixo)
                # já coberto pelo default de 30.0
            except (ValueError, TypeError):
                logger.warning(f"Planet {planet_name_for_log}: Could not convert st_age '{st_age_str}' to float. Stellar Activity Score set to 30% (default for Low activity / unknown).")
                # stellar_activity_score_val já é 30.0 por default
        
        logger.debug(f"Planet {planet_name_for_log}: st_age='{st_age_str}', Stellar Activity Description (from logic): '{stellar_activity_desc_for_log}', Score: {stellar_activity_score_val}%")
        # --- FIM DO NOVO CÁLCULO ---

        # Preparar scores para o template
        scores_for_template = {
            "ESI": get_score_info(scores_processed, "ESI"),
            "SPH": get_score_info(scores_processed, "SPH"),
            "PHI": get_score_info(scores_processed, "PHI"),
            "Host_Star_Type": get_score_info(scores_processed, "Host Star Type"),
            "System_Age": get_score_info(scores_processed, "System Age"),
            # >>>>> MODIFICAÇÃO PARA STELLAR ACTIVITY <<<<<
            "Stellar_Activity": {
                # Supondo que 'stellar_activity_score' deve vir de planet_raw_TAP_data
                # Se precisar de uma descrição mais elaborada, você precisará de uma fonte para ela.
                "score": stellar_activity_score_val,
                "color": get_color_for_percentage(stellar_activity_score_val),
                "text": stellar_activity_desc_for_log, # Tenta pegar uma descrição se houver
            },   
            "Orbital_Eccentricity": get_score_info(scores_processed, "Orbital Eccentricity"),
            # >>>>> USAR enriched_details AQUI <<<<<
            "Atmosphere_Potential": {
                "score": np.clip(float(enriched_details.get("atmosphere_potential_score", 0.0)), 0, 100),
                "color": get_color_for_percentage(float(enriched_details.get("atmosphere_potential_score", 0.0))),
                "text": enriched_details.get("atmosphere_potential_desc", "N/A")
            },
            "Liquid_Water_Potential": {
                "score": np.clip(float(enriched_details.get("liquid_water_potential_score", 0.0)), 0, 100),
                "color": get_color_for_percentage(float(enriched_details.get("liquid_water_potential_score", 0.0))),
                "text": enriched_details.get("liquid_water_potential_desc", "N/A")
            },
            "Magnetic_Activity": {
                "score": np.clip(float(enriched_details.get("magnetic_activity_score", 0.0)), 0, 100),
                "color": get_color_for_percentage(float(enriched_details.get("magnetic_activity_score", 0.0))),
                "text": enriched_details.get("magnetic_activity_desc", "N/A") 
            },
            "Presence_of_Moons": {
                "score": np.clip(float(enriched_details.get("presence_of_moons_score", 0.0)), 0, 100),
                "color": get_color_for_percentage(float(enriched_details.get("presence_of_moons_score", 0.0))),
                "text": enriched_details.get("presence_of_moons_desc", "N/A")
            },
            "Magnetic_Activity": get_score_info(scores_processed, "Magnetic Activity"),
            "Habitable_Zone_Position": get_score_info(scores_processed, "Habitable Zone Position"),
            "Temperature": get_score_description(scores_processed, "Temperature", classification_text),
            "Bio Potential": get_score_description_bio(scores_processed, "Bio Potential", planet_raw_TAP_data.get("pl_eqt")),
            "Presence of Moons": get_score_description_moons(scores_processed, "Presence of Moons", classification_text, planet_raw_TAP_data),
            "Size": get_score_info(scores_processed, "Size"),
            "Density": get_score_info(scores_processed, "Density"),
            "Mass": get_score_info(scores_processed, "Mass"),
            "Star_Metallicity": get_score_info(scores_processed, "Star Metallicity")
        }

        # Preparar scores SEPHI
        sephi_scores_for_template = {
            "SEPHI": {"score": 0.0, "color": "#808080", "text": "N/A"},
            "SEPHI_L1": {"score": 0.0, "color": "#808080", "text": "N/A"},
            "SEPHI_L2": {"score": 0.0, "color": "#808080", "text": "N/A"},
            "SEPHI_L3": {"score": 0.0, "color": "#808080", "text": "N/A"},
            "SEPHI_L4": {"score": 0.0, "color": "#808080", "text": "N/A"}
        }
        
        if isinstance(sephi_processed, dict):
            for key, display_key in [
                ("SEPHI", "SEPHI"),
                ("L1 (Surface)", "SEPHI_L1"),
                ("L2 (Escape Velocity)", "SEPHI_L2"),
                ("L3 (Habitable Zone)", "SEPHI_L3"),
                ("L4 (Magnetic Field)", "SEPHI_L4")
            ]:
                if key in sephi_processed and isinstance(sephi_processed[key], (list, tuple)) and len(sephi_processed[key]) >= 1:
                    try:
                        score = float(sephi_processed[key][0])
                        color = sephi_processed[key][1] if len(sephi_processed[key]) > 1 and isinstance(sephi_processed[key][1], str) else get_color_for_percentage(score)
                        text = str(score) if len(sephi_processed[key]) <= 2 else str(sephi_processed[key][2])
                        sephi_scores_for_template[display_key] = {
                            "score": score,
                            "color": color,
                            "text": text
                        }
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error processing SEPHI score for {key} in planet {planet_name_for_log}: {e}")

        # Calcular Habitability Score
        components = [
            scores_for_template["Temperature"]["score"],
            scores_for_template["Bio Potential"]["score"],
            scores_for_template["Magnetic_Activity"]["score"],
            scores_for_template["System_Age"]["score"],
            scores_for_template["Presence of Moons"]["score"],
            scores_for_template["Size"]["score"],
            scores_for_template["Density"]["score"]
        ]
        habitability_score_value = 0.0
        if components:
            habitability_score_value = np.power(np.prod([max(1e-10, c) for c in components]), 1/7)
            habitability_score_value = np.clip(habitability_score_value, 0, 100)
        else:
            logger.warning(f"No components available to calculate Habitability Score for {planet_name_for_log}. Set to 0.")

        scores_for_template["Habitability"] = {
            "score": habitability_score_value,
            "color": get_color_for_percentage(habitability_score_value),
            "text": "Overall Habitability Score"
        }

        is_warm_classified = "Warm" in classification_text
        if is_warm_classified and ("Terran" in classification_text or "Superterran" in classification_text):
            habitability_score_value = min(habitability_score_value + 10, 100)
        
        habitability_score_value = np.clip(habitability_score_value, 0, 100)
        scores_for_template["Habitability"] = {
            "score": habitability_score_value,
            "color": get_color_for_percentage(habitability_score_value),
            "text": "Overall Habitability Score"
        }

        # Calcular informações de viagem
        sy_dist_pc = planet_raw_TAP_data.get("sy_dist")
        distance_ly_str = "N/A"
        travel_details = {
            "distance_ly": "N/A",
            "current_tech_years": "N/A",
            "twenty_ls_years": "N/A",
            "near_ls_years": "N/A"
        }
        if pd.notna(sy_dist_pc):
            try:
                dist_ly_f = float(str(sy_dist_pc)) * 3.26156
                distance_ly_str = f"{dist_ly_f:.2f}"
                travel_details["distance_ly"] = distance_ly_str
                travel_details["current_tech_years"] = f"{dist_ly_f * (299792.458 / 170) / 1000:.1f} thousand years"
                travel_details["twenty_ls_years"] = f"{dist_ly_f / 0.2:.1f} years"
                travel_details["near_ls_years"] = f"{dist_ly_f / 0.99:.1f} years"
            except (ValueError, TypeError):
                logger.warning(f"Could not calculate travel times for {planet_name_for_log} due to distance conversion error for sy_dist: {sy_dist_pc}")

        # Obter descrição da zona habitável
        hz_description = "N/A"
        if hz_data_tuple_raw and len(hz_data_tuple_raw) > 4 and pd.notna(hz_data_tuple_raw[4]):
            hz_description = str(hz_data_tuple_raw[4])

        # Calcular gravidade superficial
        surface_gravity_value_str = "N/A"
        raw_pl_grav = planet_raw_TAP_data.get("pl_grav")
        if pd.notna(raw_pl_grav):
            surface_gravity_value_str = format_float_field(raw_pl_grav, ".2f")
        else:
            raw_pl_masse = planet_raw_TAP_data.get("pl_masse")
            if not pd.notna(raw_pl_masse):
                raw_pl_masse = planet_raw_TAP_data.get("pl_bmassj")
            raw_pl_rade = planet_raw_TAP_data.get("pl_rade")
            if pd.notna(raw_pl_masse) and pd.notna(raw_pl_rade):
                try:
                    mass_earth_str = str(raw_pl_masse)
                    if mass_earth_str.startswith("<"):
                        mass_earth_str = mass_earth_str.lstrip("<")
                    mass_earth = float(mass_earth_str)
                    radius_earth = float(str(raw_pl_rade))
                    if radius_earth > 0:
                        calculated_gravity = mass_earth / (radius_earth ** 2)
                        surface_gravity_value_str = format_float_field(calculated_gravity, ".2f")
                        logger.info(f"Calculated surface gravity for {planet_name_for_log}: {surface_gravity_value_str} g (M={mass_earth} M⊕, R={radius_earth} R⊕)")
                    else:
                        logger.warning(f"Cannot calculate surface gravity for {planet_name_for_log}: radius is zero or invalid ({radius_earth}).")
                except (ValueError, TypeError) as e_calc:
                    logger.warning(f"Could not convert mass ('{raw_pl_masse}') or radius ('{raw_pl_rade}') to float for surface gravity calculation for {planet_name_for_log}. Error: {e_calc}")

        # Adicionar dados de descoberta
        discovery_method = find_key_insensitive(planet_raw_TAP_data, "discoverymethod")
        if discovery_method is None or pd.isna(discovery_method) or str(discovery_method).strip().lower() == "n/a":
            discovery_method = find_key_insensitive(planet_raw_TAP_data, "disc_method")
        discovery_method = discovery_method if discovery_method is not None and not pd.isna(discovery_method) and str(discovery_method).strip().lower() != "n/a" else "N/A"
        method_map = {
            "tran": "Transit",
            "rv": "Radial Velocity",
            "ima": "Imaging",
            "micro": "Microlensing",
            "ttv": "Transit Timing Variations",
            "ast": "Astrometry",
            "dkin": "Disk Kinematics",
            "etv": "Eclipse Timing Variations"
        }
        discovery_method = method_map.get(discovery_method.lower(), discovery_method)
        logger.debug(f"Planet {planet_name_for_log}: Discovery Method - NASA (discoverymethod): {planet_raw_TAP_data.get('discoverymethod')}, NASA (disc_method): {planet_raw_TAP_data.get('disc_method')}, Selected: {discovery_method}")

        discovery_year = find_key_insensitive(planet_raw_TAP_data, "disc_year")
        discovery_year = discovery_year if discovery_year is not None and not pd.isna(discovery_year) and str(discovery_year).strip().lower() != "n/a" else "N/A"
        logger.debug(f"Planet {planet_name_for_log}: Discovery Year - NASA (disc_year): {planet_raw_TAP_data.get('disc_year')}, Selected: {discovery_year}")

        discovery_facility = find_key_insensitive(planet_raw_TAP_data, "disc_facility")
        if discovery_facility is None or pd.isna(discovery_facility) or str(discovery_facility).strip().lower() == "n/a":
            discovery_facility = find_key_insensitive(planet_raw_TAP_data, "disc_instrument")
        discovery_facility = discovery_facility if discovery_facility is not None and not pd.isna(discovery_facility) and str(discovery_facility).strip().lower() != "n/a" else "N/A"
        logger.debug(f"Planet {planet_name_for_log}: Discovery Instrument - NASA (disc_instrument): {planet_raw_TAP_data.get('disc_instrument')}, Selected: {discovery_facility}")

        discovery_telescope = find_key_insensitive(planet_raw_TAP_data, "disc_telescope")
        discovery_telescope = discovery_telescope if discovery_telescope is not None and not pd.isna(discovery_telescope) and str(discovery_telescope).strip().lower() != "n/a" else "N/A"
        logger.debug(f"Planet {planet_name_for_log}: Discovery Telescope - NASA (disc_telescope): {planet_raw_TAP_data.get('disc_telescope')}, Selected: {discovery_telescope}")

        # Adicionar dados de localização
        x_pixel_ra = find_key_insensitive(planet_raw_TAP_data, "S_RA")
        if x_pixel_ra is None or pd.isna(x_pixel_ra) or str(x_pixel_ra).strip().lower() == "n/a":
            x_pixel_ra = find_key_insensitive(planet_raw_TAP_data, "ra")
        x_pixel_ra = x_pixel_ra if x_pixel_ra is not None and not pd.isna(x_pixel_ra) and str(x_pixel_ra).strip().lower() != "n/a" else "N/A"

        y_pixel_dec = find_key_insensitive(planet_raw_TAP_data, "S_DEC")
        if y_pixel_dec is None or pd.isna(y_pixel_dec) or str(y_pixel_dec).strip().lower() == "n/a":
            y_pixel_dec = find_key_insensitive(planet_raw_TAP_data, "dec")
        y_pixel_dec = y_pixel_dec if y_pixel_dec is not None and not pd.isna(y_pixel_dec) and str(y_pixel_dec).strip().lower() != "n/a" else "N/A"

        right_ascension = find_key_insensitive(planet_raw_TAP_data, "S_RA_STR")
        if right_ascension is None or pd.isna(right_ascension) or str(right_ascension).strip().lower() == "n/a":
            right_ascension = find_key_insensitive(planet_raw_TAP_data, "rastr")
        right_ascension = right_ascension if right_ascension is not None and not pd.isna(right_ascension) and str(right_ascension).strip().lower() != "n/a" else "N/A"

        declination = find_key_insensitive(planet_raw_TAP_data, "S_DEC_STR")
        if declination is None or pd.isna(declination) or str(declination).strip().lower() == "n/a":
            declination = find_key_insensitive(planet_raw_TAP_data, "decstr")
        declination = declination if declination is not None and not pd.isna(declination) and str(declination).strip().lower() != "n/a" else "N/A"

        # Preparar star_info com constelação
        star_info = {
            "temperature_k": format_float_field(planet_raw_TAP_data.get("st_teff"), ".0f"),
            "radius_solar": format_float_field(planet_raw_TAP_data.get("st_rad")),
            "mass_solar": format_float_field(planet_raw_TAP_data.get("st_mass")),
            "luminosity_log_solar": format_float_field(planet_raw_TAP_data.get("st_lum")),
            "age_gyr": format_float_field(planet_raw_TAP_data.get("st_age")),
            "metallicity_dex": format_float_field(planet_raw_TAP_data.get("st_metfe")),
            "constellation": find_key_insensitive(planet_raw_TAP_data, "S_CONSTELLATION") or "N/A"
        }
        sy_dist_pc = planet_raw_TAP_data.get("sy_dist")
        if pd.notna(sy_dist_pc):
            try:
                star_info["distance_ly"] = f"{float(str(sy_dist_pc)) * 3.26156:.2f}"
            except (ValueError, TypeError):
                star_info["distance_ly"] = "N/A"
        else:
            star_info["distance_ly"] = "N/A"

        # Preparar dados para o template
        data_for_template = {
            "planet_name": planet_raw_TAP_data.get("pl_name", "N/A"),
            "classification": classification_text,
            "star_type": planet_raw_TAP_data.get("st_spectype", "N/A"),
            "distance_light_years": distance_ly_str,
            "equilibrium_temp_k": format_float_field(planet_raw_TAP_data.get("pl_eqt"), ".0f"),
            "planet_radius_earth": format_float_field(planet_raw_TAP_data.get("pl_rade")),
            "planet_mass_earth": format_float_field(planet_raw_TAP_data.get("pl_bmassj") if pd.notna(planet_raw_TAP_data.get("pl_bmassj")) else planet_raw_TAP_data.get("pl_masse"), ".2f"),
            "planet_density_gcm3": format_float_field(planet_raw_TAP_data.get("pl_dens")),
            "surface_gravity_g": surface_gravity_value_str,
            "orbital_period_days": format_float_field(planet_raw_TAP_data.get("pl_orbper")),
            "semi_major_axis_au": format_float_field(planet_raw_TAP_data.get("pl_orbsmax")),
            "eccentricity": format_float_field(planet_raw_TAP_data.get("pl_orbeccen")),
            "travel_curiosities": travel_details,
            "habitable_zone_description": hz_description,
            "scores": scores_for_template,
            "sephi_scores": sephi_scores_for_template,
            "star_info": star_info,
            "magnetic_activity_score": enriched_details.get("magnetic_activity_score", 0.0),
            "presence_of_moons_score": enriched_details.get("presence_of_moons_score", 0.0),
            "atmosphere_potential_desc": enriched_details.get("atmosphere_potential_desc", "N/A"),
            "liquid_water_potential_desc": enriched_details.get("liquid_water_potential_desc", "N/A"),
            "magnetic_activity_desc": enriched_details.get("magnetic_activity_desc", "N/A"),
            "presence_of_moons_desc": enriched_details.get("presence_of_moons_desc", "N/A"),
            "discovery_method": discovery_method,
            "discovery_year": discovery_year,
            "discovery_facility": discovery_facility,
            "discovery_telescope": discovery_telescope,
            "x_pixel_ra": format_float_field(x_pixel_ra, ".5f"),
            "y_pixel_dec": format_float_field(y_pixel_dec, ".5f"),
            "right_ascension": right_ascension,
            "declination": declination
        }
        
        processed_data_list.append(data_for_template)

    if not processed_data_list:
        logger.warning("No data processed for summary/combined report (processed_data_list is empty).")
        return []
        
    debug_output_path = os.path.join(output_dir, "debug_output_processed_planets_data.json")
    try:
        with open(debug_output_path, "w", encoding="utf-8") as f_debug:
            json.dump(processed_data_list, f_debug, indent=2, default=str)
        logger.info(f"Saved processed_planets_data for debugging to {debug_output_path}")
    except Exception as e_debug:
        logger.error(f"Could not save processed_planets_data for debugging: {e_debug}")

    return processed_data_list

def generate_summary_report_html(all_planets_report_data, template_env, output_dir):
    """Generates a summary HTML report for multiple planets.
    
    Uses the `_prepare_data_for_aggregated_reports` function to process the input data
    and then renders it using the "summary_template.html" Jinja2 template.
    If an error occurs during generation, it attempts to create an error report.
    
    Args:
        all_planets_report_data (list): A list of dictionaries, each containing
                                        processed data for a single planet.
        template_env (jinja2.Environment): The Jinja2 template environment.
        output_dir (str): The directory where the HTML report will be saved.
    
    Returns:
        str or None: The full path to the generated summary HTML report file.
                     Returns path to an error report if main generation fails,
                     or None if error report also fails.
    """
    logger = logging.getLogger(__name__)
    
    # Função auxiliar para garantir que o diretório exista
    def ensure_dir(directory):
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")
    
    ensure_dir(output_dir)
    report_filename = "summary_report.html"
    full_report_path = os.path.join(output_dir, report_filename)
    logger.info(f"Generating summary report to {full_report_path}")
    
    try:
        template = template_env.get_template("summary_template.html")
        
        # Usar a versão corrigida da função de preparação de dados
        processed_planets_data = _prepare_data_for_aggregated_reports(all_planets_report_data, output_dir)
        
        if not processed_planets_data:
            logger.warning("No processed data available for summary report. Creating empty report.")
            # Criar um relatório vazio em vez de retornar None
            processed_planets_data = []
        
        context = {"all_planets_data": processed_planets_data, "datetime": datetime}
        html_content = template.render(context)
        
        with open(full_report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"Summary report saved to {full_report_path}")
        return full_report_path
    
    except Exception as e:
        logger.error(f"Error generating summary report: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        
        # Criar um relatório de erro em vez de retornar None
        try:
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Summary Report Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .error {{ color: red; background-color: #ffeeee; padding: 10px; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <h1>Summary Report Error</h1>
                <div class="error">
                    <p>An error occurred while generating the summary report:</p>
                    <pre>{str(e)}</pre>
                </div>
                <p>Please try again or contact support if the problem persists.</p>
                <p>Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </body>
            </html>
            """
            with open(full_report_path, "w", encoding="utf-8") as f:
                f.write(error_html)
            logger.info(f"Error summary report saved to {full_report_path}")
            return full_report_path
        except Exception as e2:
            logger.error(f"Failed to create error report: {e2}")
            return None


def generate_combined_report_html(all_planets_report_data, template_env, output_dir):
    """Generates a combined HTML report providing detailed comparisons for multiple planets.
    
    Similar to the summary report, it uses `_prepare_data_for_aggregated_reports`
    to process input data and then renders it using the "combined_template.html"
    Jinja2 template.
    If an error occurs, it attempts to create an error report.
    
    Args:
        all_planets_report_data (list): A list of dictionaries, each containing
                                        processed data for a single planet.
        template_env (jinja2.Environment): The Jinja2 template environment.
        output_dir (str): The directory where the HTML report will be saved.
    
    Returns:
        str or None: The full path to the generated combined HTML report file.
                     Returns path to an error report if main generation fails,
                     or None if error report also fails.
    """
    logger = logging.getLogger(__name__)
    
    # Função auxiliar para garantir que o diretório exista
    def ensure_dir(directory):
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")
    
    ensure_dir(output_dir)
    report_filename = "combined_report.html"
    full_report_path = os.path.join(output_dir, report_filename)
    logger.info(f"Generating combined report to {full_report_path}")
    
    try:
        template = template_env.get_template("combined_template.html")
        
        # Usar a versão corrigida da função de preparação de dados
        processed_planets_data = _prepare_data_for_aggregated_reports(all_planets_report_data, output_dir)
        
        if not processed_planets_data:
            logger.warning("No processed data available for combined report. Creating empty report.")
            # Criar um relatório vazio em vez de retornar None
            processed_planets_data = []
        
        context = {"all_planets_data": processed_planets_data, "datetime": datetime}
        html_content = template.render(context)
        
        with open(full_report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"Combined report saved to {full_report_path}")
        return full_report_path
    
    except Exception as e:
        logger.error(f"Error generating combined report: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        
        # Criar um relatório de erro em vez de retornar None
        try:
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Combined Report Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .error {{ color: red; background-color: #ffeeee; padding: 10px; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <h1>Combined Report Error</h1>
                <div class="error">
                    <p>An error occurred while generating the combined report:</p>
                    <pre>{str(e)}</pre>
                </div>
                <p>Please try again or contact support if the problem persists.</p>
                <p>Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </body>
            </html>
            """
            with open(full_report_path, "w", encoding="utf-8") as f:
                f.write(error_html)
            logger.info(f"Error combined report saved to {full_report_path}")
            return full_report_path
        except Exception as e2:
            logger.error(f"Failed to create error report: {e2}")
            return None

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir) 
    templates_dir = os.path.join(project_root, "app", "templates")
    
    if not os.path.exists(templates_dir):
        templates_dir = os.path.join(script_dir, "..", "app", "templates") 
    if not os.path.exists(templates_dir):
        templates_dir = os.path.join(script_dir, "app", "templates") 
    if not os.path.exists(templates_dir):
        alt_templates_dir = os.path.join(script_dir, "templates")
        if os.path.exists(alt_templates_dir):
            templates_dir = alt_templates_dir
        else:
            logger.error(f"Could not find templates directory. Tried various paths including {alt_templates_dir}")
            exit(1)

    logger.info(f"Using templates directory: {templates_dir}")
    template_env = Environment(loader=FileSystemLoader(templates_dir), autoescape=select_autoescape(["html", "xml"])) # Added autoescape
    test_output_dir = os.path.join(script_dir, "test_reports_output")
    ensure_dir(test_output_dir)

    # Dummy data structure should mimic what routes.py passes to generate_summary/combined_report_html
    # which is a list of `processed_result` dicts from `process_planet_data`
    dummy_all_planets_data_from_routes = [
        {
            # This inner structure should match the output of `process_planet_data`
            "planet_data_dict": {
                "pl_name": "Test Planet Alpha", "hostname": "Test Star A", "st_spectype": "G2V",
                "sy_dist": 10.0, "st_teff": 5800, "st_rad": 1.0, "st_lum": 0.0,
                "pl_orbsmax": 1.0, "pl_orbper": 365.0, "pl_orbeccen": 0.01, "pl_orbincl": 90.0,
                "pl_rade": 1.0, "pl_masse": 1.0, "pl_dens": 5.51, "pl_eqt": 288, "pl_grav": 1.0,
                "classification_final_display": "Mesoplanet", "pl_name_display": "Test Planet Alpha"
            },
            "scores_for_report": { # This key is used by _prepare_data_for_aggregated_reports (stable version)
                "ESI": (85.0, get_color_for_percentage(85.0), "High Earth Similarity"),
                "PHI": (70.0, get_color_for_percentage(70.0), "Moderate PHI"),
                "SPH": (75.0, get_color_for_percentage(75.0), "Good SPH"),
                "Habitability Score": (9200.0, get_color_for_percentage(92.0), "Very Habitable (Test Inflated)"), # Test inflated score
                "Host Star Type": (100.0, get_color_for_percentage(100.0), "G-type Star"),
                "System Age": (80.0, get_color_for_percentage(80.0), "Optimal Age"),
                "Stellar Activity": (70.0, get_color_for_percentage(70.0), "Low Activity"),
                "Orbital Eccentricity": (95.0, get_color_for_percentage(95.0), "Near Circular"),
                "Atmosphere Potential": (75.0, get_color_for_percentage(75.0), "Good Potential"),
                "Liquid Water Potential": (88.0, get_color_for_percentage(88.0), "High Potential"),
                "Magnetic Activity": (60.0, get_color_for_percentage(60.0), "Moderate Field"),
                "Presence of Moons": (50.0, get_color_for_percentage(50.0), "Possible Moons (Placeholder)"),
                "Habitable Zone Position": (90.0, get_color_for_percentage(90.0), "Well within HZ"),
                "Size": (98.0, get_color_for_percentage(98.0), "Earth-sized"),
                "Density": (96.0, get_color_for_percentage(96.0), "Earth-like Density"),
                "Mass": (97.0, get_color_for_percentage(97.0), "Earth-like Mass"),
                "Star Metallicity": (70.0, get_color_for_percentage(70.0), "Solar Metallicity")
            },
            "sephi_scores_for_report": { # This key is used by _prepare_data_for_aggregated_reports (stable version)
                "SEPHI": (80.0, get_color_for_percentage(80.0), "High SEPHI"), 
                "L1 (Surface)": (85.0, get_color_for_percentage(85.0), "L1 Desc"),
                "L2 (Escape Velocity)": (75.0, get_color_for_percentage(75.0), "L2 Desc"),
                "L3 (Habitable Zone)": (90.0, get_color_for_percentage(90.0), "L3 Desc"),
                "L4 (Magnetic Field)": (70.0, get_color_for_percentage(70.0), "L4 Desc")
            },
            "hz_data_tuple": (0.8, 0.9, 1.5, 1.6, "In Conservative Habitable Zone"),
            # Other keys from process_planet_data like pl_name_display, classification_final_display etc.
            # are often directly within planet_data_dict or at the top level of processed_result.
            # For this test, we assume they are accessible as needed or within planet_data_dict.
        },
        {
            "planet_data_dict": {
                "pl_name": "Test Planet Beta", "hostname": "Test Star B", "st_spectype": "M5V",
                "sy_dist": 50.0, "st_teff": 3200, "st_rad": 0.5, "st_lum": -1.5,
                "pl_orbsmax": 0.1, "pl_orbper": 10.0, "pl_orbeccen": 0.2, "pl_orbincl": 89.5,
                "pl_rade": 1.5, "pl_masse": 3.0, "pl_dens": 4.0, "pl_eqt": 200, "pl_grav": 1.2,
                "classification_final_display": "Superterran", "pl_name_display": "Test Planet Beta"
            },
            "scores_for_report": {
                "ESI": (50.0, get_color_for_percentage(50.0), "Corrected ESI Example"), 
                "PHI": (40.0, get_color_for_percentage(40.0), "Low PHI"),
                "Habitability Score": (30.0, get_color_for_percentage(30.0), "Low Habitability"),
                "Host Star Type": (60.0, get_color_for_percentage(60.0), "M-type Star"),
                "System Age": (50.0, get_color_for_percentage(50.0), "Moderate Age"),
                "Presence of Moons": (10.0, get_color_for_percentage(10.0), "Unlikely Moons (Placeholder)"),
                "Size": (70.0, get_color_for_percentage(70.0), "Super-Earth size")
            },
            "sephi_scores_for_report": {
                "SEPHI": (30.0, get_color_for_percentage(30.0), "Low SEPHI"),
                "L1 (Surface)": (25.0, get_color_for_percentage(25.0), "L1 Desc Beta")
            },
            "hz_data_tuple": (0.05, 0.08, 0.15, 0.2, "Outer Edge of Optimistic HZ"),
        }
    ]

    # Test individual reports (simplified, assuming plots are handled)
    for planet_bundle_from_routes in dummy_all_planets_data_from_routes:
        planet_name_s = planet_bundle_from_routes["planet_data_dict"]["pl_name"].lower().replace(" ", "_")
        # In a real scenario, plots would be generated based on data within planet_bundle_from_routes
        dummy_plots_for_individual = {}
        
        generate_planet_report_html(
            planet_bundle_from_routes["planet_data_dict"], # Pass the core planet data
            planet_bundle_from_routes["scores_for_report"], # Pass scores
            planet_bundle_from_routes["sephi_scores_for_report"], # Pass SEPHI scores
            dummy_plots_for_individual, 
            template_env,
            test_output_dir,
            planet_name_s
        )

    summary_report_path = generate_summary_report_html(dummy_all_planets_data_from_routes, template_env, test_output_dir)
    if summary_report_path:
        logger.info(f"Test Summary report generated at: {summary_report_path}")

    combined_report_path = generate_combined_report_html(dummy_all_planets_data_from_routes, template_env, test_output_dir)
    if combined_report_path:
        logger.info(f"Test Combined report generated at: {combined_report_path}")

    logger.info("Test script finished. Check \"test_reports_output\" directory.")

