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

logger = logging.getLogger(__name__)

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
    if form.validate_on_submit():
        planet_names_input = form.planet_names.data
        parameter_overrides_input = form.parameter_overrides.data
        
        planet_names_list = [name.strip() for name in planet_names_input.replace(",", "\n").split("\n") if name.strip()]

        if not planet_names_list:
            flash("Please enter valid planet names.", "danger")
            return render_template("index.html", form=form, title="LifeSearch Web")

        session["planet_names_list"] = planet_names_list
        session["parameter_overrides_input"] = parameter_overrides_input
        
        logger.info(f"Planet names submitted: {planet_names_list}")
        logger.info(f"Parameter overrides: {parameter_overrides_input}")
        
        return redirect(url_for("results"))
        
    return render_template("index.html", form=form, title="LifeSearch Web")

@app.route("/configure", methods=["GET", "POST"])
def configure():
    hab_form = HabitabilityWeightsForm(prefix="hab")
    phi_form = PHIWeightsForm(prefix="phi")

    if request.method == "POST":
        if hab_form.submit_weights.data and hab_form.validate():
            updated_hab_weights = {}
            for field_name, _ in hab_form.factors.items():
                form_field_name = field_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
                updated_hab_weights[field_name] = getattr(hab_form, form_field_name).data
            session["habitability_weights"] = updated_hab_weights
            flash("Habitability weights updated!", "success")
            logger.info(f"Habitability weights updated: {updated_hab_weights}")
            return redirect(url_for("configure"))

        if phi_form.submit_phi_weights.data and phi_form.validate():
            updated_phi_weights = {}
            for field_name, _ in phi_form.phi_factors.items():
                form_field_name = field_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
                updated_phi_weights[field_name] = getattr(phi_form, form_field_name).data
            session["phi_weights"] = updated_phi_weights
            flash("PHI weights updated!", "success")
            logger.info(f"PHI weights updated: {updated_phi_weights}")
            return redirect(url_for("configure"))

    if request.method == "GET":
        current_hab_weights = session.get("habitability_weights", DEFAULT_HABITABILITY_WEIGHTS)
        for field_name, default_value in DEFAULT_HABITABILITY_WEIGHTS.items():
            form_field_name = field_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
            actual_value = current_hab_weights.get(field_name, default_value)
            getattr(hab_form, form_field_name).data = actual_value if actual_value is not None else default_value

        current_phi_weights = session.get("phi_weights", DEFAULT_PHI_WEIGHTS)
        for field_name, default_value in DEFAULT_PHI_WEIGHTS.items():
            form_field_name = field_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
            actual_value = current_phi_weights.get(field_name, default_value)
            getattr(phi_form, form_field_name).data = actual_value if actual_value is not None else default_value
            
    return render_template("configure.html", hab_form=hab_form, phi_form=phi_form, title="Configure Weights")

@app.route("/results")
def results():
    logger = current_app.logger # Use o logger da aplicação Flask
    planet_names_list = session.get("planet_names_list", [])
    parameter_overrides_input = session.get("parameter_overrides_input", "")
    habitability_weights = session.get("habitability_weights", DEFAULT_HABITABILITY_WEIGHTS)
    phi_weights = session.get("phi_weights", DEFAULT_PHI_WEIGHTS)

    if not planet_names_list:
        flash("No planets to process. Please perform a new search.", "warning")
        return redirect(url_for("index")) # ou url_for("index")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_results_dir_name = f"lifesearch_results_{timestamp}"
    absolute_session_results_dir = os.path.join(current_app.config["RESULTS_DIR"], session_results_dir_name)
    
    if not os.path.exists(absolute_session_results_dir):
        os.makedirs(absolute_session_results_dir)
    
    absolute_charts_output_dir = os.path.join(absolute_session_results_dir, "charts") 
    if not os.path.exists(absolute_charts_output_dir):
        os.makedirs(absolute_charts_output_dir)

    template_env = get_template_env()
    # Assegure-se que DATA_DIR está configurado corretamente em config.py
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
            logger.warning(f"Could not fetch API data for {planet_name}. Skipping individual report, but will be included in combined if possible.")
            flash(f"Could not retrieve API data for {planet_name}.", "warning")
            # Criar um processed_result mínimo para este planeta
            processed_result = {
                "planet_data_dict": {"pl_name": planet_name, "classification": "N/A - API Data Missing", "hostname": "N/A"},
                "scores_for_report": {}, "sephi_scores_for_report": {}, "hz_data_tuple": None, "star_info": {}
            }
            all_planets_processed_data_for_summary.append(processed_result)
            continue # Pula para o próximo planeta para relatórios individuais

        current_planet_overrides = user_overrides.get(normalize_name(planet_name), {})
        if current_planet_overrides:
            logger.info(f"Applying overrides for {planet_name}: {current_planet_overrides}")
            for key, value in current_planet_overrides.items():
                api_data[key] = value 
        
        if "pl_name" not in api_data or pd.isna(api_data.get("pl_name")):
            api_data["pl_name"] = planet_name 

        normalized_planet_name = normalize_name(api_data.get("pl_name", planet_name))
        combined_data = merge_data_sources(api_data, hwc_df, hz_gallery_df, normalized_planet_name)
        
        processed_result = process_planet_data(normalized_planet_name, combined_data, {"habitability": habitability_weights, "phi": phi_weights})
        
        if not processed_result:
            logger.warning(f"Failed to process data for {planet_name}. Creating default/minimal result for combined reports.")
            processed_result = {
                "planet_data_dict": {"pl_name": planet_name, "classification": "N/A - Processing Failed", "hostname": "N/A"},
                "scores_for_report": {}, "sephi_scores_for_report": {}, "hz_data_tuple": None, "star_info": {}
            }
            flash(f"Limited data or processing error for {planet_name}. Report may be incomplete or missing.", "warning")
        
        # Mesmo com dados limitados/falha, adicione à lista para tentativa de relatório combinado
        all_planets_processed_data_for_summary.append(processed_result)

        # Prosseguir com relatórios individuais apenas se processed_result for válido
        if processed_result and processed_result.get("planet_data_dict"):
            scores_for_report = processed_result.get("scores_for_report", {})
            sephi_scores_for_report = processed_result.get("sephi_scores_for_report", {})
            hz_data_for_plot = processed_result.get("hz_data_tuple")
            planet_data_dict_for_report = processed_result.get("planet_data_dict", {}) # Já é o dict

            planet_name_slug = secure_filename(normalized_planet_name.replace(" ", "_"))
            plots = {}

            hz_plot_filename = plot_habitable_zone(planet_data_dict_for_report, planet_data_dict_for_report.get("star_info",{}), hz_data_for_plot, absolute_charts_output_dir, planet_name_slug)
            if hz_plot_filename:
                plots["habitable_zone_plot"] = os.path.join("charts", hz_plot_filename).replace("\\", "/")

            scores_plot_filename = plot_scores_comparison(scores_for_report, absolute_charts_output_dir, planet_name_slug)
            if scores_plot_filename:
                plots["scores_plot"] = os.path.join("charts", scores_plot_filename).replace("\\", "/")

            # Supondo que generate_planet_report_html também foi ajustado para ser mais robusto
            report_html_abs_path = generate_planet_report_html(
                planet_data_dict_for_report, 
                scores_for_report, 
                sephi_scores_for_report, 
                plots, 
                template_env, 
                absolute_session_results_dir, 
                planet_name_slug
            )
            
            if report_html_abs_path:
                report_filename = os.path.basename(report_html_abs_path)
                report_links.append({
                    "name": f"Individual Report: {planet_data_dict_for_report.get('pl_name', planet_name)}",
                    "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=report_filename) # ou "serve_generated_file"
                })
            else:
                flash(f"Failed to generate individual report for {planet_name}.", "danger")
        else:
             logger.warning(f"Skipping individual report for {planet_name} due to previous processing issues.")


    # Sempre tentar gerar relatórios combinados se houver algo para processar
    if all_planets_processed_data_for_summary:
        # Use as funções de geração de relatório (que devem ser as versões corrigidas)
        # Ex: generate_summary_report_html_corrigido ou a versão original se ela foi substituída pela corrigida
        summary_report_abs_path = generate_summary_report_html(all_planets_processed_data_for_summary, template_env, absolute_session_results_dir)
        if summary_report_abs_path:
            summary_filename = os.path.basename(summary_report_abs_path)
            report_links.append({
                "name": "Summary Report",
                "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=summary_filename) # ou "serve_generated_file"
            })
        
        combined_report_abs_path = generate_combined_report_html(all_planets_processed_data_for_summary, template_env, absolute_session_results_dir)
        if combined_report_abs_path:
            combined_filename = os.path.basename(combined_report_abs_path)
            report_links.append({
                "name": "Combined Report",
                "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=combined_filename) # ou "serve_generated_file"
            })
    else:
        logger.warning("No data processed for any planet, skipping combined reports.")


    if not report_links:
        flash("No reports were generated. Check logs for more details.", "warning")
        return redirect(url_for("index")) # ou url_for("index")

    return render_template(
        "results.html", 
        title="Search Results", 
        report_links=report_links, 
        session_results_dir_name=session_results_dir_name
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

@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error_code=404, error_message="Page not found."), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return render_template("error.html", error_code=500, error_message="An internal server error occurred."), 500


