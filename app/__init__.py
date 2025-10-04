import importlib
import logging
import os
import tempfile
from typing import Optional

from flask import Flask
from lifesearch.data import ensure_cache_ready


logger = logging.getLogger(__name__)


def _prepare_directory(env_var: str, default_subdir: str, *, description: Optional[str] = None) -> str:
    """Return a writable directory for application storage.

    The function attempts to create (or reuse) a directory specified via the
    ``env_var`` environment variable. If the variable is not set or the
    directory cannot be created (for example, because the container runs with a
    random non-root UID in OpenShift), it falls back to a project-relative
    directory. Should that also fail, a final attempt is made in the system
    temporary directory. This ensures the application always has a writable
    location for generated artefacts such as cached reports or session files.

    Args:
        env_var: Name of the environment variable that can override the
            directory.
        default_subdir: The folder name to use for the project and temporary
            fallbacks.
        description: Optional human-readable description for logging
            (e.g. "results" or "session").

    Returns:
        The absolute path to a writable directory.

    Raises:
        RuntimeError: If no writable directory could be prepared.
    """

    description = description or default_subdir
    candidates = []

    env_path = os.environ.get(env_var)
    if env_path:
        candidates.append(os.path.abspath(env_path))

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates.append(os.path.join(project_root, default_subdir))
    candidates.append(os.path.join(tempfile.gettempdir(), default_subdir))

    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            if os.access(path, os.W_OK | os.X_OK):
                if path != env_path:
                    logger.debug("Using %s directory at %s", description, path)
                return path
            logger.warning("Directory %s is not writable: %s", description, path)
        except OSError as exc:  # pragma: no cover - depends on filesystem permissions
            logger.warning(
                "Failed to prepare %s directory at %s: %s", description, path, exc
            )

    raise RuntimeError(f"Unable to prepare writable directory for {description} storage")


def create_app():
    # Initialize Flask app
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_for_lifesearch")
    app.config["RESULTS_DIR"] = _prepare_directory(
        "LIFESEARCH_RESULTS_DIR", "lifesearch_results", description="results"
    )
    app.config["DATA_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lifesearch", "data")

    # Session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = _prepare_directory(
        "LIFESEARCH_SESSION_DIR", "flask_session", description="session"
    )
    app.config['SESSION_PERMANENT'] = False

    ensure_cache_ready()

    # Import and register routes
    from .routes import routes_bp
    app.register_blueprint(routes_bp)

    # Prometheus metrics (optional in test environments)
    metrics_spec = importlib.util.find_spec("prometheus_flask_exporter")
    if metrics_spec is None:
        logger.info("prometheus_flask_exporter not available; Prometheus metrics disabled.")
    else:
        prometheus_module = importlib.import_module("prometheus_flask_exporter")
        prometheus_module.PrometheusMetrics(app)

    return app
