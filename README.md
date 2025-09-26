# LifeSearch Web Application

This is a Flask web application that allows users to search for information about exoplanets, configure habitability weights, and generate detailed reports with graphical visualizations.

## Project Structure

```
.
├── CONTRIBUTING.md              # Guidelines for contributing to the project
├── LICENSE                      # Project license information
├── README.md                    # Original README file (Portuguese)
├── README_en.md                 # This README file (English)
├── app/                         # Flask application source code
│   ├── __init__.py            # Initializes the Flask app, registers blueprints
│   ├── forms.py               # Defines WTForms for user input
│   ├── routes.py              # Defines all application routes and API endpoints
│   ├── static/                # Static assets like CSS, JS, and images
│   │   └── charts/            # Placeholder for generated chart images
│   │       └── none.txt       # Placeholder file
│   └── templates/             # Jinja2 HTML templates for rendering pages
│       ├── base.html          # Base template for consistent page structure
│       ├── combined_template.html # Template for combined planet reports
│       ├── configure.html     # Page to configure habitability weights
│       ├── error.html         # Template for error pages (404, 500)
│       ├── index.html         # Home page with planet search form
│       ├── report_template.html # Template for individual planet reports
│       ├── results.html       # Page displaying links to generated reports
│       └── summary_template.html # Template for the summary report
├── cache/                       # Directory for caching external API data
│   └── cache.txt                # Placeholder file for cache directory
├── docs/                        # MkDocs documentation source files
│   ├── about.md               # About page for the documentation
│   ├── api/                   # API documentation
│   │   ├── data.md            # Documentation for data handling functions
│   │   ├── lifesearch_main.md # Documentation for main logic functions
│   │   ├── reports.md         # Documentation for report generation functions
│   │   └── routes.md          # Documentation for API routes
│   ├── formulas_lifesearch.md # Documentation on LifeSearch formulas
│   ├── index.md               # Main index page for the documentation
│   ├── sources.md             # Documentation on data sources
│   └── user_guide.md          # User guide for the application
├── lifesearch/                  # Core logic and data processing for LifeSearch
│   ├── __init__.py            # Initializes the lifesearch module
│   ├── cache/                 # Internal cache for lifesearch module
│   │   └── cache.txt          # Placeholder file
│   ├── data/                  # Local data files (CSV)
│   │   ├── hwc.csv            # Habitable Worlds Catalog data
│   │   └── table-hzgallery.csv # Habitable Zone Gallery data
│   ├── data.py                # Functions for data retrieval and processing
│   ├── lifesearch_main.py     # Main calculations and logic for planet analysis
│   └── reports.py             # Functions for generating reports and plots
├── lifesearch-docker.dockerfile # Dockerfile for building the application image
├── lifesearch-docker.dockerignore # Files to ignore when building Docker image
├── lifesearch_results/          # Directory where generated reports and charts are saved
│   └── lifesearch_results_YYYYMMDD_HHMMSS/ # Example session-specific subdirectory
│       ├── charts/            # Charts generated for this session
│       └── *.html             # HTML reports for this session
├── mkdocs.yml                   # MkDocs configuration file
├── requirements-dev.txt         # Development dependencies (e.g., for MkDocs, testing)
├── requirements.txt             # Production dependencies for the Flask application
├── run.py                       # Entry point to run the Flask development server
├── tests/                       # Unit and integration tests for the application
│   ├── conftest.py            # Pytest configuration and fixtures
│   ├── test_data.py           # Tests for data handling functions
│   ├── test_forms.py          # Tests for WTForms
│   ├── test_lifesearch_main.py # Tests for main calculation logic
│   ├── test_reports.py        # Tests for report generation
│   └── test_routes.py         # Tests for Flask routes and API endpoints
└── todo.md                      # Development task list
```

## Configuration and Execution

1.  **Prerequisites**:
    *   Python 3.8 or higher
    *   `pip` to install dependencies
    *   Postman (for API tests)
    *   Docker (for containerized deployment)

2.  **Clone the repository (or extract files from ZIP)**:
    Navigate to the directory where you want to save the project.

3.  **Create and Activate a Virtual Environment (Recommended)**:
    ```bash
    python3 -m venv lifesearch_env
    source lifesearch_env/bin/activate   # On Linux/macOS
    # lifesearch_env\Scripts\activate    # On Windows
    ```

4.  **Install Dependencies**:
    In the project's root directory (where `requirements.txt` is located), run:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Install Development Dependencies (for MkDocs and other dev tools)**:
    ```bash
    pip install -r requirements-dev.txt
    ```

6.  **Run MkDocs Documentation (Optional)**:
    After installing development dependencies, you can serve the documentation locally:
    ```bash
    mkdocs serve -a 0.0.0.0:8000
    ```
    The documentation will be accessible at `http://0.0.0.0:8000/` in your browser.

7.  **Configure Flask Secret Key (Optional for Development)**:
    The application uses a default secret key for development. For production, it is highly recommended to set a `FLASK_SECRET_KEY` environment variable with a secure value.

8.  **Run the Application**:
    In the project's root directory, run:
    ```bash
    python run.py
    ```
    The application will be accessible at `http://0.0.0.0:5000/` or `http://127.0.0.1:5000/` in your browser.

9.  **Run API Tests (Optional)**:
    To run the API tests using Postman:
    *   Import the `lifesearch_api_tests.json` collection into Postman.
    *   Ensure the Flask application is running locally (step 8).
    *   Set the `base_url` environment variable in Postman to `http://127.0.0.1:5000`.
    *   Run the collection or individual requests within Postman.

## Docker Deployment

To build and run the application using Docker:

1.  **Build the Docker image**:
    ```bash
    docker build -t lifesearch-app -f lifesearch-docker.dockerfile .
    ```

2.  **Run the Docker container**:
    ```bash
    docker run -p 5000:5000 lifesearch-app
    ```
    The application will be accessible at `http://localhost:5000/`.

## Features

*   **Home Page (`/`)**: Allows the user to enter exoplanet names (separated by comma or newline) and, optionally, override specific parameters for each planet.
*   **Configuration Page (`/configure`)**: Allows the user to adjust weights for different habitability factors (ESI, SPH) and for PHI components. These weights are saved in the user's session.
*   **Results Page (`/results`)**: After the search, this page displays links to the generated reports:
    *   Individual reports for each processed planet.
    *   Summary report (if multiple planets are processed).
    *   Combined report (if multiple planets are processed).
*   **Reports**: HTML reports include detailed information about the planet, star, orbit, habitability scores (ESI, SPH, PHI), and charts (Habitable Zone, Score Comparison).
*   **Cache**: NASA Exoplanet Archive API data is cached to improve performance and reduce the number of API calls. The cache expires after 24 hours.
*   **Logging**: The application logs information about its operation, including API calls, data processing, and errors.

## How to Use

1.  Access the home page.
2.  (Optional) Go to the "Configure Weights" page to adjust habitability factor weights. Default settings will be used otherwise.
3.  On the home page, enter the names of the planets you want to analyze.
    *   Example: `Kepler-452 b, TRAPPIST-1 e`
4.  (Optional) Use the "Override Parameters" field to provide custom values.
    *   Format: `PlanetName: param1=value1; param2=value2` (one line per planet)
    *   Example: `Kepler-452 b: pl_rade=2.4; st_age=6.0`
5.  Click "Search Planets".
6.  The results page will show links to the generated reports. Click the links to view the reports.

## Notes

*   Charts are saved as PNG images in the `lifesearch_results/session_name_YYYYMMDD_HHMMSS/charts/` directory and are referenced in the HTML reports.
*   For production deployment, use a WSGI server like Gunicorn or Waitress instead of the Flask development server.

