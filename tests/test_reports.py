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
        "report_template.html": "<html>Planet: {{ planet_data.pl_name }} "
                                "- Scores: {{ scores }} "
                                "- SEPHI: {{ sephi_scores }}</html>",
        "summary_template.html": "<html>Summary: {{ all_planets_data|length }} planets</html>",
        "combined_template.html": "<html>Combined: {{ all_planets_data|length }} planets</html>",
    }))


# ---------------------------
# ensure_dir
# ---------------------------

def test_ensure_dir_creates_and_skips(tmp_path, caplog):
    new_dir = tmp_path / "newfolder"
    # Diretório não existe -> deve ser criado
    reports.ensure_dir(str(new_dir))
    assert new_dir.exists()
    # Diretório já existe -> não deve recriar nem logar erro
    caplog.clear()
    reports.ensure_dir(str(new_dir))
    assert "Created directory" not in caplog.text


# ---------------------------
# get_color_for_percentage
# ---------------------------

@pytest.mark.parametrize("value,expected", [
    (None, "#808080"),          # None -> cinza
    ("abc", "#808080"),         # inválido -> cinza
    (90, "#28a745"),            # >= 80 -> verde
    (70, "#90ee90"),            # >= 60 -> verde claro
    (50, "#ffc107"),            # >= 40 -> âmbar
    (30, "#fd7e14"),            # >= 20 -> laranja
    (10, "#dc3545"),            # < 20 -> vermelho
])
def test_get_color_for_percentage_cases(value, expected):
    assert reports.get_color_for_percentage(value) == expected


# ---------------------------
# format_float_field
# ---------------------------

def test_format_float_field_special_cases():
    assert reports.format_float_field(None) == "N/A"
    assert reports.format_float_field("N/A") == "N/A"
    assert reports.format_float_field("") == "N/A"
    assert reports.format_float_field("   ") == "N/A"

def test_format_float_field_valid_and_invalid():
    assert reports.format_float_field(3.14159) == "3.14"
    assert reports.format_float_field("42") == "42.00"
    assert reports.format_float_field("abc") == "abc"


# ---------------------------
# get_score_description
# ---------------------------

def test_get_score_description_cases():
    scores = {"ESI": (90, "#00FF00"), "PHI": (55, "#AAAAAA"), "SPH": (20, "#FF0000")}
    assert reports.get_score_description(scores, "ESI", "Terran")["text"] == "Likely"
    assert reports.get_score_description(scores, "PHI", "Terran")["text"] == "Possible"
    assert reports.get_score_description(scores, "SPH", "Terran")["text"] == "Unlikely"


# ---------------------------
# get_score_description_bio
# ---------------------------

def test_get_score_description_bio_cases():
    scores = {"BIO": (70, "#00FF00"), "ALT": (40, "#CCCCCC"), "LOW": (10, "#FF0000")}
    hot = reports.get_score_description_bio(scores, "BIO", pl_eqt=2000)
    assert "Too Hot" in hot["text"]
    assert reports.get_score_description_bio(scores, "BIO", pl_eqt=300)["text"] == "Likely"
    assert reports.get_score_description_bio(scores, "ALT", pl_eqt=300)["text"] == "Possible"
    assert reports.get_score_description_bio(scores, "LOW", pl_eqt=300)["text"] == "Unlikely"
    assert reports.get_score_description_bio(scores, "LOW", pl_eqt="bad")["text"] == "Unlikely"


# ---------------------------
# get_score_description_moons
# ---------------------------

def test_get_score_description_moons_cases():
    scores = {"MOONS": (50, "#AAAAAA")}
    jovian = reports.get_score_description_moons(scores, "MOONS", "Jovian", {"pl_masse": 1, "pl_orbsmax": 2})
    assert jovian["text"] == "Likely"
    highly = reports.get_score_description_moons(scores, "MOONS", "Terran", {"pl_masse": 1, "pl_orbsmax": 2})
    assert highly["text"] == "Highly Possible"
    possible = reports.get_score_description_moons(scores, "MOONS", "Terran", {"pl_masse": 1, "pl_orbsmax": 0.5})
    assert possible["text"] == "Possible"
    unlikely = reports.get_score_description_moons(scores, "MOONS", "Terran", {"pl_masse": 0.1, "pl_orbsmax": 2})
    assert unlikely["text"] == "Unlikely"
    other = reports.get_score_description_moons(scores, "MOONS", "Unknown", {"pl_masse": None})
    assert other["text"] == "Unlikely"


# ---------------------------
# to_float_or_none
# ---------------------------

def test_to_float_or_none_cases():
    assert reports.to_float_or_none(None) is None
    assert reports.to_float_or_none("abc") is None
    assert reports.to_float_or_none(3.14) == 3.14
    assert reports.to_float_or_none("42") == 42.0

# ---------------------------
# Enrich
# ---------------------------

def test_enrich_atmosphere_invalid_temp_and_mass(caplog):
    caplog.set_level("WARNING")
    data = {"pl_name": "X1", "pl_eqt": "bad", "pl_masse": "bad", "st_spectype": "G2V"}
    result = reports.enrich_atmosphere_water_magnetic_moons(data, "Terran")
    assert result["atmosphere_potential_score"] in (20, 90, 50)
    assert "Could not convert pl_eqt" in caplog.text
    assert "Could not convert mass" in caplog.text
    assert "Unable to calculate temperature" in caplog.text


def test_enrich_atmosphere_star_params_invalid(caplog):
    caplog.set_level("WARNING")
    data = {"pl_name": "X2", "st_teff": "bad", "st_rad": "bad", "pl_orbsmax": "bad"}
    result = reports.enrich_atmosphere_water_magnetic_moons(data, "Superterran")
    assert result["atmosphere_potential_score"] in (20, 90, 50)
    assert "Could not convert stellar parameters" in caplog.text
    assert "Unable to calculate temperature" in caplog.text


def test_enrich_atmosphere_star_params_invalid(caplog):
    caplog.set_level("WARNING")
    data = {"pl_name": "X2", "st_teff": "bad", "st_rad": "bad", "pl_orbsmax": "bad"}
    result = reports.enrich_atmosphere_water_magnetic_moons(data, "Superterran")
    assert result["atmosphere_potential_score"] in (20, 90, 50)
    assert "Could not convert stellar parameters" in caplog.text
    assert "Unable to calculate temperature" in caplog.text

def test_enrich_atmosphere_temperature_ranges():
    base = {"pl_name": "EarthLike", "pl_eqt": 288, "pl_masse": 1}
    r1 = reports.enrich_atmosphere_water_magnetic_moons(base, "Terran")
    assert r1["atmosphere_potential_desc"] == "Likely"

    base["pl_eqt"] = 250
    r2 = reports.enrich_atmosphere_water_magnetic_moons(base, "Terran")
    assert r2["atmosphere_potential_desc"] == "Possible"

    base["pl_eqt"] = 100
    r3 = reports.enrich_atmosphere_water_magnetic_moons(base, "Terran")
    assert r3["atmosphere_potential_desc"] == "Unlikely"

def test_enrich_atmosphere_magnetic_and_moons():
    data = {"pl_name": "X4", "pl_eqt": 288, "pl_masse": 2, "st_spectype": "K"}
    r = reports.enrich_atmosphere_water_magnetic_moons(data, "Superterran")
    assert r["magnetic_activity_desc"] == "High"
    assert r["presence_of_moons_desc"] == "Possible"

    r2 = reports.enrich_atmosphere_water_magnetic_moons({"pl_name": "X5"}, "Jovian")
    assert r2["presence_of_moons_desc"] == "Unlikely"

def test_enrich_atmosphere_star_type_M():
    data = {"pl_name": "X6", "pl_masse": None, "st_spectype": "M"}
    r = reports.enrich_atmosphere_water_magnetic_moons(data, "Unknown")
    assert r["magnetic_activity_score"] == 40

def test_enrich_atmosphere_star_params_invalid_all_none(caplog):
    caplog.set_level("WARNING")
    # Force all stellar parameters to invalid values
    data = {
        "pl_name": "X7",
        "pl_eqt": None,
        "st_teff": "bad",
        "st_rad": "bad",
        "pl_orbsmax": "bad"
    }
    result = reports.enrich_atmosphere_water_magnetic_moons(data, "Terran")
    # Should hit the except and then fall back to default temperature
    assert result["atmosphere_potential_score"] in (20, 50, 90)
    assert "Could not convert stellar parameters" in caplog.text
    assert "Unable to calculate temperature" in caplog.text

def test_enrich_atmosphere_temperature_unlikely_range():
    data = {"pl_name": "X8", "pl_eqt": 100, "pl_masse": 1}
    result = reports.enrich_atmosphere_water_magnetic_moons(data, "Terran")
    # Should fall into the else branch → Unlikely
    assert result["atmosphere_potential_score"] == 20
    assert result["atmosphere_potential_desc"] == "Unlikely"

# ---------------------------
# get_score_info
# ---------------------------

def test_get_score_info_non_dict():
    result = reports.get_score_info("notadict", "ESI")
    assert result["score"] == 0.0 and result["color"] == "#808080"

def test_get_score_info_with_dict_field():
    scores = {"ESI": {"score": 88, "color": "#123456", "text": "Good"}}
    r = reports.get_score_info(scores, "ESI")
    assert r["score"] == 88 and r["color"] == "#123456" and r["text"] == "Good"

def test_get_score_info_invalid_tuple(caplog):
    caplog.set_level("DEBUG")
    scores = {"ESI": ("bad",)}
    r = reports.get_score_info(scores, "ESI")
    assert r["score"] == 0.0
    assert "not a valid number" in caplog.text or "Invalid or missing" in caplog.text

def test_get_score_info_valid_tuple_with_color_and_text():
    scores = {"ESI": (75.0, "#FF0000", "Custom")}
    r = reports.get_score_info(scores, "ESI")
    assert r["score"] == 75.0
    assert r["color"] == "#FF0000"
    assert r["text"] == "Custom"



# ---------------------------
# plot_habitable_zone
# ---------------------------

def test_plot_habitable_zone_valid(tmp_output_dir):
    planet_data = {"pl_name": "Kepler-22 b", "pl_orbsmax": 1.0}
    star_data = {"st_lum": 1.0}
    result = reports.plot_habitable_zone(planet_data, star_data, None, tmp_output_dir, "kepler22b")
    assert result.endswith("_hz.png")

def test_plot_habitable_zone_invalid_data(tmp_output_dir):
    planet_data = {"pl_name": "Kepler-22 b"}  # falta pl_orbsmax
    star_data = {"st_lum": 1.0}
    result = reports.plot_habitable_zone(planet_data, star_data, None, tmp_output_dir, "kepler22b")
    assert result.endswith("_hz.png")

def test_plot_habitable_zone_with_stellar_luminosity(tmp_output_dir):
    planet_data = {"pl_name": "Kepler-22 b", "pl_orbsmax": "1.5"}
    star_data = {"st_lum": 0.0}
    result = reports.plot_habitable_zone(planet_data, star_data, None, tmp_output_dir, "kepler22b")
    assert result.endswith("_hz.png")

def test_plot_habitable_zone_invalid_st_lum_and_orbsmax(tmp_output_dir, caplog):
    planet_data = {"pl_name": "Kepler-22 b", "pl_orbsmax": "bad"}
    star_data = {"st_lum": "invalid"}
    caplog.set_level("WARNING")
    result = reports.plot_habitable_zone(planet_data, star_data, None, tmp_output_dir, "kepler22b")
    assert result.endswith("_hz.png")
    assert "Orbital semi-major axis" in caplog.text

def test_plot_habitable_zone_invalid_orbsmax_warning(tmp_output_dir, caplog):
    caplog.set_level("WARNING")
    planet_data = {"pl_name": "Kepler-22 b", "pl_orbsmax": "abc"}  # inválido
    star_data = {"st_lum": 1.0}
    result = reports.plot_habitable_zone(planet_data, star_data, None, tmp_output_dir, "kepler22b")
    assert result.endswith("_hz.png")
    assert "Orbital semi-major axis" in caplog.text

def test_plot_habitable_zone_no_values_sets_default_xlim(tmp_output_dir):
    planet_data = {"pl_name": "Kepler-22 b"}
    star_data = {}
    result = reports.plot_habitable_zone(planet_data, star_data, (None, None, None, None, None), tmp_output_dir, "kepler22b")
    assert result.endswith("_hz.png")

def test_plot_habitable_zone_invalid_orbsmax_triggers_warning(tmp_output_dir, caplog):
    caplog.set_level("WARNING")
    planet_data = {"pl_name": "Kepler-22 b", "pl_orbsmax": "abc"}  # inválido
    star_data = {"st_lum": 1.0}
    result = reports.plot_habitable_zone(planet_data, star_data, None, tmp_output_dir, "kepler22b")
    assert result.endswith("_hz.png")
    assert "Orbital semi-major axis" in caplog.text



# ---------------------------
# plot_scores_comparison
# ---------------------------

def test_plot_scores_comparison_valid(tmp_output_dir):
    scores = {"ESI": (85.0, "#00FF00")}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "kepler22b")
    assert result.endswith("_scores.png")

def test_plot_scores_comparison_empty(tmp_output_dir):
    scores = {}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "kepler22b")
    assert result is None

def test_plot_scores_comparison_invalid_input(tmp_output_dir):
    result = reports.plot_scores_comparison(None, tmp_output_dir, "kepler22b")
    assert result is None

def test_plot_scores_comparison_with_non_numeric_value(tmp_output_dir, caplog):
    caplog.set_level("DEBUG")
    scores = {"ESI": ("bad", "#00FF00")}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "kepler22b")
    assert result is None
    assert "Could not convert score value" in caplog.text

def test_plot_scores_comparison_multiple_scores(tmp_output_dir):
    scores = {"ESI": (85.0, "#00FF00"), "PHI": (60.0, "#FF0000")}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "kepler22b")
    assert result.endswith("_scores.png")

def test_plot_scores_comparison_bar_labels(tmp_output_dir, caplog):
    scores = {"ESI": (85.0, "#00FF00")}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "kepler22b")
    assert result.endswith("_scores.png")
    # garante que passou pelo loop de barras
    assert os.path.exists(os.path.join(tmp_output_dir, result))

def test_plot_scores_comparison_loop_labels(tmp_output_dir, caplog):
    scores = {"ESI": (85.0, "#00FF00")}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "kepler22b")
    assert result.endswith("_scores.png")
    # Deve ter chamado ax.text() → registrado no caplog? (se logs internos forem usados)
    # ou, pelo menos, o arquivo foi gerado
    assert os.path.exists(os.path.join(tmp_output_dir, result))

def test_plot_scores_comparison_non_numeric_value(tmp_output_dir, caplog):
    caplog.set_level("WARNING")
    scores = {"ESI": ("not-a-float", "#00FF00")}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "weirdplanet")
    # Deve retornar None pois score inválido não gera gráfico
    assert result is None
    # A mensagem correta que o código gera
    assert "No valid numeric scores to plot" in caplog.text

def test_plot_scores_comparison_labels_called(tmp_output_dir, monkeypatch):
    called = {}

    def fake_text(*args, **kwargs):
        called["text"] = True
        return None

    monkeypatch.setattr(reports.plt.subplots()[1], "text", fake_text)

    scores = {"ESI": (50.0, "#00FF00")}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "labelplanet")
    assert result.endswith("_scores.png")
    assert "text" in called  # confirma que a label foi escrita

def test_plot_habitable_zone_orbsmax_invalid(tmp_output_dir, caplog):
    caplog.set_level("WARNING")
    planet_data = {"pl_name": "Kepler-22 b", "pl_orbsmax": "not-a-number"}
    star_data = {"st_lum": 1.0}
    result = reports.plot_habitable_zone(planet_data, star_data, None, tmp_output_dir, "kepler22b")
    assert result.endswith("_hz.png")
    assert "Orbital semi-major axis" in caplog.text

def test_plot_scores_comparison_with_label_loop(tmp_output_dir):
    scores = {"ESI": (42.0, "#123456")}
    result = reports.plot_scores_comparison(scores, tmp_output_dir, "kepler22b")
    assert result.endswith("_scores.png")
    # garante que o arquivo foi criado
    assert os.path.exists(os.path.join(tmp_output_dir, result))

# ---------------------------
# _prepare_data_for_aggregated_reports
# ---------------------------

def test_prepare_data_skips_empty_planet_data(tmp_output_dir, caplog):
    caplog.set_level("WARNING")
    result = reports._prepare_data_for_aggregated_reports([{}], tmp_output_dir)
    assert result == []
    assert "Skipping planet with no raw data dictionary" in caplog.text


def test_prepare_data_classification_final_display(tmp_output_dir):
    data = {
        "planet_data_dict": {
            "pl_name": "X1",
            "classification": "Terran",
            "classification_final_display": "Warm Terran"
        }
    }
    result = reports._prepare_data_for_aggregated_reports([data], tmp_output_dir)
    assert result[0]["classification"] == "Warm Terran"


def test_prepare_data_stellar_activity_scores(tmp_output_dir, caplog):
    # invalid age
    d1 = {"planet_data_dict": {"pl_name": "P1", "st_age": "bad"}}
    r1 = reports._prepare_data_for_aggregated_reports([d1], tmp_output_dir)
    assert r1[0]["scores"]["Stellar_Activity"]["score"] == 30.0
    assert "Could not convert st_age" in caplog.text

    # old star
    d2 = {"planet_data_dict": {"pl_name": "P2", "st_age": 6}}
    r2 = reports._prepare_data_for_aggregated_reports([d2], tmp_output_dir)
    assert r2[0]["scores"]["Stellar_Activity"]["score"] == 90.0

    # middle-aged star
    d3 = {"planet_data_dict": {"pl_name": "P3", "st_age": 3}}
    r3 = reports._prepare_data_for_aggregated_reports([d3], tmp_output_dir)
    assert r3[0]["scores"]["Stellar_Activity"]["score"] == 60.0


def test_prepare_data_sephi_invalid(tmp_output_dir, caplog):
    caplog.set_level("WARNING")
    data = {
        "planet_data_dict": {"pl_name": "X2"},
        "sephi_scores_for_report": {"SEPHI": ["bad"]}
    }
    result = reports._prepare_data_for_aggregated_reports([data], tmp_output_dir)
    assert result[0]["sephi_scores"]["SEPHI"]["score"] == 0.0
    assert "Error processing SEPHI" in caplog.text


def test_prepare_data_no_components_for_habitability(tmp_output_dir):
    data = {"planet_data_dict": {"pl_name": "X3"}, "scores_for_report": {}}
    result = reports._prepare_data_for_aggregated_reports([data], tmp_output_dir)
    score = result[0]["scores"]["Habitability"]["score"]
    # Should be effectively zero (very close to 0)
    assert score < 1e-5

def test_prepare_data_invalid_sy_dist(tmp_output_dir, caplog):
    caplog.set_level("WARNING")
    data = {"planet_data_dict": {"pl_name": "X4", "sy_dist": "bad"}}
    result = reports._prepare_data_for_aggregated_reports([data], tmp_output_dir)
    assert result[0]["travel_curiosities"]["distance_ly"] == "N/A"
    assert "Could not calculate travel times" in caplog.text


def test_prepare_data_surface_gravity_errors(tmp_output_dir, caplog):
    caplog.set_level("WARNING")
    d1 = {"planet_data_dict": {"pl_name": "X5", "pl_masse": "bad", "pl_rade": "bad"}}
    r1 = reports._prepare_data_for_aggregated_reports([d1], tmp_output_dir)
    assert r1[0]["surface_gravity_g"] == "N/A"
    assert "Could not convert mass" in caplog.text

    d2 = {"planet_data_dict": {"pl_name": "X6", "pl_masse": 1, "pl_rade": 0}}
    r2 = reports._prepare_data_for_aggregated_reports([d2], tmp_output_dir)
    assert "N/A" in r2[0]["surface_gravity_g"] or "0" in r2[0]["surface_gravity_g"]
    assert "radius is zero or invalid" in caplog.text


def test_prepare_data_empty_processed_list(tmp_output_dir, caplog):
    caplog.set_level("WARNING")
    result = reports._prepare_data_for_aggregated_reports([], tmp_output_dir)
    assert result == []
    assert "No data processed for summary/combined report" in caplog.text

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

def test_generate_planet_report_with_scores(tmp_output_dir, template_env):
    planet = {"pl_name": "Kepler-22 b"}
    scores = {"ESI": (85.0, "#00FF00")}
    sephi_scores = {}
    path = reports.generate_planet_report_html(
        planet, scores, sephi_scores, {}, template_env, tmp_output_dir, "kepler22b"
    )
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "ESI" in content

def test_generate_planet_report_with_sephi_scores(tmp_output_dir, template_env):
    planet = {"pl_name": "Kepler-22 b"}
    scores = {}
    sephi_scores = {"SEPHI": (70.0, "#FF0000")}
    path = reports.generate_planet_report_html(
        planet, scores, sephi_scores, {}, template_env, tmp_output_dir, "kepler22b"
    )
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "SEPHI" in content

def test_generate_planet_report_exception(tmp_output_dir):
    planet = {"pl_name": "Kepler-22 b"}
    scores = {}
    sephi_scores = {}
    bad_env = Environment(loader=DictLoader({}))  # sem o template
    result = reports.generate_planet_report_html(
        planet, scores, sephi_scores, {}, bad_env, tmp_output_dir, "kepler22b"
    )
    assert result is None

def test_generate_planet_report_with_transformed_scores(tmp_output_dir, template_env):
    planet = {"pl_name": "Kepler-22 b"}
    scores = {"ESI": (85.0, "#00FF00")}  # válido
    path = reports.generate_planet_report_html(
        planet, scores, {}, {}, template_env, tmp_output_dir, "kepler22b"
    )
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # deve aparecer o valor convertido em lista
    assert "85.0" in content or "ESI" in content

def test_generate_planet_report_with_transformed_sephi_scores(tmp_output_dir, template_env):
    planet = {"pl_name": "Kepler-22 b"}
    sephi_scores = {"SEPHI": (70.0, "#FF0000")}  # válido
    path = reports.generate_planet_report_html(
        planet, {}, sephi_scores, {}, template_env, tmp_output_dir, "kepler22b"
    )
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # deve aparecer SEPHI com valor
    assert "70.0" in content or "SEPHI" in content

def test_generate_planet_report_html_with_scores(tmp_output_dir, template_env):
    planet = {"pl_name": "Kepler-22 b"}
    scores = {"ESI": (85.0, "#00FF00")}  # válido
    path = reports.generate_planet_report_html(
        planet, scores, {}, {}, template_env, tmp_output_dir, "kepler22b"
    )
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "85.0" in content or "ESI" in content

def test_generate_planet_report_html_with_sephi_scores(tmp_output_dir, template_env):
    planet = {"pl_name": "Kepler-22 b"}
    sephi_scores = {"SEPHI": (70.0, "#FF0000")}  # válido
    path = reports.generate_planet_report_html(
        planet, {}, sephi_scores, {}, template_env, tmp_output_dir, "kepler22b"
    )
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "70.0" in content or "SEPHI" in content


# ---------------------------
# generate_summary_report_html
# ---------------------------

def test_generate_summary_report_html(tmp_output_dir, template_env):
    planets = [{"planet_data_dict": {"pl_name": "Kepler-22 b"}}]
    path = reports.generate_summary_report_html(planets, template_env, tmp_output_dir)
    assert path.endswith("summary_report.html")
    assert os.path.exists(path)

def test_generate_summary_report_html_success(tmp_output_dir, template_env):
    data = [{"planet_data_dict": {"pl_name": "PlanetX"}}]
    result = reports.generate_summary_report_html(data, template_env, tmp_output_dir)
    assert result.endswith("summary_report.html")
    with open(result, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Summary:" in content


def test_generate_summary_report_html_no_data(tmp_output_dir, template_env, caplog):
    caplog.set_level("WARNING")
    result = reports.generate_summary_report_html([], template_env, tmp_output_dir)
    assert result.endswith("summary_report.html")
    assert "No processed data available for summary report" in caplog.text


def test_generate_summary_report_html_template_error(tmp_output_dir):
    # Pass a broken template_env that raises
    from jinja2 import Environment, DictLoader
    env = Environment(loader=DictLoader({"summary_template.html": "{{ invalid_var | nonexistent_filter }}"}))
    result = reports.generate_summary_report_html([{"planet_data_dict": {"pl_name": "X"}}], env, tmp_output_dir)
    # Should fall back to error HTML
    assert result.endswith("summary_report.html")
    with open(result, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Summary Report Error" in content

# ---------------------------
# generate_combined_report_html
# ---------------------------

def test_generate_combined_report_html(tmp_output_dir, template_env):
    planets = [{"planet_data_dict": {"pl_name": "Kepler-22 b"}}]
    path = reports.generate_combined_report_html(planets, template_env, tmp_output_dir)
    assert path.endswith("combined_report.html")
    assert os.path.exists(path)

def test_generate_combined_report_html_success(tmp_output_dir, template_env):
    data = [{"planet_data_dict": {"pl_name": "PlanetY"}}]
    result = reports.generate_combined_report_html(data, template_env, tmp_output_dir)
    assert result.endswith("combined_report.html")
    with open(result, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Combined:" in content

def test_generate_combined_report_html_no_data(tmp_output_dir, template_env, caplog):
    caplog.set_level("WARNING")
    result = reports.generate_combined_report_html([], template_env, tmp_output_dir)
    assert result.endswith("combined_report.html")
    assert "No processed data available for combined report" in caplog.text

def test_generate_combined_report_html_template_error(tmp_output_dir):
    from jinja2 import Environment, DictLoader
    env = Environment(loader=DictLoader({"combined_template.html": "{{ invalid_var | nonexistent_filter }}"}))
    result = reports.generate_combined_report_html([{"planet_data_dict": {"pl_name": "Y"}}], env, tmp_output_dir)
    assert result.endswith("combined_report.html")
    with open(result, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Combined Report Error" in content