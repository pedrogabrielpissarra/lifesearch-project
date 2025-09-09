from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, send_from_directory, flash, jsonify
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime
import logging
from jinja2 import Environment, FileSystemLoader


from lifesearch.data import fetch_exoplanet_data_api, load_hwc_catalog, load_hzgallery_catalog, merge_data_sources, normalize_name
from lifesearch.reports import plot_habitable_zone, plot_scores_comparison, generate_planet_report_html, generate_summary_report_html, generate_combined_report_html
from lifesearch.lifesearch_main import (
    process_planet_data,
    sliders_phi,
    reference_values_slider,
    initial_esi_weights,
    classify_planet,
)
from .forms import PlanetSearchForm, HabitabilityWeightsForm, PHIWeightsForm  # Ajuste conforme necessário
#from .utils import normalize_name, DEFAULT_HABITABILITY_WEIGHTS, DEFAULT_PHI_WEIGHTS # Ajuste
from lifesearch.data import load_hwc_catalog, load_hzgallery_catalog  # Ajuste
import requests
import math
import json


logger = logging.getLogger(__name__)

# 🔹 CRIA O BLUEPRINT
routes_bp = Blueprint("routes", __name__)


def replace_nan_with_none(obj):
    """Recursively replaces float NaN values with None in a nested data structure.
    
    Args:
        obj (dict, list, float, or other): The object to process. Can be a dictionary,
                                            list, or a single value.
    
    Returns:
        The processed object with NaN values replaced by None.
    """
    if isinstance(obj, dict):
        return {k: replace_nan_with_none(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_nan_with_none(elem) for elem in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    return obj

import math # Garanta que math seja importado no topo de routes.py


def get_template_env():
    """Initializes and returns a Jinja2 template environment.
    
    Configures the template loader to look for templates in the 'templates'
    directory relative to the application's root path. Enables autoescaping
    for security.
    
    Returns:
        jinja2.Environment: The configured Jinja2 environment.
    """
    template_loader = FileSystemLoader(searchpath=os.path.join(current_app.root_path, "templates"))
    return Environment(loader=template_loader, autoescape=True) # Added autoescape for security

DEFAULT_HABITABILITY_WEIGHTS = {
    "Habitable Zone": 1.0, "Size": 1.0, "Density": 1.0, "Atmosphere": 1.0,
    "Water": 1.0, "Presence of Moons": 1.0, "Magnetic Activity": 1.0, "System Age": 1.0
}
DEFAULT_PHI_WEIGHTS = {
    "Solid Surface": 0.25, "Stable Energy": 0.25, 
    "Life Compounds": 0.25, "Stable Orbit": 0.25
}

from flask import current_app as app

@routes_bp.app_context_processor
def inject_global_vars():
    """Injects global variables into the template context.
    
    Makes the current year and the datetime object available in all templates.
    
    Returns:
        dict: A dictionary of variables to inject into the template context.
    """
    return {
        "current_year": datetime.now().year,
        "datetime": datetime # Make datetime object available for templates if needed
    }

@routes_bp.route("/", methods=["GET", "POST"])
@routes_bp.route("/index", methods=["GET", "POST"], endpoint="index")
def index():
    """Handles the main page for planet search.
    
    Displays the planet search form. On GET request with 'restore=1' parameter,
    it restores planet names and parameter overrides from the session.
    On POST request (form submission), it validates the input, stores
    planet names and overrides in the session, and redirects to the results page.
    
    Returns:
        werkzeug.wrappers.response.Response: Renders the index.html template or
                                             redirects to the results page.
    """
    logger.info(f"Index: Initial session content: {dict(session)}")
    form = PlanetSearchForm()

    # Recovery session data via ?restore=1
    if request.method == "GET" and request.args.get("restore") == "1":
        planet_names_list = session.get("planet_names_list", [])
        parameter_overrides_input = session.get("parameter_overrides_input", "")
        
        logger.info(f"Index: Restoring session - planet_names_list={planet_names_list}, parameter_overrides_input={parameter_overrides_input}")
        
        if planet_names_list:
            form.planet_names.data = ", ".join(planet_names_list)
        if parameter_overrides_input:
            form.parameter_overrides.data = parameter_overrides_input

    # If is a form post submission (POST)
    if form.validate_on_submit():
        planet_names_input = form.planet_names.data
        parameter_overrides_input = form.parameter_overrides.data
        
        planet_names_list = [name.strip() for name in planet_names_input.replace(",", "\n").split("\n") if name.strip()]

        if not planet_names_list:
            flash("Please enter valid planet names.", "danger")
            logger.info("Index: No valid planet names provided")
            return render_template("index.html", form=form, title="LifeSearch Web")

        session["planet_names_list"] = planet_names_list
        session["parameter_overrides_input"] = parameter_overrides_input
        session.modified = True
        logger.info(f"Index: Updated session with planet_names_list={planet_names_list}, parameter_overrides_input={parameter_overrides_input}")
        logger.info(f"Index: Session after update: {dict(session)}")
        
        return redirect(url_for("routes.results"))

    logger.info(f"Index: Rendering index.html with session: {dict(session)}")
    return render_template("index.html", form=form, title="LifeSearch Web")

@routes_bp.route("/configure", methods=["GET", "POST"])
def configure():
    """Handles the configuration page for habitability and PHI weights.
    
    Displays forms for setting global and potentially planet-specific weights.
    Retrieves planet names from the session and fetches their reference ESI/PHI
    values based on current global weights for display.
    
    Returns:
        werkzeug.wrappers.response.Response: Renders the configure.html template.
    """
    planet_names_list = session.get("planet_names_list", [])
    logger.info(f"Configure: Full session content: {dict(session)}")
    logger.info(f"Configure: planet_names_list na sessão = {planet_names_list}")
    
    hab_form = HabitabilityWeightsForm(prefix="hab")
    phi_form = PHIWeightsForm(prefix="phi")

    default_hab_weights = DEFAULT_HABITABILITY_WEIGHTS 
    default_phi_weights = DEFAULT_PHI_WEIGHTS
    current_global_hab_weights = session.get("habitability_weights", default_hab_weights)
    current_global_phi_weights = session.get("phi_weights", default_phi_weights)
    current_planet_specific_weights = session.get("planet_weights", {})
    use_individual = session.get("use_individual_weights", False)

    reference_values = []
    initial_hab_weights = {}
    initial_phi_weights = {}
    if planet_names_list:
        default_habitability_weights_ref = current_app.config.get("DEFAULT_HABITABILITY_WEIGHTS", DEFAULT_HABITABILITY_WEIGHTS)
        default_phi_weights_ref = current_app.config.get("DEFAULT_PHI_WEIGHTS", DEFAULT_PHI_WEIGHTS)
        global_habitability_weights_ref = session.get("habitability_weights", default_habitability_weights_ref)
        global_phi_weights_ref = session.get("phi_weights", default_phi_weights_ref)
        
        hwc_df = load_hwc_catalog(os.path.join(current_app.config["DATA_DIR"], "hwc.csv"))
        hz_gallery_df = load_hzgallery_catalog(os.path.join(current_app.config["DATA_DIR"], "table-hzgallery.csv"))
        
        for planet_name in planet_names_list:
            logger.info(f"Processing reference values for planet: {planet_name}")
            api_data = fetch_exoplanet_data_api(planet_name)
            
            if api_data is None:
                logger.warning(f"Could not fetch API data for reference values of {planet_name}.")
                continue
            
            if "pl_name" not in api_data or pd.isna(api_data.get("pl_name")):
                api_data["pl_name"] = planet_name
                
            normalized_planet_name = normalize_name(api_data.get("pl_name", planet_name))
            combined_data = merge_data_sources(api_data, hwc_df, hz_gallery_df, normalized_planet_name)
            
            logger.debug(f"Combined data for {normalized_planet_name}: {combined_data}")

            # Calcular ESI e PHI com pesos padrão (0.0 para habitability, 0.0 para PHI)
            processed_result = process_planet_data(
                normalized_planet_name,
                combined_data,
                {"habitability": {"Size": 0.0, "Density": 0.0, "Habitable Zone": 0.0},
                 "phi": {"Solid Surface": 0.0, "Stable Energy": 0.0, "Life Compounds": 0.0, "Stable Orbit": 0.0}}
            )

            if processed_result:
                planet_data = processed_result.get("planet_data_dict", {})

                # CORREÇÃO: Calcular valores de referência corretos para ESI e PHI
                esi_val, phi_val = reference_values_slider(planet_data)

                reference_planet = {
                    "name": planet_data.get("pl_name", normalized_planet_name),
                    "esi": esi_val,
                    "phi": phi_val,
                    "classification": planet_data.get("classification", "Unknown")
                }
                reference_values.append(reference_planet)
                logger.info(f"Reference values para {normalized_planet_name}: ESI={esi_val}%, PHI={phi_val}%")

                # Calcular similaridades reais para pesos iniciais do ESI
                earth_params = {"pl_rade": 1.0, "pl_dens": 5.51, "pl_eqt": 255.0}
                esi_factors_map = {"pl_rade": "Size", "pl_dens": "Density", "pl_eqt": "Habitable Zone"}
                similarities = {}
                total_similarity = 0.0
                num_esi_params = 0

                for param_key, weight_key in esi_factors_map.items():
                    planet_val = planet_data.get(param_key)
                    earth_val = earth_params.get(param_key)
                    if pd.notna(planet_val) and pd.notna(earth_val) and earth_val != 0:
                        try:
                            planet_val_fl = float(planet_val)
                            earth_val_fl = float(earth_val)
                            similarity = 1.0 - abs((planet_val_fl - earth_val_fl) / (planet_val_fl + earth_val_fl))
                            if similarity < 0:
                                similarity = 0.0
                            similarities[weight_key] = similarity
                            total_similarity += similarity
                            num_esi_params += 1
                            logger.debug(f"Similarity for {param_key} ({weight_key}): {similarity}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Could not compute similarity for {param_key}: {e}")
                            similarities[weight_key] = 0.0
                    else:
                        logger.warning(f"Missing or invalid data for {param_key}: planet_val={planet_val}, earth_val={earth_val}")
                        similarities[weight_key] = 0.0

                # Calcular pesos iniciais para ESI
                esi_target = esi_val / 100.0 if esi_val > 0 else 0.0
                initial_hab_weights[normalized_planet_name] = {
                    "Size": 0.0,
                    "Density": 0.0,
                    "Habitable Zone": 0.0
                }
                if num_esi_params > 0 and total_similarity > 0:
                    for weight_key in esi_factors_map.values():
                        initial_hab_weights[normalized_planet_name][weight_key] = similarities[weight_key]
                        logger.debug(
                            f"Initial ESI weight for {weight_key}: {initial_hab_weights[normalized_planet_name][weight_key]}"
                        )
                else:
                    logger.warning(
                        f"No valid ESI similarities calculated for {normalized_planet_name}. Using ESI target as fallback."
                    )
                    for weight_key in esi_factors_map.values():
                        initial_hab_weights[normalized_planet_name][weight_key] = (
                            esi_target / num_esi_params if num_esi_params > 0 else 0.0
                        )

                # CORREÇÃO: Calcular pesos iniciais para PHI usando a função sliders_phi
                initial_phi_weights[normalized_planet_name] = sliders_phi(planet_data)
                logger.info(
                    f"Initial PHI weights para {normalized_planet_name}: {initial_phi_weights[normalized_planet_name]}"
                )

    logger.info(f"Configure: reference_values = {reference_values}")
    logger.info(f"Configure: initial_hab_weights = {initial_hab_weights}")
    logger.info(f"Configure: initial_phi_weights = {initial_phi_weights}")
    logger.info(f"Configure: initial_hab_weights_json = {json.dumps(initial_hab_weights)}")
    logger.info(f"Configure: initial_phi_weights_json = {json.dumps(initial_phi_weights)}")
    return render_template("configure.html", 
                           hab_form=hab_form, 
                           phi_form=phi_form, 
                           title="Configure Weights", 
                           reference_values=reference_values,
                           default_hab_weights_json=json.dumps(default_hab_weights),
                           default_phi_weights_json=json.dumps(default_phi_weights),
                           current_global_hab_weights_json=json.dumps(current_global_hab_weights),
                           current_global_phi_weights_json=json.dumps(current_global_phi_weights),
                           current_planet_specific_weights_json=json.dumps(current_planet_specific_weights),
                           use_individual_weights_val=use_individual,
                           initial_hab_weights_json=json.dumps(initial_hab_weights),
                           initial_phi_weights_json=json.dumps(initial_phi_weights))

@routes_bp.route("/api/planets/reference-values", methods=["GET"])
def get_planet_reference_values_hyphen():
    """
    API endpoint (hyphenated path) to provide reference ESI, PHI, and classification
    for planets currently in the session.
    
    This endpoint calls `get_planet_reference_values` and is provided for frontend
    compatibility that might prefer hyphenated URLs.
    
    Returns:
        flask.Response: JSON response containing a list of planets with their
                        reference values.
    """
    return get_planet_reference_values()


@routes_bp.route("/api/planets/reference_values", methods=["GET", "POST"])
def get_planet_reference_values():
    """
    API endpoint to calculate and return reference ESI, PHI, and classification
    for planets in the session.
    
    On GET, uses global weights from the session or defaults.
    On POST, can accept `use_individual_weights` and `planet_weights` to calculate
    reference values with potentially different weights for each planet, without
    permanently saving these weights to the session from this endpoint.
    
    Returns:
        flask.Response: JSON response containing a list of planets, each with
                        'name', 'esi', 'phi', and 'classification'.
    """
    logger = current_app.logger
    planet_names_list = session.get("planet_names_list", [])
    logger.info(f"API reference_values: planet_names_list na sessão = {planet_names_list}")
    
    if not planet_names_list:
        return jsonify({"planets": []})
    
    use_individual_weights = False
    planet_weights = {}
    if request.method == "POST":
        data = request.json or {}
        use_individual_weights = data.get("use_individual_weights", False)
        planet_weights = data.get("planet_weights", {})
        logger.info(f"API reference_values - POST data: use_individual_weights={use_individual_weights}, planet_weights={planet_weights}")
    
    default_habitability_weights = current_app.config.get("DEFAULT_HABITABILITY_WEIGHTS", DEFAULT_HABITABILITY_WEIGHTS)
    default_phi_weights = current_app.config.get("DEFAULT_PHI_WEIGHTS", DEFAULT_PHI_WEIGHTS)
    global_habitability_weights = session.get("habitability_weights", default_habitability_weights)
    global_phi_weights = session.get("phi_weights", default_phi_weights)
    
    logger.info(f"API reference_values - Global weights: hab={global_habitability_weights}, phi={global_phi_weights}")
    
    hwc_df = load_hwc_catalog(os.path.join(current_app.config["DATA_DIR"], "hwc.csv"))
    hz_gallery_df = load_hzgallery_catalog(os.path.join(current_app.config["DATA_DIR"], "table-hzgallery.csv"))
    
    reference_planets = []
    
    for planet_name in planet_names_list:
        logger.info(f"Processing reference values for planet: {planet_name}")
        api_data = fetch_exoplanet_data_api(planet_name)
        
        if api_data is None:
            logger.warning(f"Could not fetch API data for reference values of {planet_name}.")
            continue
        
        if "pl_name" not in api_data or pd.isna(api_data.get("pl_name")):
            api_data["pl_name"] = planet_name
            
        normalized_planet_name = normalize_name(api_data.get("pl_name", planet_name))
        combined_data = merge_data_sources(api_data, hwc_df, hz_gallery_df, normalized_planet_name)
        
        weights = {
            "habitability": global_habitability_weights,
            "phi": global_phi_weights
        }
        if use_individual_weights and normalized_planet_name in planet_weights:
            planet_specific_weights = planet_weights.get(normalized_planet_name, {})
            weights["habitability"] = planet_specific_weights.get("habitability", global_habitability_weights)
            weights["phi"] = planet_specific_weights.get("phi", global_phi_weights)
            logger.info(f"Using individual weights for {normalized_planet_name}: {planet_specific_weights}")
        
        processed_result = process_planet_data(
            normalized_planet_name,
            combined_data,
            weights
        )

        if processed_result:
            planet_data = processed_result.get("planet_data_dict", {})

            # Calculate reference ESI and PHI using planet-specific defaults
            esi_val, phi_val = reference_values_slider(planet_data)

            reference_planet = {
                "name": planet_data.get("pl_name", normalized_planet_name),
                "esi": esi_val,
                "phi": phi_val,
                "classification": planet_data.get("classification", "Unknown")
            }

            reference_planets.append(reference_planet)
    
    return jsonify({"planets": reference_planets})

@routes_bp.route("/results", endpoint="results")
def results():
    """Generates and displays the analysis results for selected planets.
    
    Retrieves planet names, parameter overrides, and weight configurations
    from the session. For each planet, it fetches data, applies overrides,
    processes it (calculating scores, generating plots), and creates an
    individual HTML report.
    It also generates a summary report and a combined report for all processed planets.
    Reports and charts are saved to a timestamped session directory.
    
    Returns:
        werkzeug.wrappers.response.Response: Renders the results.html template
                                             with links to the generated reports.
                                             Redirects to index if no planets are in session.
    """
    logger = current_app.logger 
    planet_names_list = session.get("planet_names_list", [])
    parameter_overrides_input = session.get("parameter_overrides_input", "")
    
    logger.info(f"Results: Full session content: {dict(session)}")
    
    default_habitability_weights = current_app.config.get("DEFAULT_HABITABILITY_WEIGHTS", DEFAULT_HABITABILITY_WEIGHTS)
    default_phi_weights = current_app.config.get("DEFAULT_PHI_WEIGHTS", DEFAULT_PHI_WEIGHTS)
    global_habitability_weights = session.get("habitability_weights", default_habitability_weights)
    global_phi_weights = session.get("phi_weights", default_phi_weights)

    use_individual_weights = session.get('use_individual_weights', False)
    individual_planet_weights_map = session.get('planet_weights', {}) 
    logger.info(f"Results: use_individual_weights={use_individual_weights}, individual_planet_weights_map={individual_planet_weights_map}")
    logger.info(f"Results: individual_planet_weights_map keys={list(individual_planet_weights_map.keys())}")

    if not planet_names_list:
        flash("No planets to process. Please perform a new search.", "warning")
        return redirect(url_for("index"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_results_dir_name = f"lifesearch_results_{timestamp}"
    absolute_session_results_dir = os.path.join(current_app.config["RESULTS_DIR"], session_results_dir_name)
    
    if not os.path.exists(absolute_session_results_dir):
        os.makedirs(absolute_session_results_dir)
    
    absolute_charts_output_dir = os.path.join(absolute_session_results_dir, "charts") 
    if not os.path.exists(absolute_charts_output_dir):
        os.makedirs(absolute_charts_output_dir)

    template_env = get_template_env()
    hwc_df = load_hwc_catalog(os.path.join(current_app.config["DATA_DIR"], "hwc.csv"))
    hz_gallery_df = load_hzgallery_catalog(os.path.join(current_app.config["DATA_DIR"], "table-hzgallery.csv"))

    all_planets_processed_data_for_summary = [] 
    report_links = []
    user_overrides = {}

    if parameter_overrides_input:
        try:
            lines = parameter_overrides_input.strip().split("\n")
            for line in lines:
                if ":" not in line: continue
                planet_part, params_part = line.split(":", 1)
                planet_key = normalize_name(planet_part.strip())
                user_overrides[planet_key] = {}
                params = params_part.strip().split(";")
                for param_entry in params:
                    if "=" not in param_entry: continue
                    key, value = param_entry.split("=", 1)
                    try:
                        user_overrides[planet_key][key.strip()] = float(value.strip())
                    except ValueError:
                        user_overrides[planet_key][key.strip()] = value.strip()
        except Exception as e:
            logger.error(f"Error parsing parameter overrides: {e}", exc_info=True)
            flash(f"Error processing parameter overrides: {e}", "danger")

    for planet_name in planet_names_list:
        logger.info(f"Processing planet: {planet_name}")
        api_data = fetch_exoplanet_data_api(planet_name)
        
        if api_data is None:
            logger.warning(f"Could not fetch API data for {planet_name}. Skipping individual report.")
            flash(f"Could not retrieve API data for {planet_name}.", "warning")
            processed_result = {
                "planet_data_dict": {"pl_name": planet_name, "classification": "N/A - API Data Missing", "hostname": "N/A"},
                "scores_for_report": {}, "sephi_scores_for_report": {}, "hz_data_tuple": None, "star_info": {}
            }
            all_planets_processed_data_for_summary.append(processed_result)
            continue

        current_planet_overrides = user_overrides.get(normalize_name(planet_name), {})
        if current_planet_overrides:
            logger.info(f"Applying overrides for {planet_name}: {current_planet_overrides}")
            for key, value in current_planet_overrides.items():
                api_data[key] = value 
        
        if "pl_name" not in api_data or pd.isna(api_data.get("pl_name")):
            api_data["pl_name"] = planet_name 

        normalized_planet_name = normalize_name(api_data.get("pl_name", planet_name))
        logger.info(f"Normalized planet name: '{planet_name}' -> '{normalized_planet_name}'")
        combined_data = merge_data_sources(api_data, hwc_df, hz_gallery_df, normalized_planet_name)
        combined_data_dict = combined_data.to_dict() if hasattr(combined_data, "to_dict") else combined_data

        if use_individual_weights:
            if normalized_planet_name in individual_planet_weights_map:
                planet_specific_weights_entry = individual_planet_weights_map.get(normalized_planet_name)
                logger.info(f"Found individual weights for '{normalized_planet_name}': {planet_specific_weights_entry}")
                current_hab_weights = planet_specific_weights_entry.get('habitability', global_habitability_weights)
                current_phi_weights = planet_specific_weights_entry.get('phi', global_phi_weights)
            else:
                logger.info(
                    f"No individual weights found for '{normalized_planet_name}' with use_individual_weights=True. "
                    "Calculating reference-based weights."
                )
                combined_data_dict["classification"] = classify_planet(
                    combined_data_dict.get("pl_masse"),
                    combined_data_dict.get("pl_rade"),
                    combined_data_dict.get("pl_eqt"),
                )
                current_hab_weights = initial_esi_weights(combined_data_dict)
                current_phi_weights = sliders_phi(combined_data_dict)
        else:
            logger.info(f"No individual weights or feature disabled. Using global weights for '{normalized_planet_name}'.")
            current_hab_weights = global_habitability_weights
            current_phi_weights = global_phi_weights

        logger.info(f"Final habitability weights for '{normalized_planet_name}': {current_hab_weights}")
        logger.info(f"Final PHI weights for '{normalized_planet_name}': {current_phi_weights}")

        processed_result = process_planet_data(
            normalized_planet_name,
            combined_data,
            {"habitability": current_hab_weights, "phi": current_phi_weights}
        )                   
        
        if not processed_result:
            logger.warning(f"Processing failed or returned no data for {planet_name}. Creating placeholder.")
            processed_result = {
                "planet_data_dict": {"pl_name": normalized_planet_name, "classification": "N/A - Processing Failed", "hostname": "N/A"},
                "scores_for_report": {}, "sephi_scores_for_report": {}, "hz_data_tuple": None, "star_info": {}
            }
            all_planets_processed_data_for_summary.append(processed_result)
            flash(f"Error processing data for {planet_name}. Check logs for details.", "warning")
            continue

        planet_data_dict = processed_result.get("planet_data_dict", {})
        scores_for_report = processed_result.get("scores_for_report", {})
        sephi_scores_for_report = processed_result.get("sephi_scores_for_report", {})
        hz_data_tuple = processed_result.get("hz_data_tuple")
        star_info = processed_result.get("star_info", {})
        
        plots = {}
        hz_plot_filename = plot_habitable_zone(
            planet_data_dict, star_info, hz_data_tuple, 
            absolute_charts_output_dir, normalized_planet_name
        )
        if hz_plot_filename:
            plots["hz_plot"] = f"charts/{hz_plot_filename}"
        
        scores_plot_filename = plot_scores_comparison(
            scores_for_report, absolute_charts_output_dir, normalized_planet_name
        )
        if scores_plot_filename:
            plots["scores_plot"] = f"charts/{scores_plot_filename}"
        
        try:
            report_path = generate_planet_report_html(
                planet_data_dict,
                scores_for_report,
                sephi_scores_for_report,
                plots,
                template_env,
                absolute_session_results_dir,
                normalized_planet_name
            )
            
            if report_path:
                report_filename = os.path.basename(report_path)
                report_links.append({
                    "name": planet_data_dict.get("pl_name", normalized_planet_name),
                    "url": url_for("routes.serve_generated_file", results_dir=session_results_dir_name, filename=report_filename),
                    "type": "individual"
                })
            else:
                flash(f"Failed to generate individual report for {planet_name}.", "warning")
        except Exception as e:
            logger.error(f"Error generating individual report for {planet_name}: {e}", exc_info=True)
            flash(f"Error generating individual report for {planet_name}: {e}", "warning")
        
        all_planets_processed_data_for_summary.append(processed_result)

    if all_planets_processed_data_for_summary:
        logger.info(f"Attempting to generate summary and combined reports for {len(all_planets_processed_data_for_summary)} processed planet entries.")
        
        try:
            summary_report_path = generate_summary_report_html(
                all_planets_processed_data_for_summary, 
                template_env, 
                absolute_session_results_dir
            )
            if summary_report_path:
                summary_filename = os.path.basename(summary_report_path)
                report_links.append({
                    "name": "Summary Report",
                    "url": url_for("routes.serve_generated_file", results_dir=session_results_dir_name, filename=summary_filename),
                    "type": "summary"
                })
                logger.info(f"Summary report generated: {summary_filename}")
            else:
                logger.warning("Failed to generate summary report.")
                flash("Failed to generate the summary report.", "warning")
        except Exception as e:
            logger.error(f"Error generating summary report: {e}", exc_info=True)
            flash(f"Error generating summary report: {e}", "warning")

        try:
            combined_report_path = generate_combined_report_html(
                all_planets_processed_data_for_summary,
                template_env,
                absolute_session_results_dir
            )
            if combined_report_path:
                combined_filename = os.path.basename(combined_report_path)
                report_links.append({
                    "name": "Combined Report",
                    "url": url_for("routes.serve_generated_file", results_dir=session_results_dir_name, filename=combined_filename),
                    "type": "combined"
                })
                logger.info(f"Combined report generated: {combined_filename}")
            else:
                logger.warning("Failed to generate combined report.")
                flash("Failed to generate the combined report.", "warning")
        except Exception as e:
            logger.error(f"Error generating combined report: {e}", exc_info=True)
            flash(f"Error generating combined report: {e}", "warning")
    else:
        logger.warning("No planet data was processed or all processing attempts failed. Skipping summary and combined reports.")
        flash("No data was processed for any of the planets, or all processing failed. Summary and combined reports could not be generated.", "warning")

    return render_template(
        "results.html",
        title="Exoplanet Analysis Results",
        report_links=report_links,
        planets_data=all_planets_processed_data_for_summary,
        session_dir=session_results_dir_name
    )

@routes_bp.route("/results_archive/<path:results_dir>/<path:filename>")
def serve_generated_file(results_dir, filename):
    """Serves generated report files and charts from the results archive.
    
    Ensures that files are served only from within the application's
    configured RESULTS_DIR to prevent directory traversal attacks.
    
    Args:
        results_dir (str): The specific timestamped subdirectory within RESULTS_DIR.
        filename (str): The name of the file to serve.
    
    Returns:
        werkzeug.wrappers.response.Response: The requested file or a 403 error
                                             if access is denied.
    """
    # Ensure the directory is always relative to RESULTS_DIR and secure
    directory = os.path.normpath(os.path.join(current_app.config["RESULTS_DIR"], results_dir))
    logger.info(f"Attempting to serve file: {filename} from directory: {directory}")
    
    # Security check: ensure the path is within RESULTS_DIR
    if not directory.startswith(os.path.normpath(current_app.config["RESULTS_DIR"])):
        logger.error(f"Attempt to access file outside of RESULTS_DIR: {directory} (filename: {filename})")
        return "Access denied", 403
        
    return send_from_directory(directory, filename)

@routes_bp.route('/api/planets/autocomplete')
def planets_autocomplete():
    """API endpoint for planet name autocompletion.
    
    Searches the local HWC (Habitable Worlds Catalog) CSV file for planet names
    matching the provided 'term' query parameter.
    
    Query Args:
        term (str): The search term for planet names (minimum 2 characters).
    
    Returns:
        flask.Response: JSON list of suggestions (up to 20) in the format
                        `[{'value': 'PlanetName'}]`. Returns an empty list
                        if the term is too short or no matches are found.
                        Returns an error JSON on file issues.
    """
    term = request.args.get('term', '').strip().lower()
    
    if not term or len(term) < 2:
        return jsonify([])

    try:
        hwc_file_path = os.path.join(current_app.config["DATA_DIR"], "hwc.csv")
        hwc_df = load_hwc_catalog(hwc_file_path) 

        suggestions = []
        #  Usar 'P_NAME' em vez de 'pl_name'
        if 'P_NAME' in hwc_df.columns:
            #  Filtrar e selecionar da coluna 'P_NAME'
            mask = hwc_df['P_NAME'].astype(str).str.lower().str.contains(term, na=False)
            matched_names = hwc_df.loc[mask, 'P_NAME'].unique() 
            
            suggestions = [{'value': name} for name in matched_names]
        else:
            #  Mensagem de log atualizada
            current_app.logger.warning("Column 'P_NAME' not found in HWC DataFrame for autocomplete.")
        
        return jsonify(suggestions[:20])

    except FileNotFoundError:
        current_app.logger.error(f"HWC catalog file not found at {hwc_file_path} for autocomplete.")
        return jsonify({"error": "Local HWC catalog (hwc.csv) not found"}), 500
    except Exception as e:
        current_app.logger.error(f"Error processing HWC for autocomplete: {e}", exc_info=True)
        return jsonify({"error": "Could not fetch suggestions from local HWC catalog"}), 500
    
@routes_bp.route('/api/planets/parameters', methods=['POST'])
def get_planet_parameters():
    """API endpoint to fetch raw parameters for a list of planet names.
    
    Accepts a JSON POST request with a list of 'planet_names'. For each name,
    it fetches data from an external API (e.g., NASA Exoplanet Archive).
    NaN values in the fetched data are replaced with None.
    
    JSON Request Body:
        {"planet_names": ["Planet1", "Planet2"]}
    
    Returns:
        flask.Response: JSON response containing a list of 'planets', where each
                        item is a dictionary of parameters for that planet,
                        or an error status if data couldn't be fetched.
    """
    data = request.json
    planet_names = data.get('planet_names', [])
    
    if not planet_names:
        return jsonify({'error': 'No planet names provided'}), 400
    
    planets_data_raw = [] # Renomeado para clareza
    
    for planet_name in planet_names:
        try:
            api_data = fetch_exoplanet_data_api(planet_name)
            
            if api_data is None:
                planets_data_raw.append({
                    'pl_name': planet_name,
                    'status': 'not_found',
                    'message': 'Planet data not found'
                })
                continue
            
            if isinstance(api_data, pd.Series):
                api_data = api_data.to_dict()
            
            planets_data_raw.append(api_data)
            
        except Exception as e:
            logger.error(f"Error fetching data for planet {planet_name}: {e}", exc_info=True)
            planets_data_raw.append({
                'pl_name': planet_name,
                'status': 'error',
                'message': str(e)
            })
    
    # >>> CHAMADA PARA A FUNÇÃO DE LIMPEZA <<<
    planets_data_cleaned = replace_nan_with_none(planets_data_raw)
    
    return jsonify({'planets': planets_data_cleaned}) # Use a lista limpa

@routes_bp.route('/api/clear-session', methods=['POST'])
def clear_session():
    """API endpoint to clear specific items from the user's session.
    
    Specifically removes 'parameter_overrides_input', 'planet_weights',
    and 'use_individual_weights' from the session.
    
    Returns:
        flask.Response: JSON response indicating the status of the operation.
    """
    logger.info(f"Clear-session called: Before clear, session content: {dict(session)}")
    session.pop("parameter_overrides_input", None)
    session.pop("planet_weights", None)
    session.pop("use_individual_weights", None)
    logger.info(f"Clear-session: After clear, session content: {dict(session)}")
    return jsonify({"status": "partial session cleared"})

@routes_bp.route('/api/save-planet-weights', methods=['POST'])
def save_planet_weights():
    """API endpoint to save planet-specific or global weight configurations to the session.
    
    Accepts a JSON POST request with `use_individual_weights` (bool) and
    `planet_weights` (dict). Planet names in `planet_weights` are normalized.
    Updates the session with these settings.
    
    JSON Request Body:
        {
            "use_individual_weights": true,
            "planet_weights": {
                "Planet1": {"habitability": {...}, "phi": {...}},
                ...
            }
        }
    
    Returns:
        flask.Response: JSON response indicating the status of the operation.
    """
    data = request.json
    use_individual_weights = data.get('use_individual_weights', False)
    planet_weights = data.get('planet_weights', {})
    
    logger.info(f"API save-planet-weights - Raw input: {data}")
    
    normalized_planet_weights = {}
    for planet_name, weights in planet_weights.items():
        normalized_name = normalize_name(planet_name)
        normalized_planet_weights[normalized_name] = weights
        logger.info(f"API save-planet-weights - Normalized '{planet_name}' to '{normalized_name}'")
    
    logger.info(f"API save-planet-weights - Normalized planet_weights: {normalized_planet_weights}")
    
    session['use_individual_weights'] = use_individual_weights
    
    if use_individual_weights and normalized_planet_weights:
        # Mesclar com pesos existentes na sessão
        existing_weights = session.get('planet_weights', {})
        existing_weights.update(normalized_planet_weights)
        session['planet_weights'] = existing_weights
        session.modified = True
        logger.info(f"API save-planet-weights - Saved to session: planet_weights={session['planet_weights']}")
        logger.info(f"API save-planet-weights - Session keys after save: {list(session.keys())}")
    
    return jsonify({'status': 'success'})

@routes_bp.route('/api/debug-session', methods=['GET'])
def debug_session():
    """API endpoint for debugging session content.
    
    Returns a JSON representation of selected session variables, useful for
    development and troubleshooting.
    
    Returns:
        flask.Response: JSON object with 'planet_names_list', 'use_individual_weights',
                        and 'planet_weights' from the session.
    """
    logger.info(f"Debugging session: planet_names_list={session.get('planet_names_list')}, use_individual_weights={session.get('use_individual_weights')}, planet_weights={session.get('planet_weights')}")
    return jsonify({
        'planet_names_list': session.get('planet_names_list'),
        'use_individual_weights': session.get('use_individual_weights'),
        'planet_weights': session.get('planet_weights')
    })

@routes_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error_code=404, error_message="Page not found."), 404

@routes_bp.app_errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return render_template("error.html", error_code=500, error_message="An internal server error occurred."), 500

@routes_bp.route('/api/save-planets-to-session', methods=['POST'])
def save_planets_to_session():
    """API endpoint to save a list of planet names to the session.
    
    Accepts a JSON POST request containing a list of 'planet_names'.
    This is typically used by the frontend to update the session when
    planets are added or removed in the UI, for example, on the 'configure' page.
    
    JSON Request Body:
        {"planet_names": ["Planet1", "Planet2", ...]}
    
    Returns:
        flask.Response: JSON response indicating 'saved' status or 'no_planets'
                        with a 400 error if the list is empty.
    """
    data = request.get_json()
    planet_names = data.get("planet_names", [])
    if planet_names:
        session["planet_names_list"] = planet_names
        current_app.logger.info(f"Saved planet_names_list to session: {planet_names}")
        return jsonify({"status": "saved"})
    return jsonify({"status": "no_planets"}), 400

