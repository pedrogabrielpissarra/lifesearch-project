from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, send_from_directory, flash, jsonify
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime
import logging
from jinja2 import Environment, FileSystemLoader


from lifesearch.data import fetch_exoplanet_data_api, load_hwc_catalog, load_hzgallery_catalog, merge_data_sources, normalize_name
from lifesearch.reports import plot_habitable_zone, plot_scores_comparison, generate_planet_report_html, generate_summary_report_html, generate_combined_report_html
from lifesearch.lifesearch_main import process_planet_data
from .forms import PlanetSearchForm, HabitabilityWeightsForm, PHIWeightsForm # Ajuste conforme necessário
#from .utils import normalize_name, DEFAULT_HABITABILITY_WEIGHTS, DEFAULT_PHI_WEIGHTS # Ajuste
from lifesearch.data import load_hwc_catalog, load_hzgallery_catalog # Ajuste
import requests
import math
import json

logger = logging.getLogger(__name__)

def replace_nan_with_none(obj):
    if isinstance(obj, dict):
        return {k: replace_nan_with_none(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_nan_with_none(elem) for elem in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    return obj

import math # Garanta que math seja importado no topo de routes.py


def get_template_env():
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

@app.context_processor
def inject_global_vars(): # Renamed for clarity
    return {
        "current_year": datetime.now().year,
        "datetime": datetime # Make datetime object available for templates if needed
    }

@app.route("/", methods=["GET", "POST"])
@app.route("/index", methods=["GET", "POST"])
def index():
    form = PlanetSearchForm()

    # ✅ Restaura dados da sessão se acesso via ?restore=1
    if request.method == "GET" and request.args.get("restore") == "1":
        planet_names_list = session.get("planet_names_list", [])
        parameter_overrides_input = session.get("parameter_overrides_input", "")
        
        if planet_names_list:
            form.planet_names.data = ", ".join(planet_names_list)
        if parameter_overrides_input:
            form.parameter_overrides.data = parameter_overrides_input

    # 🔁 Se for uma submissão do formulário (POST)
    if request.form.get('parameter_overrides') is not None:
        planet_names_input = request.form.get('planet_names', '')
        parameter_overrides_input = request.form.get('parameter_overrides', '')
        
        planet_names_list = [name.strip() for name in planet_names_input.replace(",", "\n").split("\n") if name.strip()]

        if not planet_names_list:
            flash("Please enter valid planet names.", "danger")
            return render_template("index.html", form=form, title="LifeSearch Web")

        session["planet_names_list"] = planet_names_list
        session["parameter_overrides_input"] = parameter_overrides_input
        
        return redirect(url_for("results"))
    
    elif form.validate_on_submit():
        planet_names_input = form.planet_names.data
        parameter_overrides_input = form.parameter_overrides.data
        
        planet_names_list = [name.strip() for name in planet_names_input.replace(",", "\n").split("\n") if name.strip()]

        if not planet_names_list:
            flash("Please enter valid planet names.", "danger")
            return render_template("index.html", form=form, title="LifeSearch Web")

        session.pop("planet_names_list", None)
        session.pop("parameter_overrides_input", None)
        
        session["planet_names_list"] = planet_names_list
        session["parameter_overrides_input"] = parameter_overrides_input
        
        return redirect(url_for("results"))

    return render_template("index.html", form=form, title="LifeSearch Web")

@app.route("/configure", methods=["GET", "POST"])
def configure():
    planet_names_list = session.get("planet_names_list", [])
    logger.info(f"Configure: planet_names_list na sessão = {planet_names_list}")
    
    # These forms might still be needed if you use their definitions for factor names/labels,
    # but they won't be submitted directly from global forms anymore.
    hab_form = HabitabilityWeightsForm(prefix="hab")
    phi_form = PHIWeightsForm(prefix="phi")

    # POST logic for hab_form and phi_form will be removed as global forms are gone.
    # if request.method == "POST":
    # ... (remove the old POST handling for hab_form.submit_weights and phi_form.submit_phi_weights) ...

    # GET logic remains similar, but primarily to set up data for JS
    # Default weights (application's base defaults)
    default_hab_weights = DEFAULT_HABITABILITY_WEIGHTS 
    default_phi_weights = DEFAULT_PHI_WEIGHTS

    # Current global weights (what's currently saved globally, falls back to defaults)
    current_global_hab_weights = session.get("habitability_weights", default_hab_weights)
    current_global_phi_weights = session.get("phi_weights", default_phi_weights)
    
    # Current individual planet-specific weights
    current_planet_specific_weights = session.get("planet_weights", {})
    
    use_individual = session.get("use_individual_weights", False) # State of the checkbox

    reference_values = [] # Your existing logic to populate reference_values ...
    if planet_names_list:
        # ... (your existing logic to calculate reference_values based on current_global_weights) ...
        # This part remains the same as it's for the top "Reference Values" table.
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
            
            processed_result = process_planet_data(
                normalized_planet_name,
                combined_data,
                {"habitability": global_habitability_weights_ref, "phi": global_phi_weights_ref}
            )
            
            if processed_result:
                planet_data = processed_result.get("planet_data_dict", {})
                scores = processed_result.get("scores_for_report", {}) # scores_for_report contém ESI, PHI
                
                # Log para depuração
                logger.info(f"Configure: scores para {normalized_planet_name}: {scores}")
                
                # CORREÇÃO: Extração robusta de ESI - Usando a chave 'ESI' em maiúsculo
                esi_data = scores.get("ESI")
                if isinstance(esi_data, tuple):
                    esi_val = esi_data[0]
                elif isinstance(esi_data, (float, int)):
                    esi_val = esi_data
                else:
                    esi_val = 0.0 # Default para 0.0 se não encontrado ou formato inválido

                # CORREÇÃO: Extração robusta de PHI - Usando a chave 'PHI' em maiúsculo
                phi_data = scores.get("PHI")
                if isinstance(phi_data, tuple):
                    phi_val = phi_data[0]
                elif isinstance(phi_data, (float, int)):
                    phi_val = phi_data
                else:
                    phi_val = 0.0 # Default para 0.0

                reference_planet = {
                    "name": planet_data.get("pl_name", normalized_planet_name),
                    "esi": esi_val, # Usar o valor extraído
                    "phi": phi_val, # Usar o valor extraído
                    "classification": planet_data.get("classification", "Unknown")
                }
                reference_values.append(reference_planet)

    logger.info(f"Configure: reference_values = {reference_values}")
    # Pass hab_form and phi_form if their definitions are used by the template for something else,
    # otherwise they can be removed from here too.
    return render_template("configure.html", 
                           hab_form=hab_form, 
                           phi_form=phi_form, 
                           title="Configure Weights", 
                           reference_values=reference_values,
                           # Data for JavaScript:
                           default_hab_weights_json=json.dumps(default_hab_weights),
                           default_phi_weights_json=json.dumps(default_phi_weights),
                           current_global_hab_weights_json=json.dumps(current_global_hab_weights),
                           current_global_phi_weights_json=json.dumps(current_global_phi_weights),
                           current_planet_specific_weights_json=json.dumps(current_planet_specific_weights),
                           use_individual_weights_val=use_individual
                           )

# Novo endpoint para fornecer valores de referência dos planetas via AJAX
# CORREÇÃO: Adicionado endpoint com hífen para compatibilidade com o frontend
@app.route("/api/planets/reference-values", methods=["GET"])
def get_planet_reference_values_hyphen():
    """
    Endpoint API para fornecer valores de referência dos planetas para a página Configure Weights.
    Retorna os planetas da sessão com seus valores de ESI, PHI e classificação.
    Versão com hífen para compatibilidade com o frontend.
    """
    return get_planet_reference_values()

# Mantido o endpoint original com underscore para compatibilidade
@app.route("/api/planets/reference_values", methods=["GET"])
def get_planet_reference_values():
    """
    Endpoint API para fornecer valores de referência dos planetas para a página Configure Weights.
    Retorna os planetas da sessão com seus valores de ESI, PHI e classificação.
    """
    logger = current_app.logger
    planet_names_list = session.get("planet_names_list", [])
    logger.info(f"API reference_values: planet_names_list na sessão = {planet_names_list}")
    
    if not planet_names_list:
        return jsonify({"planets": []})
    
    # Obter pesos globais/padrão da sessão ou usar defaults
    default_habitability_weights = current_app.config.get("DEFAULT_HABITABILITY_WEIGHTS", DEFAULT_HABITABILITY_WEIGHTS)
    default_phi_weights = current_app.config.get("DEFAULT_PHI_WEIGHTS", DEFAULT_PHI_WEIGHTS)
    global_habitability_weights = session.get("habitability_weights", default_habitability_weights)
    global_phi_weights = session.get("phi_weights", default_phi_weights)
    
    # Logar os pesos globais usados
    logger.info(f"API reference_values - Global weights: hab={global_habitability_weights}, phi={global_phi_weights}")
    
    # Carregar catálogos de dados
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
        
        # Processar dados do planeta com os pesos atuais
        processed_result = process_planet_data(
            normalized_planet_name,
            combined_data,
            {"habitability": global_habitability_weights, "phi": global_phi_weights}
        )
        
        if processed_result:
            planet_data = processed_result.get("planet_data_dict", {})
            scores = processed_result.get("scores_for_report", {})
            
            # Logar os scores retornados
            logger.info(f"API reference_values - Scores for {normalized_planet_name}: {scores}")
            
            # Extração robusta de ESI
            esi_data_api = scores.get("esi")
            if isinstance(esi_data_api, tuple):
                esi_val_api = esi_data_api[0]
            elif isinstance(esi_data_api, (float, int)):
                esi_val_api = esi_data_api
            else:
                esi_val_api = 0.0
            
            # Extração robusta de PHI
            phi_data_api = scores.get("phi")
            if isinstance(phi_data_api, tuple):
                phi_val_api = phi_data_api[0]
            elif isinstance(phi_data_api, (float, int)):
                phi_val_api = phi_data_api
            else:
                phi_val_api = 0.0
            
            reference_planet = {
                "name": planet_data.get("pl_name", normalized_planet_name),
                "esi": esi_val_api,
                "phi": phi_val_api,
                "classification": planet_data.get("classification", "Unknown")
            }
            
            reference_planets.append(reference_planet)
    
    return jsonify({"planets": reference_planets})

@app.route("/results")
def results():
    logger = current_app.logger 
    planet_names_list = session.get("planet_names_list", [])
    parameter_overrides_input = session.get("parameter_overrides_input", "")
    
    default_habitability_weights = current_app.config.get("DEFAULT_HABITABILITY_WEIGHTS", DEFAULT_HABITABILITY_WEIGHTS)
    default_phi_weights = current_app.config.get("DEFAULT_PHI_WEIGHTS", DEFAULT_PHI_WEIGHTS)
    global_habitability_weights = session.get("habitability_weights", default_habitability_weights)
    global_phi_weights = session.get("phi_weights", default_phi_weights)

    use_individual_weights = session.get('use_individual_weights', False)
    individual_planet_weights_map = session.get('planet_weights', {}) 
    logger.info(f"Results: use_individual_weights={use_individual_weights}, individual_planet_weights_map={individual_planet_weights_map}")

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
        combined_data = merge_data_sources(api_data, hwc_df, hz_gallery_df, normalized_planet_name)

        current_hab_weights = global_habitability_weights
        current_phi_weights = global_phi_weights

        if use_individual_weights and normalized_planet_name in individual_planet_weights_map:
            planet_specific_weights_entry = individual_planet_weights_map.get(normalized_planet_name)
            if isinstance(planet_specific_weights_entry, dict):
                logger.info(f"Found individual weights entry for {normalized_planet_name}: {planet_specific_weights_entry}")
                if 'habitability' in planet_specific_weights_entry and planet_specific_weights_entry['habitability'] is not None:
                    current_hab_weights = planet_specific_weights_entry['habitability']
                    logger.info(f"Using individual habitability weights for {normalized_planet_name}")
                else:
                    logger.info(f"Individual habitability weights not found or None for {normalized_planet_name}, using global.")
                
                if 'phi' in planet_specific_weights_entry and planet_specific_weights_entry['phi'] is not None:
                    current_phi_weights = planet_specific_weights_entry['phi']
                    logger.info(f"Using individual PHI weights for {normalized_planet_name}")
                else:
                    logger.info(f"Individual PHI weights not found or None for {normalized_planet_name}, using global.")
            else:
                logger.warning(f"Individual weights entry for {normalized_planet_name} is not a dict: {planet_specific_weights_entry}. Using global weights.")
        elif use_individual_weights:
            logger.info(f"Individual weights enabled, but no entry found for {normalized_planet_name}. Using global weights.")
        else:
            logger.info(f"Using global weights for {normalized_planet_name} (individual weights disabled).")
        
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

        # Gerar gráficos para o relatório
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
        
        # Gerar relatório individual
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
                    "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=report_filename),
                    "type": "individual"
                })
            else:
                flash(f"Failed to generate individual report for {planet_name}.", "warning")
        except Exception as e:
            logger.error(f"Error generating individual report for {planet_name}: {e}", exc_info=True)
            flash(f"Error generating individual report for {planet_name}: {e}", "warning")
        
        all_planets_processed_data_for_summary.append(processed_result)

    # Gerar relatórios de resumo e combinado
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
                    "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=summary_filename),
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
                    "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=combined_filename),
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

@app.route("/results_archive/<path:results_dir>/<path:filename>")
def serve_generated_file(results_dir, filename):
    # Ensure the directory is always relative to RESULTS_DIR and secure
    directory = os.path.normpath(os.path.join(current_app.config["RESULTS_DIR"], results_dir))
    logger.info(f"Attempting to serve file: {filename} from directory: {directory}")
    
    # Security check: ensure the path is within RESULTS_DIR
    if not directory.startswith(os.path.normpath(current_app.config["RESULTS_DIR"])):
        logger.error(f"Attempt to access file outside of RESULTS_DIR: {directory} (filename: {filename})")
        return "Access denied", 403
        
    return send_from_directory(directory, filename)

@app.route('/api/planets/autocomplete')
def planets_autocomplete():
    term = request.args.get('term', '').strip().lower()
    
    if not term or len(term) < 2:
        return jsonify([])

    try:
        hwc_file_path = os.path.join(current_app.config["DATA_DIR"], "hwc.csv")
        hwc_df = load_hwc_catalog(hwc_file_path) 

        suggestions = []
        # MODIFICAÇÃO AQUI: Usar 'P_NAME' em vez de 'pl_name'
        if 'P_NAME' in hwc_df.columns:
            # MODIFICAÇÃO AQUI: Filtrar e selecionar da coluna 'P_NAME'
            mask = hwc_df['P_NAME'].astype(str).str.lower().str.contains(term, na=False)
            matched_names = hwc_df.loc[mask, 'P_NAME'].unique() 
            
            suggestions = [{'value': name} for name in matched_names]
        else:
            # MODIFICAÇÃO AQUI: Mensagem de log atualizada
            current_app.logger.warning("Column 'P_NAME' not found in HWC DataFrame for autocomplete.")
        
        return jsonify(suggestions[:20])

    except FileNotFoundError:
        current_app.logger.error(f"HWC catalog file not found at {hwc_file_path} for autocomplete.")
        return jsonify({"error": "Local HWC catalog (hwc.csv) not found"}), 500
    except Exception as e:
        current_app.logger.error(f"Error processing HWC for autocomplete: {e}", exc_info=True)
        return jsonify({"error": "Could not fetch suggestions from local HWC catalog"}), 500
    
# Novo endpoint para buscar parâmetros dos planetas
@app.route('/api/planets/parameters', methods=['POST'])
def get_planet_parameters():
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
    
    # >>> ADICIONE A CHAMADA PARA A FUNÇÃO DE LIMPEZA AQUI <<<
    planets_data_cleaned = replace_nan_with_none(planets_data_raw)
    
    return jsonify({'planets': planets_data_cleaned}) # Use a lista limpa

@app.route('/api/clear-session', methods=['POST'])
def clear_session():
    session.pop("parameter_overrides_input", None)
    session.pop("planet_weights", None)
    session.pop("use_individual_weights", None)
    # NÃO remove planet_names_list aqui
    return jsonify({"status": "partial session cleared"})

@app.route('/api/save-planet-weights', methods=['POST'])
def save_planet_weights():
    data = request.json
    use_individual_weights = data.get('use_individual_weights', False)
    planet_weights = data.get('planet_weights', {})
    
    # Logar os pesos recebidos
    logger.info(f"API save-planet-weights - Received: use_individual_weights={use_individual_weights}, planet_weights={planet_weights}")
    
    session['use_individual_weights'] = use_individual_weights
    
    if use_individual_weights and planet_weights:
        session['planet_weights'] = planet_weights
    
    return jsonify({'status': 'success'})


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error_code=404, error_message="Page not found."), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return render_template("error.html", error_code=500, error_message="An internal server error occurred."), 500

@app.route('/api/save-planets-to-session', methods=['POST'])
def save_planets_to_session():
    data = request.get_json()
    planet_names = data.get("planet_names", [])
    if planet_names:
        session["planet_names_list"] = planet_names
        current_app.logger.info(f"Saved planet_names_list to session: {planet_names}")
        return jsonify({"status": "saved"})
    return jsonify({"status": "no_planets"}), 400

