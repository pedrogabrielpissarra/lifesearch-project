from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, send_from_directory, flash
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime
import logging
from jinja2 import Environment, FileSystemLoader

from app.forms import PlanetSearchForm, HabitabilityWeightsForm, PHIWeightsForm
from lifesearch.data import fetch_exoplanet_data_api, load_hwc_catalog, load_hzgallery_catalog, merge_data_sources, normalize_name
from lifesearch.reports import plot_habitable_zone, plot_scores_comparison, generate_planet_report_html, generate_summary_report_html, generate_combined_report_html
from lifesearch.lifesearch_main import process_planet_data

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
    planet_names_list = session.get("planet_names_list", [])
    parameter_overrides_input = session.get("parameter_overrides_input", "")
    habitability_weights = session.get("habitability_weights", DEFAULT_HABITABILITY_WEIGHTS)
    phi_weights = session.get("phi_weights", DEFAULT_PHI_WEIGHTS)

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

    all_planets_processed_data_for_summary = [] # For summary/combined reports
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
            logger.error(f"Error parsing parameter overrides: {e}")
            flash(f"Error processing parameter overrides: {e}", "danger")

    for planet_name in planet_names_list:
        logger.info(f"Processing planet: {planet_name}")
        api_data = fetch_exoplanet_data_api(planet_name)
        
        if api_data is None:
            logger.warning(f"Could not fetch API data for {planet_name}. Skipping.")
            flash(f"Could not retrieve API data for {planet_name}.", "warning")
            continue

        current_planet_overrides = user_overrides.get(normalize_name(planet_name), {})
        if current_planet_overrides:
            logger.info(f"Applying overrides for {planet_name}: {current_planet_overrides}")
            for key, value in current_planet_overrides.items():
                api_data[key] = value # Apply override to the fetched API data
        
        if "pl_name" not in api_data or pd.isna(api_data.get("pl_name")):
            api_data["pl_name"] = planet_name # Ensure pl_name is set

        normalized_planet_name = normalize_name(api_data.get("pl_name", planet_name))
        # Pass the potentially overridden api_data to merge_data_sources
        combined_data = merge_data_sources(api_data, hwc_df, hz_gallery_df, normalized_planet_name)
        
        # Pass combined_data (which includes API data and overrides) to process_planet_data
        processed_result = process_planet_data(normalized_planet_name, combined_data, {"habitability": habitability_weights, "phi": phi_weights})
        if not processed_result:
            flash(f"Failed to process data for {planet_name}.", "danger")
            continue

        scores_for_report = processed_result["scores_for_report"]
        sephi_scores_for_report = processed_result["sephi_scores_for_report"]
        hz_data_for_plot = processed_result["hz_data_tuple"]
        planet_data_dict_for_report = processed_result["planet_data_dict"]

        planet_name_slug = secure_filename(normalized_planet_name.replace(" ", "_"))
        plots = {}

        hz_plot_filename = plot_habitable_zone(planet_data_dict_for_report, planet_data_dict_for_report.get("star_info",{}), hz_data_for_plot, absolute_charts_output_dir, planet_name_slug)
        if hz_plot_filename:
            plots["habitable_zone_plot"] = os.path.join("charts", hz_plot_filename).replace("\\", "/")

        scores_plot_filename = plot_scores_comparison(scores_for_report, absolute_charts_output_dir, planet_name_slug)
        if scores_plot_filename:
            plots["scores_plot"] = os.path.join("charts", scores_plot_filename).replace("\\", "/")

        report_html_abs_path = generate_planet_report_html(planet_data_dict_for_report, scores_for_report, sephi_scores_for_report, plots, template_env, absolute_session_results_dir, planet_name_slug)
        
        if report_html_abs_path:
            report_filename = os.path.basename(report_html_abs_path)
            report_links.append({
                "name": f"Individual Report: {planet_data_dict_for_report.get("pl_name", planet_name)}",
                "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=report_filename)
            })
            # Append the full processed_result for summary/combined reports
            all_planets_processed_data_for_summary.append(processed_result)
        else:
            flash(f"Failed to generate report for {planet_name}.", "danger")

    if len(all_planets_processed_data_for_summary) > 0:
        # Pass all_planets_processed_data_for_summary to summary/combined generators
        summary_report_abs_path = generate_summary_report_html(all_planets_processed_data_for_summary, template_env, absolute_session_results_dir)
        if summary_report_abs_path:
            summary_filename = os.path.basename(summary_report_abs_path)
            report_links.append({
                "name": "Summary Report",
                "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=summary_filename)
            })
        
        combined_report_abs_path = generate_combined_report_html(all_planets_processed_data_for_summary, template_env, absolute_session_results_dir)
        if combined_report_abs_path:
            combined_filename = os.path.basename(combined_report_abs_path)
            report_links.append({
                "name": "Combined Report",
                "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=combined_filename)
            })

    if not report_links:
        flash("No reports were generated. Check logs for more details.", "warning")
        return redirect(url_for("index"))

    # Pass session_results_dir_name to results.html for plot URLs if needed there (though individual reports handle it now)
    return render_template("results.html", title="Search Results", report_links=report_links, session_results_dir_name=session_results_dir_name)

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

@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error_code=404, error_message="Page not found."), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return render_template("error.html", error_code=500, error_message="An internal server error occurred."), 500


