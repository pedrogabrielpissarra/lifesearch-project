"""
Main script to start the LifeSearch Flask application.

This script configures basic logging for the application and then
creates and runs the Flask application instance. It serves as the
entry point for running the development server.

To run the application:
    python run.py
"""
from app import create_app
import logging

# Configure basic logging for the application startup
# Change level to logging.DEBUG to see more detailed logs from all modules
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(threadName)s - %(message)s'
                    # filename='app.log', filemode='w' # Uncomment to log to a file
                    )

logger = logging.getLogger(__name__)

app = create_app()  # to run guicorn correctly

if __name__ == "__main__":
    logger.info("Starting LifeSearch Flask application...")
    app = create_app()  # Create app instance

    try:
        app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=True)  # Local dev change to 5000 if needed
    except Exception as e:
        logger.critical(f"Failed to start the Flask application: {e}", exc_info=True)
