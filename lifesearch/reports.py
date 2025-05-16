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

logger = logging.getLogger(__name__)

# Helper function to create output directories if they don"t exist
def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def get_color_for_percentage(percentage):
    """Helper function to determine color based on percentage for reports."""
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
    if pd.isna(value) or value == "N/A" or str(value).strip() == "":
        return "N/A"
    try:
        return f"{float(str(value)):{precision}}"
    except (ValueError, TypeError):
        return str(value)  # Return as string if conversion fails

# --- Plotting Functions ---
def plot_habitable_zone(planet_data, star_data, hz_limits, output_path, planet_name_slug):
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
            ax.plot(pl_orbsmax_fl, 0, "o", markersize=10, color="blue", label=f"{planet_data.get("pl_name", planet_name_slug)} ({pl_orbsmax_fl:.2f} AU)")
        else:
            logger.warning(f"Orbital semi-major axis (pl_orbsmax) not available or not float for {planet_name_slug}.")

        ax.set_yticks([])
        ax.set_xlabel("Distance from Star (AU)")
        ax.set_title(f"Habitable Zone for {planet_data.get("pl_name", planet_name_slug)}")
        
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
    radius_str = data.get("pl_rade")
    mass, radius = None, None

    if mass_str is not None:
        try: mass = float(mass_str)
        except (ValueError, TypeError): pass
    
    if radius_str is not None:
        try: radius = float(radius_str)
        except (ValueError, TypeError): pass

    if mass is None and radius is not None:
        try:
            if radius < 1.5:
                mass = radius ** 2.06
            else:
                mass = radius ** 0.59
        except Exception:
            mass = None # Mantém mass como None se houver erro no cálculo
            
    st_spectype = data.get("st_spectype", "")
    magnetic_score = 60 # Default

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

def _prepare_data_for_aggregated_reports(all_planets_report_data, output_dir_for_debug_json):
    logger.info(f"Starting _prepare_data_for_aggregated_reports with {len(all_planets_report_data)} planets.")
    
    # This function now expects `all_planets_report_data` to be a list of dictionaries,
    # where each dictionary is the `processed_result` from `process_planet_data` (via app/routes.py)
    # This `processed_result` (now `p_data` in the loop) should contain:
    # - "planet_data_dict": The core data for the planet.
    # - "scores_for_report": Calculated habitability scores.
    # - "sephi_scores_for_report": Calculated SEPHI scores.
    # - "hz_data_tuple": Habitable zone data.

    debug_file_path = os.path.join(output_dir_for_debug_json, "debug_input_all_planets_report_data_AGGREGATED_INPUT.json")
    try:
        with open(debug_file_path, "w", encoding="utf-8") as f_debug:
            json.dump(all_planets_report_data, f_debug, indent=2, default=str) 
        logger.info(f"Saved all_planets_report_data (input to _prepare_data) for debugging to {debug_file_path}")
    except Exception as e_debug:
        logger.error(f"Could not save all_planets_report_data for debugging: {e_debug}")

    processed_data_list = []
    for i, p_data in enumerate(all_planets_report_data):
        # ALIGNMENT WITH STABLE VERSION:
        # Extract data using keys consistent with the stable version"s `processed_result` structure
        planet_raw_TAP_data = p_data.get("planet_data_dict", {}) 
        scores_processed = p_data.get("scores_for_report", {}) 
        sephi_processed = p_data.get("sephi_scores_for_report", {})
        hz_data_tuple_raw = p_data.get("hz_data_tuple", (None, None, None, None, None))

        
        planet_name_for_log = planet_raw_TAP_data.get("pl_name", p_data.get("pl_name_display", "Unknown"))
        logger.info(f"Processing planet {i+1}/{len(all_planets_report_data)} for aggregated report: {planet_name_for_log}")

        classification_text = planet_raw_TAP_data.get("classification_final_display", planet_raw_TAP_data.get("classification", "N/A"))
        extra_fields = enrich_atmosphere_water_magnetic_moons(planet_raw_TAP_data, classification_text)
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

        def get_score_info(score_source_dict, key, default_percentage=0.0):
            val_tuple = score_source_dict.get(key)
            score_percentage_for_display = default_percentage 
            color_val = get_color_for_percentage(default_percentage)
            text_desc = "N/A"
            

            raw_value_from_input = None
            input_color = None
            input_text_desc = None

            if val_tuple is not None:
                if isinstance(val_tuple, (list, tuple)) and len(val_tuple) > 0 and pd.notna(val_tuple[0]):
                    raw_value_from_input = val_tuple[0]
                    if len(val_tuple) > 1 and pd.notna(val_tuple[1]): input_color = val_tuple[1]
                    if len(val_tuple) > 2 and pd.notna(val_tuple[2]): input_text_desc = str(val_tuple[2])
                elif pd.notna(val_tuple): 
                    raw_value_from_input = val_tuple
            
            if raw_value_from_input is not None:
                try:
                    current_score_val = float(raw_value_from_input)
                    # Heuristic to correct potentially 100x inflated scores (only if they are way off)
                    if abs(current_score_val) > 100.5 and abs(current_score_val) <= 10050: # e.g. 5000% for 50%
                        potential_corrected_score = current_score_val / 100.0
                        # Only apply correction if it brings it into a reasonable 0-100 range
                        if 0 <= abs(potential_corrected_score) <= 100.5: 
                            current_score_val = potential_corrected_score
                            logger.info(f"Planet {planet_name_for_log}: Score {key} ({raw_value_from_input}) seemed 100x inflated, corrected to {current_score_val}%.")
                    
                    score_percentage_for_display = np.clip(current_score_val, 0, 100) # Ensure it's within 0-100
                    color_val = input_color if input_color is not None else get_color_for_percentage(score_percentage_for_display)
                    text_desc = input_text_desc if input_text_desc is not None else "N/A"
                        
                except (ValueError, TypeError):
                    logger.warning(f"Planet {planet_name_for_log}: Could not convert score value for {key}: {raw_value_from_input}. Using default {default_percentage}%.")
                    score_percentage_for_display = default_percentage
                    color_val = get_color_for_percentage(default_percentage)
                    text_desc = "N/A"
            else: # val_tuple is None or first element is NaN
                score_percentage_for_display = default_percentage
                color_val = get_color_for_percentage(default_percentage)
                text_desc = "N/A"

            return {"score": score_percentage_for_display, "color": color_val, "text": text_desc}

        scores_for_template = {
            "ESI": get_score_info(scores_processed, "ESI"),
            "PHI": get_score_info(scores_processed, "PHI"),
            "SPH": get_score_info(scores_processed, "SPH", 0.0),
            "Habitability": get_score_info(scores_processed, "Habitability Score", 0.0),
            "Host_Star_Type": get_score_info(scores_processed, "Host Star Type"),
            "System_Age": get_score_info(scores_processed, "System Age"),
            "Stellar_Activity": {  # Nova lógica integrada
                "score": stellar_activity_score_val,
                "color": get_color_for_percentage(stellar_activity_score_val),
                "text": "N/A" # O template não parece usar 'text' para este score específico
            },            
            "Orbital_Eccentricity": get_score_info(scores_processed, "Orbital Eccentricity"),
            "Atmosphere_Potential": get_score_info(scores_processed, "Atmosphere Potential"),
            "Liquid_Water_Potential": get_score_info(scores_processed, "Liquid Water Potential"),
                            # --- INÍCIO DA CORREÇÃO 1 ---
            "Magnetic_Activity": {
            "score": np.clip(float(extra_fields.get("magnetic_activity_score", 0.0)), 0, 100),
            "color": get_color_for_percentage(float(extra_fields.get("magnetic_activity_score", 0.0))),
        # O template combined_template não usa 'text' para estes, mas é bom ter para consistência
            "text": extra_fields.get("magnetic_activity_desc", "N/A") 
            },
            "Presence_of_Moons": {
            "score": np.clip(float(extra_fields.get("presence_of_moons_score", 0.0)), 0, 100),
            "color": get_color_for_percentage(float(extra_fields.get("presence_of_moons_score", 0.0))),
            "text": extra_fields.get("presence_of_moons_desc", "N/A")
            },
    # --- FIM DA CORREÇÃO 1 ---
            "Habitable_Zone_Position": get_score_info(scores_processed, "Habitable Zone Position"),
            "Size": get_score_info(scores_processed, "Size"),
            "Density": get_score_info(scores_processed, "Density"),
            "Mass": get_score_info(scores_processed, "Mass"),
            "Star_Metallicity": get_score_info(scores_processed, "Star Metallicity")

        }
        
        # ALIGNMENT WITH STABLE VERSION for SEPHI keys:
        sephi_scores_for_template = {
            "SEPHI": get_score_info(sephi_processed, "SEPHI"),
            "SEPHI_L1": get_score_info(sephi_processed, "L1 (Surface)"), # Changed from "SEPHI L1 (Surface)"
            "SEPHI_L2": get_score_info(sephi_processed, "L2 (Escape Velocity)"), # Changed from "SEPHI L2 (Escape Vel.)"
            "SEPHI_L3": get_score_info(sephi_processed, "L3 (Habitable Zone)"), # Changed from "SEPHI L3 (HZ)"
            "SEPHI_L4": get_score_info(sephi_processed, "L4 (Magnetic Field)") # Changed from "SEPHI L4 (Mag. Field)"
        }
        # --- INÍCIO DO CÁLCULO DO NOVO HABITABILITY SCORE ---
        is_habitable_candidate = False
        if any(term in classification_text for term in ["Mini-Terran", "Terran", "Superterran"]):
            is_habitable_candidate = True

        components_for_average = []

        # Adiciona scores sempre incluídos
        components_for_average.append(scores_for_template["Habitable_Zone_Position"]["score"])
        components_for_average.append(scores_for_template["Atmosphere_Potential"]["score"])
        components_for_average.append(scores_for_template["Liquid_Water_Potential"]["score"])
        components_for_average.append(scores_for_template["Presence_of_Moons"]["score"])
        components_for_average.append(scores_for_template["Magnetic_Activity"]["score"])
        components_for_average.append(scores_for_template["System_Age"]["score"])
        
        esi_val = scores_for_template["ESI"]["score"]
        phi_val = scores_for_template["PHI"]["score"] # Já está na escala 0-100

        if pd.notna(esi_val): 
            components_for_average.append(esi_val)
        if pd.notna(phi_val):
            components_for_average.append(phi_val)

        # Adiciona scores condicionalmente (Size, Density, Mass)
        if is_habitable_candidate:
            components_for_average.append(scores_for_template["Size"]["score"])
            components_for_average.append(scores_for_template["Density"]["score"])
            components_for_average.append(scores_for_template["Mass"]["score"])
        
        habitability_score_value = 0.0
        if components_for_average: # Evita divisão por zero se a lista estiver vazia
            habitability_score_value = round(sum(components_for_average) / len(components_for_average), 2)
        else:
            logger.warning(f"Nenhum componente para calcular a média do Habitability Score para {planet_name_for_log}. Definido como 0.")

        # Aplica bônus para planetas "Warm" Terran/Superterran
        # A classificação "Warm" deve vir de 'classification_text'
        is_warm_classified = "Warm" in classification_text 
        if is_warm_classified and ("Terran" in classification_text or "Superterran" in classification_text):
            habitability_score_value = min(habitability_score_value + 10, 100) # Bônus de 10, limitado a 100
        
        habitability_score_value = np.clip(habitability_score_value, 0, 100) # Garante que o score está entre 0 e 100

        # Adiciona/Atualiza o "Habitability" score em scores_for_template
        scores_for_template["Habitability"] = {
            "score": habitability_score_value,
            "color": get_color_for_percentage(habitability_score_value),
            "text": "Overall Habitability Score" # Texto descritivo opcional
        }
        # --- FIM DO CÁLCULO DO NOVO HABITABILITY SCORE ---        
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
        
        hz_description = "N/A"
        if hz_data_tuple_raw and len(hz_data_tuple_raw) > 4 and pd.notna(hz_data_tuple_raw[4]): 
            hz_description = str(hz_data_tuple_raw[4])
        surface_gravity_value_str = "N/A"  # Default
        raw_pl_grav = planet_raw_TAP_data.get("pl_grav")

        if pd.notna(raw_pl_grav):
            surface_gravity_value_str = format_float_field(raw_pl_grav, ".2f")
        else:
            # Tentar calcular se pl_grav não estiver disponível
            raw_pl_masse = planet_raw_TAP_data.get("pl_masse") 
            # Se pl_masse não estiver disponível, pode tentar pl_bmassj como fallback,
            # mas no seu JSON, pl_masse ("9.10") parece ser o campo mais direto para massa em M⊕ para Kepler-22 b
            # e pl_bmassj ("0.0104") para Kepler-452 b (que também tem pl_masse: "3.29")
            # A escolha de qual usar como fallback (ou se deve haver um) depende da sua prioridade de dados.
            # Vamos priorizar pl_masse se disponível, pois é o que usamos na mensagem anterior.
            if not pd.notna(raw_pl_masse): # Se pl_masse for NaN ou não existir
                 raw_pl_masse = planet_raw_TAP_data.get("pl_bmassj") # Tenta usar pl_bmassj

            raw_pl_rade = planet_raw_TAP_data.get("pl_rade")

            if pd.notna(raw_pl_masse) and pd.notna(raw_pl_rade):
                try:
                    mass_earth_str = str(raw_pl_masse)
                    radius_earth_str = str(raw_pl_rade)
                    
                    # Remove o "<" se presente, para poder converter para float
                    if isinstance(mass_earth_str, str) and mass_earth_str.startswith("<"):
                        mass_earth_str = mass_earth_str.lstrip("<")
                    
                    mass_earth = float(mass_earth_str)
                    radius_earth = float(radius_earth_str)
                    
                    if radius_earth > 0:  # Evitar divisão por zero
                        calculated_gravity = mass_earth / (radius_earth ** 2)
                        surface_gravity_value_str = format_float_field(calculated_gravity, ".2f")
                        logger.info(f"Calculated surface gravity for {planet_name_for_log}: {surface_gravity_value_str} g (M={mass_earth} M⊕, R={radius_earth} R⊕)")
                    else:
                        logger.warning(f"Cannot calculate surface gravity for {planet_name_for_log}: radius is zero or invalid ({radius_earth}).")
                except (ValueError, TypeError) as e_calc:
                    logger.warning(f"Could not convert mass ('{raw_pl_masse}') or radius ('{raw_pl_rade}') to float for surface gravity calculation for {planet_name_for_log}. Error: {e_calc}")
            else:
                logger.warning(f"Mass ('{raw_pl_masse}') or radius ('{raw_pl_rade}') is not available for surface gravity calculation for {planet_name_for_log}.")

        data_for_template = {
            "planet_name": planet_raw_TAP_data.get("pl_name", "N/A"),
            "classification": classification_text,
            "star_type": planet_raw_TAP_data.get("st_spectype", "N/A"),
            "distance_light_years": distance_ly_str, 
            "equilibrium_temp_k": format_float_field(planet_raw_TAP_data.get("pl_eqt"),".0f"),
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
            "star_temp_k": format_float_field(planet_raw_TAP_data.get("st_teff"),".0f"), 
            "star_radius_solar": format_float_field(planet_raw_TAP_data.get("st_rad")),
            "star_info": p_data.get("star_info", {}), 

        # Campos extras:
            "magnetic_activity_score": extra_fields["magnetic_activity_score"],
            "presence_of_moons_score": extra_fields["presence_of_moons_score"],
            "atmosphere_potential_desc": extra_fields["atmosphere_potential_desc"],
            "liquid_water_potential_desc": extra_fields["liquid_water_potential_desc"],
            "magnetic_activity_desc": extra_fields["magnetic_activity_desc"],
            "presence_of_moons_desc": extra_fields["presence_of_moons_desc"],

        }
        processed_data_list.append(data_for_template)


    if not processed_data_list:
        logger.warning("No data processed for summary/combined report (processed_data_list is empty).")
        return [] 
        
    logger.info(f"Finished _prepare_data_for_aggregated_reports. Processed {len(processed_data_list)} planets.")
    return processed_data_list

def generate_summary_report_html(all_planets_report_data, template_env, output_dir):
    ensure_dir(output_dir)
    report_filename = "summary_report.html"
    full_report_path = os.path.join(output_dir, report_filename)
    logger.info(f"Generating summary report to {full_report_path}")
    try:
        template = template_env.get_template("summary_template.html")
        # `all_planets_report_data` here is the list of `processed_result` dicts from routes.py
        processed_planets_data = _prepare_data_for_aggregated_reports(all_planets_report_data, output_dir)
        
        if not processed_planets_data:
            logger.warning("No processed data available for summary report. Report will be empty or show 'no data'.")

        context = {"all_planets_data": processed_planets_data, "datetime": datetime}
        html_content = template.render(context)
        with open(full_report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Summary report saved to {full_report_path}")
        return full_report_path
    except Exception as e:
        logger.error(f"Error generating summary report: {e}", exc_info=True)
        traceback.print_exc()
        return None

def generate_combined_report_html(all_planets_report_data, template_env, output_dir):
    ensure_dir(output_dir)
    report_filename = "combined_report.html"
    full_report_path = os.path.join(output_dir, report_filename)
    logger.info(f"Generating combined report to {full_report_path}")
    try:
        template = template_env.get_template("combined_template.html")
        # `all_planets_report_data` here is the list of `processed_result` dicts from routes.py
        processed_planets_data = _prepare_data_for_aggregated_reports(all_planets_report_data, output_dir)

        if not processed_planets_data:
            logger.warning("No processed data available for combined report. Report will be empty or show 'no data'.")

        context = {"all_planets_data": processed_planets_data, "datetime": datetime}
        html_content = template.render(context)
        with open(full_report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Combined report saved to {full_report_path}")
        return full_report_path
    except Exception as e:
        logger.error(f"Error generating combined report: {e}", exc_info=True)
        traceback.print_exc()
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

