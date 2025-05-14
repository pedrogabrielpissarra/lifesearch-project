import os
from flask import Flask

def create_app():
    # Ajuste: template_folder deve apontar para o subdiretório 'templates' dentro de 'app'
    app = Flask(__name__, template_folder="templates", static_folder="static")
    
    # Configuration
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_for_lifesearch")
    app.config["RESULTS_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lifesearch_results")
    # Charts são salvos dentro de cada pasta de resultado específica da sessão, não diretamente em app/static/charts globalmente.
    # A rota serve_generated_file cuidará de servir esses charts de dentro das pastas de resultados.
    # app.config["CHARTS_DIR"] = os.path.join(app.static_folder, "charts") # Este CHARTS_DIR global pode não ser necessário da forma como está.
    app.config["DATA_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lifesearch", "data")

    # Ensure results directory exists (charts dir will be created per session)
    if not os.path.exists(app.config["RESULTS_DIR"]):
        os.makedirs(app.config["RESULTS_DIR"])
    # if not os.path.exists(app.config["CHARTS_DIR"]):
    #     os.makedirs(app.config["CHARTS_DIR"])

    # Import and register routes
    with app.app_context():
        from . import routes # routes.py usará current_app para registrar as rotas

    return app