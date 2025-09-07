import os
from flask import Flask
from lifesearch.data import ensure_cache_ready


def create_app():
    # Ajuste: template_folder deve apontar para o subdiretório 'templates' dentro de 'app'
    app = Flask(__name__, template_folder="templates", static_folder="static")
    
    # Configuration
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_for_lifesearch")
    app.config["RESULTS_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lifesearch_results")
    app.config["DATA_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lifesearch", "data")
    
    # Configurações da Sessão
    app.config['SESSION_TYPE'] = 'filesystem'
    session_file_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "flask_session") 
    app.config['SESSION_FILE_DIR'] = session_file_dir
    app.config['SESSION_PERMANENT'] = False

    # Ensure results directory exists
    if not os.path.exists(app.config["RESULTS_DIR"]):
        os.makedirs(app.config["RESULTS_DIR"])
        
    # Ensure session directory exists  <-- ADIÇÃO IMPORTANTE AQUI
    if not os.path.exists(app.config['SESSION_FILE_DIR']):
        os.makedirs(app.config['SESSION_FILE_DIR'])

    ensure_cache_ready()

    # Import and register routes
    from .routes import routes_bp
    app.register_blueprint(routes_bp)

    return app
