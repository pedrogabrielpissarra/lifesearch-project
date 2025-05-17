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

def _sanitize_single_value_for_reports(value):
    """
    Higieniza um único valor para relatórios.
    Converte strings específicas e float NaN para None.
    """
    if isinstance(value, str):
        # Converte representações de string comuns de dados ausentes/inválidos para None
        if value.strip().upper() in ["N/A", "NAN", "UNKNOWN", "MISSING", "-", ""]:
            return None
    elif isinstance(value, float) and math.isnan(value):
        return None
    return value

def sanitize_data_structure_for_reports(obj):
    """
    Higieniza recursivamente uma estrutura de dados (dicionários, listas) destinada a relatórios.
    Valores de string problemáticos ou NaNs em contextos numéricos são convertidos para None.
    """
    if isinstance(obj, dict):
        return {k: sanitize_data_structure_for_reports(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        # Lida com listas do tipo score: ex: [valor, string_cor]
        # Verifica se o segundo elemento é uma string e começa com '#' (indicando uma cor)
        if len(obj) == 2 and isinstance(obj[1], str) and obj[1].startswith("#"):
            sanitized_value = _sanitize_single_value_for_reports(obj[0])
            return [sanitized_value, obj[1]]
        else:
            # Para outras listas, higieniza cada elemento
            return [sanitize_data_structure_for_reports(elem) for elem in obj]
    else:
        # Para valores autônomos (int, float, string, bool, etc.)
        return _sanitize_single_value_for_reports(obj)


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
    
    # Verificar se é uma submissão do formulário de parâmetros
    if request.form.get('parameter_overrides') is not None:
        # Obter os dados do formulário de parâmetros
        planet_names_input = request.form.get('planet_names', '')
        parameter_overrides_input = request.form.get('parameter_overrides', '')
        
        planet_names_list = [name.strip() for name in planet_names_input.replace(",", "\n").split("\n") if name.strip()]

        if not planet_names_list:
            flash("Please enter valid planet names.", "danger")
            return render_template("index.html", form=form, title="LifeSearch Web")

        session["planet_names_list"] = planet_names_list
        session["parameter_overrides_input"] = parameter_overrides_input
        
        logger.info(f"Planet names submitted from parameters form: {planet_names_list}")
        logger.info(f"Parameter overrides: {parameter_overrides_input}")
        
        return redirect(url_for("results"))
    
    # Processamento original do formulário de busca
    elif form.validate_on_submit():
        planet_names_input = form.planet_names.data
        parameter_overrides_input = form.parameter_overrides.data
        
        planet_names_list = [name.strip() for name in planet_names_input.replace(",", "\n").split("\n") if name.strip()]

        if not planet_names_list:
            flash("Please enter valid planet names.", "danger")
            return render_template("index.html", form=form, title="LifeSearch Web")

        # Limpar dados anteriores da sessão
        session.pop("planet_names_list", None)
        session.pop("parameter_overrides_input", None)
        
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
    logger = current_app.logger 
    planet_names_list = session.get("planet_names_list", [])
    parameter_overrides_input = session.get("parameter_overrides_input", "")
    
    # Obter pesos globais/padrão da sessão ou usar defaults
    default_habitability_weights = current_app.config.get("DEFAULT_HABITABILITY_WEIGHTS", DEFAULT_HABITABILITY_WEIGHTS)
    default_phi_weights = current_app.config.get("DEFAULT_PHI_WEIGHTS", DEFAULT_PHI_WEIGHTS)
    global_habitability_weights = session.get("habitability_weights", default_habitability_weights)
    global_phi_weights = session.get("phi_weights", default_phi_weights)

    # >>> NOVAS LINHAS PARA PESOS INDIVIDUAIS <<<
    use_individual_weights = session.get('use_individual_weights', False)
    # Renomeado para evitar conflito com as variáveis de pesos atuais no loop
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

                # --- CORREÇÃO: Definir os pesos a serem usados para este planeta ---
        current_hab_weights = global_habitability_weights
        current_phi_weights = global_phi_weights

        if use_individual_weights and normalized_planet_name in individual_planet_weights_map:
            planet_specific_weights_entry = individual_planet_weights_map.get(normalized_planet_name)
            if isinstance(planet_specific_weights_entry, dict):
                logger.info(f"Found individual weights entry for {normalized_planet_name}: {planet_specific_weights_entry}")
                if 'habitability' in planet_specific_weights_entry and planet_specific_weights_entry['habitability'] is not None:
                    current_hab_weights = planet_specific_weights_entry['habitability']
                    logger.info(f"Using individual habitability weights for {normalized_planet_name}")
                else: # Se a chave 'habitability' não existir ou for None, mantém global
                    logger.info(f"Individual habitability weights not found or None for {normalized_planet_name}, using global.")
                
                if 'phi' in planet_specific_weights_entry and planet_specific_weights_entry['phi'] is not None:
                    current_phi_weights = planet_specific_weights_entry['phi']
                    logger.info(f"Using individual PHI weights for {normalized_planet_name}")
                else: # Se a chave 'phi' não existir ou for None, mantém global
                    logger.info(f"Individual PHI weights not found or None for {normalized_planet_name}, using global.")
            else:
                logger.warning(f"Individual weights entry for {normalized_planet_name} is not a dict: {planet_specific_weights_entry}. Using global weights.")
        elif use_individual_weights: # Se use_individual_weights é True mas o planeta não está no mapa
            logger.info(f"Individual weights enabled, but no entry found for {normalized_planet_name}. Using global weights.")
        else: # Se use_individual_weights é False
            logger.info(f"Using global weights for {normalized_planet_name} (individual weights disabled).")
        # --- FIM DA CORREÇÃO ---
        
        # Chamada corrigida para process_planet_data
        processed_result = process_planet_data(
            normalized_planet_name, 
            combined_data, 
            {"habitability": current_hab_weights, "phi": current_phi_weights}
        )
        
        if not processed_result:
            # ... (lógica existente) ...
            processed_result = { # Garante que processed_result exista para append
                "planet_data_dict": {"pl_name": normalized_planet_name, "classification": "N/A - Processing Failed", "hostname": "N/A"},
                "scores_for_report": {}, "sephi_scores_for_report": {}, "hz_data_tuple": None, "star_info": {}
            }
            flash(f"Limited data or processing error for {normalized_planet_name}. Report may be incomplete or missing.", "warning")

        all_planets_processed_data_for_summary.append(processed_result)

        # Prosseguir com relatórios individuais apenas se processed_result for válido
        if processed_result and processed_result.get("planet_data_dict") and processed_result.get("planet_data_dict").get("classification") not in ["N/A - API Data Missing", "N/A - Processing Failed"]:
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
             logger.warning(f"Skipping individual report for {normalized_planet_name} due to previous processing issues or missing data.")


    # Sempre tentar gerar relatórios combinados se houver algo para processar
    if all_planets_processed_data_for_summary:
        # Use as funções de geração de relatório (que devem ser as versões corrigidas)
        # Ex: generate_summary_report_html_corrigido ou a versão original se ela foi substituída pela corrigida
        # Dentro da função results() em C:\lifesearch\app\routes.py
        sanitized_list_for_reports = [sanitize_data_structure_for_reports(planet_data) for planet_data in all_planets_processed_data_for_summary]

    # Use os dados higienizados para a geração do relatório
        summary_report_abs_path = generate_summary_report_html(
            sanitized_list_for_reports,  # Usa dados higienizados
            template_env,
            absolute_session_results_dir
        )
        if summary_report_abs_path:
            summary_filename = os.path.basename(summary_report_abs_path)
            report_links.append({
                "name": "Summary Report",
                "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=summary_filename)
            })
    
        combined_report_abs_path = generate_combined_report_html(
            sanitized_list_for_reports,  # Usa dados higienizados
            template_env,
            absolute_session_results_dir
        )
        if combined_report_abs_path:
            combined_filename = os.path.basename(combined_report_abs_path)
            report_links.append({
                "name": "Combined Report",
                "url": url_for("serve_generated_file", results_dir=session_results_dir_name, filename=combined_filename)
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

@app.route('/api/planets/reference-values')
def get_reference_values():
    planet_names_list = session.get("planet_names_list", [])
    logger.info(f"API /api/planets/reference-values: planet_names_list na sessão é: {planet_names_list}") # Log para depuração
    habitability_weights = session.get("habitability_weights", DEFAULT_HABITABILITY_WEIGHTS)
    phi_weights = session.get("phi_weights", DEFAULT_PHI_WEIGHTS)
    
    # >>> CORREÇÃO: Carregar configurações de pesos individuais da sessão <<<
    use_individual_weights = session.get('use_individual_weights', False)
    # Usar o mesmo nome de variável que na rota /results para clareza, 
    # assumindo que 'planet_weights' é a chave correta na sessão.
    individual_planet_weights_map = session.get('planet_weights', {}) 
    # Log para depuração
    logger.info(f"get_reference_values: use_individual_weights={use_individual_weights}, individual_planet_weights_map={individual_planet_weights_map}")
    
    if not planet_names_list:
        return jsonify({'planets': []})
    
    reference_data = []
    
    # Carregar catálogos
    hwc_df = load_hwc_catalog(os.path.join(current_app.config["DATA_DIR"], "hwc.csv"))
    hz_gallery_df = load_hzgallery_catalog(os.path.join(current_app.config["DATA_DIR"], "table-hzgallery.csv"))
    
    for planet_name_from_list in planet_names_list: # Renomeado para evitar conflito com normalized_planet_name
        try:
            api_data = fetch_exoplanet_data_api(planet_name_from_list) # Usar o nome original da lista aqui
            
            if api_data is None:
                logger.warning(f"API data not found for {planet_name_from_list} in get_reference_values. Skipping.")
                continue
            
            # Obter o nome normalizado a partir dos dados da API, ou do nome da lista como fallback
            normalized_planet_name = normalize_name(api_data.get("pl_name", planet_name_from_list))
            combined_data = merge_data_sources(api_data, hwc_df, hz_gallery_df, normalized_planet_name)

            # Usar pesos globais como padrão
            current_habitability_weights = habitability_weights
            current_phi_weights = phi_weights
        
            # >>> CORREÇÃO: Aplicar lógica de pesos individuais <<<
            if use_individual_weights and normalized_planet_name in individual_planet_weights_map:
                planet_specific_weights_entry = individual_planet_weights_map.get(normalized_planet_name)
                if isinstance(planet_specific_weights_entry, dict):
                    logger.info(f"Reference Values: Found individual weights for {normalized_planet_name}: {planet_specific_weights_entry}")
                    if 'habitability' in planet_specific_weights_entry and planet_specific_weights_entry['habitability'] is not None:
                        current_habitability_weights = planet_specific_weights_entry['habitability']
                    if 'phi' in planet_specific_weights_entry and planet_specific_weights_entry['phi'] is not None:
                        current_phi_weights = planet_specific_weights_entry['phi']
                else:
                    logger.warning(f"Reference Values: Individual weights entry for {normalized_planet_name} is not a dict. Using global.")
            elif use_individual_weights:
                 logger.info(f"Reference Values: Individual weights enabled, but no entry for {normalized_planet_name}. Using global.")
            else:
                 logger.info(f"Reference Values: Using global weights for {normalized_planet_name} (individual weights disabled).")
        
            processed_result = process_planet_data(
                normalized_planet_name, 
                combined_data, 
                {"habitability": current_habitability_weights, "phi": current_phi_weights}
            )            
            
            if not processed_result:
                logger.warning(f"Processing failed for {normalized_planet_name} in get_reference_values. Skipping.")
                continue
            
            scores = processed_result.get("scores_for_report", {})
            esi_score = 0
            if "ESI" in scores and isinstance(scores.get("ESI"), (list, tuple)) and len(scores["ESI"]) > 0:
                try:
                    esi_value = scores["ESI"][0]
                    if esi_value is not None: # Checar se não é None antes de converter
                        esi_score = float(esi_value) / 100  # Normalizar para 0-1
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse ESI score for {normalized_planet_name}: {scores['ESI'][0]}")
                    pass # Mantém esi_score como 0
            
            phi_score_value = 0 # Renomeado para evitar conflito com phi_weights
            if "PHI" in scores and isinstance(scores.get("PHI"), (list, tuple)) and len(scores["PHI"]) > 0:
                try:
                    phi_val = scores["PHI"][0]
                    if phi_val is not None: # Checar se não é None
                        phi_score_value = float(phi_val) / 100  # Normalizar para 0-1
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse PHI score for {normalized_planet_name}: {scores['PHI'][0]}")
                    pass # Mantém phi_score_value como 0
            
            classification = processed_result.get("planet_data_dict", {}).get("classification", "Unknown")
            
            reference_data.append({
                'name': normalized_planet_name, # Usar o nome normalizado aqui também para consistência
                'esi': esi_score,
                'phi': phi_score_value,
                'classification': classification
            })
            
        except Exception as e:
            logger.error(f"Error calculating reference values for {planet_name_from_list}: {e}", exc_info=True)
    
    logger.info(f"Returning reference data: {reference_data}")
    return jsonify({'planets': reference_data})

@app.route('/api/clear-session', methods=['POST'])
def clear_session():
    # Limpar dados de planetas da sessão
    session.pop("planet_names_list", None)
    session.pop("parameter_overrides_input", None)
    return jsonify({'status': 'success'})

@app.route('/api/save-planet-weights', methods=['POST'])
def save_planet_weights():
    data = request.json
    use_individual_weights = data.get('use_individual_weights', False)
    planet_weights = data.get('planet_weights', {})
    
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


