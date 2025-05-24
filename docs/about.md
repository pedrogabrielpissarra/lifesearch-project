# About

# About LifeSearch

LifeSearch is a web-based application designed for the comprehensive analysis of exoplanet habitability. It empowers users to explore and evaluate potential life-supporting conditions on planets orbiting stars beyond our solar system.

## Purpose

The primary goal of LifeSearch is to provide a user-friendly yet powerful platform for:

*   Gathering up-to-date information on exoplanets by interfacing with public astronomical databases and local catalogs.
*   Calculating a diverse suite of habitability metrics and indices, including the Earth Similarity Index (ESI), Standard Primary Habitability (SPH), Planetary Habitability Index (PHI), and the Standard Exoplanet Habitability Index (SEPHI).
*   Offering detailed assessments of various planetary characteristics such as size, mass, density, atmospheric potential, liquid water potential, and orbital stability.
*   Generating insightful reports and visualizations to aid in the systematic assessment of exoplanetary environments and their potential to harbor life.

## Key Features

LifeSearch incorporates a range of features to facilitate in-depth exoplanet analysis:

*   **Multi-Source Data Aggregation:** Fetches data from the NASA Exoplanet Archive API and integrates it with information from local catalogs like the Habitable Worlds Catalog (HWC) and the Habitable Zone Gallery (HZGallery).
*   **Advanced Habitability Metrics:** Computes several recognized habitability indices and detailed scores for factors crucial for life as we know it.
*   **Planet Classification:** Provides a classification for exoplanets based on their physical properties (mass, radius) and estimated equilibrium temperatures.
*   **Customizable Analysis:** Allows users to configure weights for different habitability factors (used in ESI and PHI calculations), enabling tailored analyses based on specific research criteria or hypotheses.
*   **Comprehensive Reporting:** Generates individual planet reports, as well as summary and combined comparison reports for multiple planets. These HTML reports include:
    *   Detailed planetary and stellar parameters.
    *   Calculated habitability scores and classifications.
    *   Visualizations, such as habitable zone diagrams and score comparison bar charts.
*   **User-Friendly Web Interface:** Built with Flask, the application offers an intuitive interface for inputting target planet names, managing analysis configurations, and viewing results.
*   **Efficient Data Handling:** Implements caching for API data to improve performance and reduce redundant external requests. It also normalizes planet names for consistent data merging and retrieval.
*   **Exploratory Tools:** Includes features like travel time estimations to exoplanets, adding a curious perspective to the vast distances involved.

## Technology Stack

LifeSearch is primarily built using Python and leverages several powerful libraries:

*   **Flask:** Powers the web application framework.
*   **Pandas:** Used extensively for data manipulation, aggregation, and analysis.
*   **NumPy:** Supports numerical operations.
*   **Matplotlib:** Generates plots and charts for visualization within reports.
*   **Jinja2:** Used as the templating engine for rendering HTML pages.
*   **Requests:** Handles HTTP requests to external APIs.

## Intended Audience

This tool is designed for a wide range of users, including:

*   Astronomy enthusiasts eager to learn more about exoplanets.
*   Students undertaking projects in astrophysics or astrobiology.
*   Researchers looking for a flexible tool to perform preliminary habitability assessments.
*   Anyone intrigued by the ongoing search for life beyond Earth.

---

LifeSearch aims to be an evolving project. Future enhancements may include additional data sources, more sophisticated habitability models, and enhanced interactive visualizations.