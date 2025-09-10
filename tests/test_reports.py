import os
import tempfile
import pytest
from jinja2 import Environment, DictLoader

from lifesearch import reports


@pytest.fixture
def tmp_output_dir():
    """Cria diretório temporário para salvar os relatórios/figuras."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def template_env():
    """Mock simples de templates Jinja2 para evitar dependência de arquivos reais."""
    return Environment(loader=DictLoader({
        "report_template.html": "<html>Planet: {{ planet_data.pl_name }} - Scores: {{ scores }}</html>",
        "summary_template.html": "<html>Summary: {{ all_planets_data|length }} planets</html>",
        "combined_template.html": "<html>Combined: {{ all_planets_data|length }} planets</html>",
    }))


# ---------------------------
# plot_habitable_zone
# ---------------------------

def test_plot_habitable_zone_valid(tmp_output_dir):
    planet_data = {"pl_name": "Kepler-22 b", "pl_orbsmax": 1.0}
    star_data = {"st_lum": 1.0}
    result = reports.plot_habitable_zone(planet_data, star_data, None, tmp_output_dir, "kepler22b")
    assert result.endswith("_hz.png")
    assert os.path.exists(os.path.join(tmp_output_dir, result))


def test_plot_habitable_zone_invalid_data(tmp_output_dir):
    planet_data = {"pl_name": "Kepler-22 b"}  # falta pl_orbsmax
    star_data = {"st_lum": 1.0}
    result = reports.plot_habitable_zone(planet_data, star_data, None, tmp_output_dir, "kepler22b")
    # mesmo sem pl_orbsmax, a função gera arquivo com warning
    assert result.endswith("_hz.png")
    assert os.path.exists(os.path.join(tmp_output_dir, result))


# ---------------------------
# plot_scores_comparison
# ---------------------------

def test_plot_scores_comparison_valid(tmp_output_dir):
    scores = {"ESI": (85.0, "#00FF00")}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "kepler22b")
    assert result.endswith("_scores.png")
    assert os.path.exists(os.path.join(tmp_output_dir, result))


def test_plot_scores_comparison_empty(tmp_output_dir):
    scores = {}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "kepler22b")
    assert result is None


# ---------------------------
# generate_planet_report_html
# ---------------------------

def test_generate_planet_report_html(tmp_output_dir, template_env):
    planet = {"pl_name": "Kepler-22 b", "hostname": "Kepler", "st_teff": 5778, "st_rad": 1.0, "st_mass": 1.0}
    scores = {"ESI": (86.7, "#00FF00")}
    sephi_scores = {"SEPHI": (70.0, "#FF0000")}
    path = reports.generate_planet_report_html(
        planet, scores, sephi_scores, {}, template_env, tmp_output_dir, "kepler22b"
    )
    assert path.endswith("kepler22b_report.html")
    assert os.path.exists(path)


# ---------------------------
# generate_summary_report_html
# ---------------------------

def test_generate_summary_report_html(tmp_output_dir, template_env):
    planets = [{"planet_data_dict": {"pl_name": "Kepler-22 b"}}]
    path = reports.generate_summary_report_html(planets, template_env, tmp_output_dir)
    assert path.endswith("summary_report.html")
    assert os.path.exists(path)


# ---------------------------
# generate_combined_report_html
# ---------------------------

def test_generate_combined_report_html(tmp_output_dir, template_env):
    planets = [{"planet_data_dict": {"pl_name": "Kepler-22 b"}}]
    path = reports.generate_combined_report_html(planets, template_env, tmp_output_dir)
    assert path.endswith("combined_report.html")
    assert os.path.exists(path)
