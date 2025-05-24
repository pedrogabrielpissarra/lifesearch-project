# User Guide

Welcome to the LifeSearch Web Application! This guide will help you set up, run, and use the application to explore exoplanet information, configure habitability weights, and generate detailed reports with graphical visualizations.

## 1. Project Structure

The project is organized as follows:

```
/lifesearch/
├── app/                         # Contains the Flask application code
│   ├── __init__.py              # Initializes the Flask app, configures, and registers blueprints/routes
│   ├── forms.py                 # Defines WTForms classes (e.g., PlanetSearchForm, HabitabilityWeightsForm)
│   ├── routes.py                # Defines application routes (e.g., index, configure, results, API endpoints)
│   ├── static/                  # Static files (CSS, JavaScript)
│   │   └── charts/              # Directory for generated charts (within each session's results folder)
│   └── templates/               # Jinja2 HTML templates
│       ├── index.html           # Home page with the search form
│       ├── configure.html       # Page for configuring habitability weights
│       ├── results.html         # Page to display links to generated reports
│       ├── report_template.html # Template for individual planet reports
│       ├── summary_template.html # Template for the summary report
│       ├── combined_template.html # Template for the combined report
│       └── error.html           # Template for error pages (e.g., 404, 500)
├── lifesearch/                    # Contains the core LifeSearch processing logic
│   ├── __init__.py              # Initialization file for the lifesearch module
│   ├── data.py                  # Functions for fetching API data, loading local CSVs, and merging data sources
│   ├── reports.py               # Functions for generating HTML reports and plots
│   ├── lifesearch_main.py       # Main logic for processing planet data and calculating scores
│   ├── cache/                   # Directory for caching API data (JSON files)
│   └── data/                    # Local CSV data files
│       ├── hwc.csv              # Habitable Worlds Catalog data
│       └── table-hzgallery.csv  # HZGallery Catalog data
├── lifesearch_results/            # Directory where results (reports, charts) are saved
│   └── lifesearch_results_YYYYMMDD_HHMMSS/ # Session-specific subdirectory with reports and charts
│       ├── charts/              # Charts for this session
│       └── *.html               # HTML reports
├── docs/                          # Documentation files for MkDocs
│   ├── index.md                 # Main documentation page
│   ├── user_guide.md            # This user guide
│   ├── formulas_lifesearch.md   # Mathematical formulas used in the application
│   ├── sources.md               # Data sources and references
│   ├── about.md                 # Project overview and credits
│   └── api/                     # API documentation
│       ├── lifesearch_main.md   # Documentation for lifesearch_main.py
│       ├── data.md              # Documentation for data.py
│       ├── routes.md            # Documentation for routes.py
│       ├── reports.md           # Documentation for reports.py
├── mkdocs.yml                     # MkDocs configuration file
├── run.py                         # Script to start the Flask development server
├── requirements.txt               # List of Python project dependencies
├── README.md                      # Project README file
```

## 2. Setup and Execution

Follow these steps to set up and run the LifeSearch Web Application and its documentation.

### 2.1. Prerequisites
- **Python**: Version 3.8 or higher.
- **pip**: Python package installer.
- **Git**: Optional, for cloning the repository.
- **Web Browser**: Modern browser (e.g., Chrome, Firefox) for accessing the application and documentation.

### 2.2. Clone or Download the Repository
- Clone the repository using Git:
  ```bash
  git clone <repository-url>
  cd lifesearch
  ```
- Alternatively, download and extract the project ZIP file to your desired directory.

### 2.3. Create and Activate a Virtual Environment
Using a virtual environment is recommended to isolate dependencies:
```bash
python -m venv venv
```
- On Linux/macOS:
  ```bash
  source venv/bin/activate
  ```
- On Windows:
  ```bash
  venv\Scripts\activate
  ```

### 2.4. Install Dependencies
In the project root directory (where `requirements.txt` is located), install the required packages:
```bash
pip install -r requirements.txt
```
This installs Flask, pandas, numpy, matplotlib, WTForms, MkDocs, pymdown-extensions (for MathJax), and other dependencies needed for the application and documentation.

### 2.5. Configure Flask Secret Key (Optional)
The application uses a default secret key for development. For production, set a secure, random secret key via an environment variable:
- On Linux/macOS:
  ```bash
  export FLASK_SECRET_KEY='your-secure-random-key'
  ```
- On Windows:
  ```bash
  set FLASK_SECRET_KEY=your-secure-random-key
  ```

### 2.6. Run the Application
Start the Flask development server from the project root:
```bash
python run.py
```
The application will be accessible at `http://127.0.0.1:5000/` in your web browser.

### 2.7. Run the Documentation (Optional)
To view the documentation locally using MkDocs:
```bash
mkdocs serve
```
Access the documentation at `http://127.0.0.1:8000/`. The `formulas_lifesearch.md` page will render LaTeX equations using MathJax.

### 2.8. Deploy to Production (Optional)
For production deployment:
- Use a WSGI server like Gunicorn:
  ```bash
  pip install gunicorn
  gunicorn -w 4 -b 0.0.0.0:5000 app:app
  ```
- Configure a reverse proxy (e.g., Nginx) and secure the application with HTTPS.
- For documentation, deploy to Read the Docs by linking your repository and configuring `readthedocs.yml`.

## 3. Usage Instructions

The LifeSearch Web Application allows you to search for exoplanets, configure habitability weights, and generate detailed reports with visualizations. Below is a step-by-step guide based on the current user experience.

### 3.1. Home Page (`/` or `/index`)

The home page is the starting point for exoplanet analysis.

- **Searching for Exoplanets**:
  - **Input Field**: Enter one or more exoplanet names in the "Enter Planet Names" text area.
  - **Format**: Separate multiple names with a new line or comma (e.g., `Kepler-477 b, TRAPPIST-1 e`).
  - **Autocomplete**: As you type, an autocomplete feature suggests names from the Habitable Worlds Catalog (`hwc.csv`). Click a suggestion or continue typing.
  - **Example**: Enter `Kepler-477 b` to analyze its habitability.

- **Parameter Overrides (Optional)**:
  - Use the "Parameter Overrides" field to specify custom values for planet or star parameters, useful for testing hypothetical scenarios or updating data.
  - **Syntax**: `Planet Name: param1=value1, param2=value2; Planet Name 2: param1=value1`
    - Separate each planet’s overrides with a semicolon (`;`).
    - Use the exact planet name, followed by a colon (`:`).
    - List key-value pairs separated by commas (`,`).
    - Example: `Kepler-477 b: pl_rade=2.0, st_age=3.0; TRAPPIST-1 e: pl_masse=0.8`
  - **Common Parameters**: Radius (`pl_rade` in Earth radii), mass (`pl_masse` in Earth masses), equilibrium temperature (`pl_eqt` in K), stellar age (`st_age` in Gyr), eccentricity (`pl_orbeccen`). Refer to NASA Exoplanet Archive column names.
  - **Note**: Overrides take precedence over database or catalog values.

- **Generating Reports**:
  - Click the "Generate Reports" button to process the input.
  - The application fetches data from the NASA Exoplanet Archive, applies overrides, calculates habitability scores (ESI, PHI, SPH, SEPHI), and redirects to the Results page.
  - If errors occur (e.g., invalid planet name), an error message is displayed.

- **Restoring a Previous Search**:
  - Use the "Back to Search (Restore Session)" link or navigate to `/index?restore=1` to repopulate the form with the last session’s planet names and overrides.

### 3.2. Configure Page (`/configure`)

The Configure page lets you customize weights for habitability calculations (ESI and PHI), with pre-filled values reflecting real HWC scores. Weights are saved to your session.

- **Accessing the Page**:
  - Navigate to `/configure` from the home page or a link in the results page.
  - The page displays a "Reference Values" table showing current ESI and PHI scores for selected planets, updated dynamically as weights change.

- **Global Habitability Weights**:
  - **ESI Factors**: Adjust sliders or number inputs for:
    - **Habitable Zone**: Weight for equilibrium temperature similarity.
    - **Size**: Weight for radius similarity.
    - **Density**: Weight for density similarity.
    - Range: 0.0 to 1.0, pre-filled with similarity values (e.g., ~0.75, ~0.83, ~0.36 for Kepler-477 b).
  - **PHI Factors**: Adjust weights for:
    - **Solid Surface**: Presence of a rocky surface.
    - **Stable Energy**: Stellar type and age suitability.
    - **Life Compounds**: Placeholder for life-essential compounds.
    - **Stable Orbit**: Orbital eccentricity stability.
    - Range: 0.0 to 0.25, pre-filled with scaled factor scores (e.g., ~0.085, 0.0, 0.0, ~0.096 for Kepler-477 b).
  - Global weights apply to all planets unless overridden by individual weights.

- **Individual Planet Weights**:
  - Check the "Setup individual weights" box to display weight controls for each planet in your session.
  - Adjust ESI and PHI weights for specific planets (e.g., increase `Stable Orbit` weight for Kepler-477 b to emphasize its low eccentricity).
  - Each planet has a tabbed interface for ESI and PHI factors, with sliders and number inputs.
  - A "Reset to Defaults" button per planet restores weights to their initial pre-filled values (e.g., HWC-based values like ~0.75 for ESI, ~0.085 for PHI).

- **Saving Weights**:
  - Click "Save All Individual Planet Weights" to save changes for all planets, or use the "Save [Planet Name] Weights" button for individual planets.
  - Changes are sent to the `/api/save-planet-weights` endpoint and stored in the session.
  - The "Reference Values" table updates to reflect new ESI and PHI scores.

- **Tips**:
  - Increase weights to boost ESI/PHI scores (up to 100%) or decrease them to reduce scores, simulating different habitability scenarios.
  - Use the "Reset to Defaults" button to revert to HWC-based weights if adjustments yield unexpected results.

### 3.3. Results Page (`/results`)

The Results page displays links to generated reports after submitting a search.

- **Viewing Reports**:
  - Links include:
    - **Individual Planet Reports**: Detailed reports for each planet (e.g., `report_Kepler-477_b.html`).
    - **Summary Report**: Overview comparing all searched planets (e.g., `summary_report.html`).
    - **Combined Report**: Detailed comparative analysis (e.g., `combined_report.html`).
  - Click a link to view the HTML report in your browser.

- **Report Contents**:
  - **Individual Reports** (`report_template.html`):
    - **Planet Data**: Name, classification (e.g., Superterran | Hyperthermoplanet), radius (`pl_rade`), density (`pl_dens`), equilibrium temperature (`pl_eqt`), mass (`pl_masse`), orbital period (`pl_orbper`), eccentricity (`pl_orbeccen`).
    - **Star Data**: Host star name, spectral type (`st_spectype`), temperature (`st_teff`), radius (`st_rad`), mass (`st_mass`), age (`st_age`), metallicity (`st_met`).
    - **Habitability Scores**: ESI, PHI, SPH, SEPHI, with sub-scores (e.g., Size, Density, Habitable Zone Position).
    - **Visualizations**:
      - Habitable Zone plot: Shows the planet’s orbit relative to conservative and optimistic habitable zones.
      - Score comparison bar chart: Displays scores for Size, Density, Atmosphere Potential, etc.
    - **Travel Times**: Estimated travel durations using current technology, 20% light speed, and near-light speed (e.g., 20999868.8 years, 5985.0 years, 1197.1 years for Kepler-477 b).
  - **Summary Report** (`summary_template.html`):
    - Table comparing ESI, PHI, SPH, SEPHI, and classifications across all planets.
    - Optional aggregated charts (e.g., score comparisons).
  - **Combined Report** (`combined_template.html`):
    - Detailed tables and comparative visualizations for all planets.

- **File Locations**:
  - Reports and charts are saved in a session-specific subdirectory under `lifesearch_results/` (e.g., `lifesearch_results/lifesearch_results_20250523_191600/`).
  - Access via the `/results_archive/<session_dir>/<filename>` route.

- **Navigating Back**:
  - Use the "Back to Search" link to return to the home page, optionally restoring the previous search with `?restore=1`.
  - Navigate to `/configure` to adjust weights and regenerate reports.

### 3.4. API Endpoints

The application uses API endpoints for dynamic functionality:

- **`/api/planets/autocomplete`**: Returns planet name suggestions for the search form based on `hwc.csv`.
- **`/api/planets/reference-values`**: Retrieves current ESI and PHI scores for session planets, used in the Configure page’s "Reference Values" table.
- **`/api/planets/parameters`**: Fetches detailed parameters for specified planets, supporting dynamic updates.
- **`/api/save-planet-weights`**: Saves global or individual planet weights to the session.
- **`/api/save-planets-to-session`**: Updates the session with a new list of planet names.
- **`/api/clear-session`**: Clears session data (e.g., weights, planet list).
- **`/api/debug-session`**: Returns a JSON dump of the current session for debugging.

## 4. Data Sources and Cache

- **NASA Exoplanet Archive**: Primary source for exoplanet and stellar data, queried via TAP service.
- **Local Catalogs**:
  - `hwc.csv`: Habitable Worlds Catalog, used for fallback data and autocomplete.
  - `table-hzgallery.csv`: Habitable Zone Gallery, used for fallback habitable zone parameters.
- **Caching**:
  - API responses are cached as JSON files in `lifesearch/cache/` for 24 hours (configurable via `CACHE_EXPIRATION_HOURS` in `data.py`).
  - Caching reduces API load and speeds up repeated queries.
  - To force a refresh, delete the relevant JSON file from `lifesearch/cache/`.

## 5. Troubleshooting & Tips

- **"Term not recognized" when running `python run.py`**:
  - Ensure Python is in your system’s PATH. Verify with `python --version`.
  - Confirm you’re in the project root directory.

- **Application Fails to Start**:
  - Check console output for errors (e.g., missing dependencies, file not found).
  - Verify all dependencies are installed (`pip list` vs. `requirements.txt`).
  - Ensure `hwc.csv` and `table-hzgallery.csv` are in `lifesearch/data/`.

- **No Data Found for a Planet**:
  - Check spelling and case sensitivity (e.g., `Kepler-477 b` not `kepler 477b`).
  - The planet may lack required parameters in the NASA Exoplanet Archive or local catalogs.
  - Use parameter overrides to provide missing data.

- **Incorrect Calculations**:
  - Verify weights on the Configure page (global and individual).
  - Check parameter overrides for errors.
  - Use `/api/debug-session` to inspect session data.
  - Review server logs for processing errors (`logger.error` messages).

- **Stale Data**:
  - Delete cached JSON files in `lifesearch/cache/` to force a fresh API query.

- **Performance Issues**:
  - For large planet lists, caching improves speed. Ensure cache files are generated.
  - Limit simultaneous planet analyses to reduce report generation time.

- **Documentation Issues**:
  - If formulas don’t render, verify MathJax setup in `mkdocs.yml`.
  - Ensure `pymdown-extensions` is installed (`pip show pymdown-extensions`).

---

This guide provides an overview of the LifeSearch Web Application. For detailed technical information, refer to the API documentation in `docs/api/` or explore source code comments in `app/` and `lifesearch/`.
```