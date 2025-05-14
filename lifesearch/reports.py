import matplotlib
matplotlib.use("Agg")  # Set non-interactive backend for matplotlib

import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import logging
from jinja2 import Environment, FileSystemLoader
import json  # For logging context and SAVING DATA
import traceback  # For explicit error printing

logger = logging.getLogger(__name__)

# Helper function to create output directories if they don't exist
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
            ax.plot(pl_orbsmax_fl, 0, "o", markersize=10, color="blue", label=f"{planet_data.get('pl_name', planet_name_slug)} ({pl_orbsmax_fl:.2f} AU)")
        else:
            logger.warning(f"Orbital semi-major axis (pl_orbsmax) not available or not float for {planet_name_slug}.")

        ax.set_yticks([])
        ax.set_xlabel("Distance from Star (AU)")
        ax.set_title(f"Habitable Zone for {planet_data.get('pl_name', planet_name_slug)}")
        
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
                travel_curiosities_for_template["scenario_1_label"] = "Current Tech (e.g., Parker Solar Probe ~170 km/s)"
                travel_curiosities_for_template["scenario_1_time"] = f"{dist_ly_f * (299792 / 170) / 1000:.1f} thousand years"
                travel_curiosities_for_template["scenario_2_label"] = "Future Tech (20% speed of light)"
                travel_curiosities_for_template["scenario_2_time"] = f"{dist_ly_f / 0.2:.1f} years"
                travel_curiosities_for_template["scenario_3_label"] = "Relativistic (99% speed of light)"
                travel_curiosities_for_template["scenario_3_time"] = f"{dist_ly_f / 0.99:.1f} years"
            except (ValueError, TypeError):
                logger.warning(f"Could not calculate travel times for {planet_name_slug} due to distance conversion error.")
                travel_curiosities_for_template["scenario_1_time"] = "N/A"
                travel_curiosities_for_template["scenario_2_time"] = "N/A"
                travel_curiosities_for_template["scenario_3_time"] = "N/A"
        else:
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

def _prepare_data_for_aggregated_reports(all_planets_report_data, output_dir_for_debug_json):
    logger.info(f"Starting _prepare_data_for_aggregated_reports with {len(all_planets_report_data)} planets.")
    
    debug_file_path = os.path.join(output_dir_for_debug_json, "debug_input_all_planets_report_data.json")
    try:
        with open(debug_file_path, "w", encoding="utf-8") as f_debug:
            json.dump(all_planets_report_data, f_debug, indent=2, default=str)
        logger.info(f"Saved all_planets_report_data (input to _prepare_data) for debugging to {debug_file_path}")
    except Exception as e_debug:
        logger.error(f"Could not save all_planets_report_data for debugging: {e_debug}")

    processed_data_list = []
    for i, p_data in enumerate(all_planets_report_data):
        planet_raw_TAP_data = p_data.get("planet_data_dict", {})
        scores_processed = p_data.get("scores_for_report", {})
        sephi_processed = p_data.get("sephi_scores_for_report", {})
        hz_data_tuple_raw = p_data.get("hz_data_tuple", (None, None, None, None, None))
        planet_name_for_log = planet_raw_TAP_data.get("pl_name", "Unknown")
        logger.info(f"Processing planet {i+1}/{len(all_planets_report_data)} for aggregated report: {planet_name_for_log}")

        classification_text = planet_raw_TAP_data.get("classification_final_display", planet_raw_TAP_data.get("classification", "N/A"))

        def get_score_info(score_source_dict, key, default_percentage=0.0):
            val_tuple = score_source_dict.get(key)
            score_percentage = default_percentage
            color_val = get_color_for_percentage(default_percentage)
            text_desc = "N/A"
            if val_tuple is not None:
                if isinstance(val_tuple, (list, tuple)) and len(val_tuple) > 0 and pd.notna(val_tuple[0]):
                    try:
                        score_percentage = float(val_tuple[0])  # Já em porcentagem, não dividir
                        color_val = val_tuple[1] if len(val_tuple) > 1 and pd.notna(val_tuple[1]) else get_color_for_percentage(score_percentage)
                        if len(val_tuple) > 2 and pd.notna(val_tuple[2]):
                            text_desc = str(val_tuple[2])
                    except (ValueError, TypeError):
                        logger.warning(f"Planet {planet_name_for_log}: Could not convert score value for {key}: {val_tuple[0]}. Using default {default_percentage}%.")
                elif pd.notna(val_tuple):
                    try:
                        score_percentage = float(val_tuple)  # Já em porcentagem, não dividir
                        color_val = get_color_for_percentage(score_percentage)
                    except (ValueError, TypeError):
                        logger.warning(f"Planet {planet_name_for_log}: Could not convert direct score value for {key}: {val_tuple}. Using default {default_percentage}%.")
            return {"score": score_percentage, "color": color_val, "text": text_desc}

        scores_for_template = {
            "ESI": get_score_info(scores_processed, "ESI"),
            "PHI": get_score_info(scores_processed, "PHI"),
            "SPH": get_score_info(scores_processed, "SPH"),
            "Habitability": get_score_info(scores_processed, "Habitability Score", 0.0),
            "Host_Star_Type": get_score_info(scores_processed, "Host Star Type"),
            "System_Age": get_score_info(scores_processed, "System Age"),
            "Stellar_Activity": get_score_info(scores_processed, "Stellar Activity", 0.0),
            "Orbital_Eccentricity": get_score_info(scores_processed, "Orbital Eccentricity"),
            "Atmosphere_Potential": get_score_info(scores_processed, "Atmosphere Potential"),
            "Liquid_Water_Potential": get_score_info(scores_processed, "Liquid Water Potential"),
            "Magnetic_Activity": get_score_info(scores_processed, "Magnetic Activity", 0.0),
            "Presence_of_Moons": get_score_info(scores_processed, "Presence of Moons", 0.0),
            "Habitable_Zone_Position": get_score_info(scores_processed, "Habitable Zone Position"),
            "Size": get_score_info(scores_processed, "Size"),
            "Density": get_score_info(scores_processed, "Density"),
            "Mass": get_score_info(scores_processed, "Mass"),
            "Star_Metallicity": get_score_info(scores_processed, "Star Metallicity")
        }
        
        sephi_for_template = {
            "SEPHI": get_score_info(sephi_processed, "SEPHI"),
            "SEPHI_L1": get_score_info(sephi_processed, "L1 (Surface)"),
            "SEPHI_L2": get_score_info(sephi_processed, "L2 (Escape Velocity)"),
            "SEPHI_L3": get_score_info(sephi_processed, "L3 (Habitable Zone)"),
            "SEPHI_L4": get_score_info(sephi_processed, "L4 (Magnetic Field)")
        }

        hz_desc = "N/A"
        if hz_data_tuple_raw and all(pd.notna(x) for x in hz_data_tuple_raw[:4]):
            hz_source = str(hz_data_tuple_raw[4]) if len(hz_data_tuple_raw) > 4 and pd.notna(hz_data_tuple_raw[4]) else "Calculated"
            pl_orbsmax_val = planet_raw_TAP_data.get("pl_orbsmax", "N/A")
            pl_orbsmax_str = "N/A"
            try:
                pl_orbsmax_str = format_float_field(pl_orbsmax_val)
            except:
                pass
            hz_desc = f"{pl_orbsmax_str} AU (Cons: {format_float_field(hz_data_tuple_raw[1])}-{format_float_field(hz_data_tuple_raw[2])} AU, Opt: {format_float_field(hz_data_tuple_raw[0])}-{format_float_field(hz_data_tuple_raw[3])} AU, Src: {hz_source})"
        
        dist_pc_val = planet_raw_TAP_data.get("sy_dist")
        travel_curiosities_data = {"distance_ly": "N/A", "current_tech_years": "N/A", "twenty_ls_years": "N/A", "near_ls_years": "N/A"}
        if pd.notna(dist_pc_val):
            try:
                dist_ly_f = float(str(dist_pc_val)) * 3.26156
                travel_curiosities_data["distance_ly"] = f"{dist_ly_f:.2f}"
                travel_curiosities_data["current_tech_years"] = f"{dist_ly_f * (299792 / 170) / 1000:.1f} thousand years"
                travel_curiosities_data["twenty_ls_years"] = f"{dist_ly_f / 0.2:.1f} years"
                travel_curiosities_data["near_ls_years"] = f"{dist_ly_f / 0.99:.1f} years"
            except (ValueError, TypeError):
                logger.warning(f"Planet {planet_name_for_log}: Could not convert sy_dist {dist_pc_val} to float for travel time calculation.")

        atmosphere_potential_text = scores_for_template.get("Atmosphere_Potential", {}).get("text", "N/A")
        liquid_water_potential_text = scores_for_template.get("Liquid_Water_Potential", {}).get("text", "N/A")
        magnetic_activity_text = scores_for_template.get("Magnetic_Activity", {}).get("text", "N/A")
        presence_of_moons_text = scores_for_template.get("Presence_of_Moons", {}).get("text", "N/A")

        data_entry = {
            "planet_name": planet_raw_TAP_data.get("pl_name", "N/A"),
            "scores": scores_for_template,
            "sephi_scores": sephi_for_template,
            "star_type": planet_raw_TAP_data.get("st_spectype", "N/A"),
            "classification": classification_text,
            "habitable_zone_description": hz_desc,
            "distance_parsecs": format_float_field(planet_raw_TAP_data.get("sy_dist")),
            "distance_light_years": travel_curiosities_data["distance_ly"],
            "planet_radius_earth": format_float_field(planet_raw_TAP_data.get("pl_rade")),
            "planet_mass_earth": format_float_field(planet_raw_TAP_data.get("pl_masse")),
            "planet_density_gcm3": format_float_field(planet_raw_TAP_data.get("pl_dens")),
            "surface_gravity_g": format_float_field(planet_raw_TAP_data.get("pl_insol")),  # Placeholder, should use pl_grav if available
            "equilibrium_temp_k": format_float_field(planet_raw_TAP_data.get("pl_eqt"), ".0f"),
            "orbital_period_days": format_float_field(planet_raw_TAP_data.get("pl_orbper")),
            "semi_major_axis_au": format_float_field(planet_raw_TAP_data.get("pl_orbsmax")),
            "eccentricity": format_float_field(planet_raw_TAP_data.get("pl_orbeccen")),
            "atmosphere_potential_text": atmosphere_potential_text,
            "liquid_water_potential_text": liquid_water_potential_text,
            "magnetic_activity_text": magnetic_activity_text,
            "presence_of_moons_text": presence_of_moons_text,
            "travel_curiosities": travel_curiosities_data,
            "star_info": {
                "temperature_k": format_float_field(planet_raw_TAP_data.get("st_teff"), ".0f"),
                "radius_solar": format_float_field(planet_raw_TAP_data.get("st_rad")),
            }
        }
        processed_data_list.append(data_entry)
        logger.debug(f"Finished processing planet {planet_name_for_log} for aggregated report. Data: {data_entry}")

    logger.info(f"_prepare_data_for_aggregated_reports finished processing {len(processed_data_list)} planets.")
    return processed_data_list

def generate_summary_report_html(all_planets_report_data_input, template_env, output_dir):
    ensure_dir(output_dir)
    report_filename = "summary_report.html"
    full_report_path = os.path.join(output_dir, report_filename)
    logger.info(f"Attempting to generate summary report to {full_report_path}")
    
    processed_planets_data = _prepare_data_for_aggregated_reports(all_planets_report_data_input, output_dir)
        
    if not processed_planets_data:
        logger.warning("No data processed for summary report (processed_planets_data is empty/None). Report will be empty or show \"no data\".")
    else:
        logger.info(f"Data processed for summary report. Count: {len(processed_planets_data)}")

    try:
        template = template_env.get_template("summary_template.html")
        context = {
            "all_planets_data": processed_planets_data,
            "datetime": datetime,
            "current_year": datetime.now().year
        }
        html_content = template.render(context)
        with open(full_report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Summary HTML report saved to {full_report_path}")
        return full_report_path
    except Exception as e:
        logger.error(f"Error generating summary HTML report: {e}", exc_info=True)
        traceback.print_exc()
        return None

def generate_combined_report_html(all_planets_report_data_input, template_env, output_dir):
    ensure_dir(output_dir)
    report_filename = "combined_report.html"
    full_report_path = os.path.join(output_dir, report_filename)
    logger.info(f"Attempting to generate combined report to {full_report_path}")

    processed_planets_data = _prepare_data_for_aggregated_reports(all_planets_report_data_input, output_dir)

    if not processed_planets_data:
        logger.warning("No data processed for combined report (processed_planets_data is empty/None). Report will be empty or show \"no data\".")
    else:
        logger.info(f"Data processed for combined report. Count: {len(processed_planets_data)}")
            
    try:
        template = template_env.get_template("combined_template.html")
        context = {
            "all_planets_data": processed_planets_data,
            "datetime": datetime
        }
        html_content = template.render(context)
        with open(full_report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Combined HTML report saved to {full_report_path}")
        return full_report_path
    except Exception as e:
        logger.error(f"Error generating combined HTML report: {e}", exc_info=True)
        traceback.print_exc()
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates_dir = os.path.join(base_dir, "app", "templates")
        
        if not os.path.isdir(templates_dir):
            templates_dir_alt1 = os.path.join(os.path.dirname(__file__), "..", "app", "templates")
            templates_dir_alt2 = os.path.join(os.path.dirname(__file__), "app", "templates")
            if os.path.isdir(templates_dir_alt1):
                templates_dir = templates_dir_alt1
            elif os.path.isdir(templates_dir_alt2):
                templates_dir = templates_dir_alt2
            else:
                logger.error(f"Templates directory not found. Checked: {templates_dir}, {templates_dir_alt1}, {templates_dir_alt2}")
                exit()
        
        logger.info(f"Using templates from: {templates_dir}")
        template_env = Environment(loader=FileSystemLoader(templates_dir))
    except Exception as e:
        logger.error(f"Failed to set up template environment: {e}")
        template_env = None

    if template_env:
        all_planets_data_for_test = [
            {
                "planet_data_dict": {
                    "pl_name": "Test Planet 1", "st_spectype": "G2V", "sy_dist": "10",
                    "pl_orbsmax": 1.0, "pl_orbper": 365.25, "pl_orbeccen": 0.017, "pl_orbincl": 0.1,
                    "hostname": "Test Star 1", "st_teff": 5778, "st_rad": 1.0, "st_mass": 1.0, "st_lum": 0.0, "st_age": 4.5, "st_metfe": 0.0,
                    "pl_rade": 1.0, "pl_masse": 1.0, "pl_dens": 5.51, "pl_eqt": 255, "pl_insol": 1.0,
                    "classification_final_display": "Mesoplanet"
                },
                "scores_for_report": {"ESI": (80.0, "green", "Good ESI"), "PHI": (70.0, "green", "Good PHI")},
                "sephi_scores_for_report": {"SEPHI": (70.0, "lightgreen", "Good SEPHI")},
                "hz_data_tuple": (0.8, 0.9, 1.5, 1.6, "Test HZ")
            },
            {
                "planet_data_dict": {
                    "pl_name": "Test Planet 2", "st_spectype": "M5V", "sy_dist": "20",
                    "pl_orbsmax": 0.1, "pl_orbper": 10.0, "pl_orbeccen": 0.1, "pl_orbincl": 1.0,
                    "hostname": "Test Star 2", "st_teff": 3000, "st_rad": 0.3, "st_mass": 0.2, "st_lum": -2.0, "st_age": 1.0, "st_metfe": -0.1,
                    "pl_rade": 0.5, "pl_masse": 0.1, "pl_dens": 3.0, "pl_eqt": 200, "pl_insol": 0.2,
                    "classification_final_display": "Psychroplanet"
                },
                "scores_for_report": {"ESI": (60.0, "lightgreen", "Okay ESI")},
                "sephi_scores_for_report": {"SEPHI": (50.0, "yellow", "Okay SEPHI")},
                "hz_data_tuple": (0.1, 0.2, 0.5, 0.6, "Test HZ 2")
            }
        ]
        output_test_dir = "test_reports_output"
        ensure_dir(output_test_dir)

        if all_planets_data_for_test:
            logger.info("--- Testing Individual Report Generation ---")
            for i, planet_test_data_item in enumerate(all_planets_data_for_test):
                pdd = planet_test_data_item["planet_data_dict"]
                s = planet_test_data_item["scores_for_report"]
                se = planet_test_data_item["sephi_scores_for_report"]
                hzd = planet_test_data_item["hz_data_tuple"]
                slug = pdd["pl_name"].lower().replace(" ", "_")
                
                plots_for_individual = {}
                hz_plot = plot_habitable_zone(pdd, pdd, hzd, os.path.join(output_test_dir, "charts"), slug)
                if hz_plot:
                    plots_for_individual["habitable_zone_plot"] = hz_plot
                
                scores_plot = plot_scores_comparison(s, os.path.join(output_test_dir, "charts"), slug)
                if scores_plot:
                    plots_for_individual["scores_plot"] = scores_plot
                
                generate_planet_report_html(pdd, s, se, plots_for_individual, template_env, output_test_dir, slug)

            logger.info("--- Testing Summary Report Generation ---")
            generate_summary_report_html(all_planets_data_for_test, template_env, output_test_dir)

            logger.info("--- Testing Combined Report Generation ---")
            generate_combined_report_html(all_planets_data_for_test, template_env, output_test_dir)
            logger.info(f"--- Finished Testing --- Please check the \"{output_test_dir}\" directory.")
        else:
            logger.info("No data for testing, skipping report generation tests.")
    else:
        logger.error("Template environment not available. Tests cannot run.")