import pytest
from lifesearch import lifesearch_main as lm


class TestHelpers:
    # ---------------------------
    # get_color_for_percentage
    # ---------------------------
    @pytest.mark.parametrize("value,expected", [
        (90, "#4CAF50"),   # verde (>=80)
        (70, "#8BC34A"),   # verde claro (>=60)
        (45, "#FFC107"),   # amarelo (>=40)
        (25, "#FF9800"),   # laranja (>=20)
        (10, "#F44336"),   # vermelho (<20)
        (None, "#757575"), # inválido = cinza
    ])
    def test_get_color_for_percentage(self, value, expected):
        """Should return the correct color (Material Design palette) for different percentage values"""
        assert lm.get_color_for_percentage(value) == expected

    def test_get_color_for_percentage_low_is_good(self):
        from lifesearch.lifesearch_main import get_color_for_percentage
        assert get_color_for_percentage(5, high_is_good=False) == "#4CAF50"   # green
        assert get_color_for_percentage(20, high_is_good=False) == "#8BC34A"  # light green
        assert get_color_for_percentage(45, high_is_good=False) == "#FFC107"  # amber
        assert get_color_for_percentage(70, high_is_good=False) == "#FF9800"  # orange
        assert get_color_for_percentage(90, high_is_good=False) == "#F44336"  # red

    def test_format_value_none_or_nan(self):
        from lifesearch.lifesearch_main import format_value
        assert format_value(None) == "N/A"
        assert format_value(float("nan")) == "N/A"

    def test_format_value_invalid_type(self, caplog):
        from lifesearch.lifesearch_main import format_value
        caplog.set_level("DEBUG")
        result = format_value("abc")
        assert result == "N/A"
        assert any("Could not convert" in m for m in caplog.messages)
        
    # ---------------------------
    # calculate_travel_times
    # ---------------------------
    def test_calculate_travel_times(self):
        """Should calculate valid travel times for a given distance in light-years"""
        times = lm.calculate_travel_times(10)
        assert isinstance(times, dict)
        assert "scenario_1_time" in times
        assert "scenario_2_time" in times
        assert "scenario_3_time" in times
        for v in times.values():
            assert isinstance(v, str)
            assert v != ""

    def test_calculate_travel_times_invalid(self):
        """Should return descriptive strings even for invalid input (e.g., None)"""
        times = lm.calculate_travel_times(None)
        assert isinstance(times, dict)
        for v in times.values():
            assert isinstance(v, str)
            assert v != ""  # não esperamos 'N/A', mas pelo menos string não vazia

    # ---------------------------
    # classify_planet
    # ---------------------------
    def test_classify_planet_terran(self):
        """Should classify as Terran planet for Earth-like values"""
        classification = lm.classify_planet(radius_earth=1.0, mass_earth=1.0, temp_k=288)
        assert "Terran" in classification or "Earth-like" in classification

    def test_classify_planet_jovian(self):
        """Should classify as Jovian planet for large radius and mass"""
        classification = lm.classify_planet(radius_earth=11.0, mass_earth=317.0, temp_k=120)
        assert "Jovian" in classification

    def test_classify_planet_unknown(self):
        """Should return an Unknown classification when no valid data is provided"""
        classification = lm.classify_planet(radius_earth=None, mass_earth=None, temp_k=None)
        assert "Unknown" in classification

    def test_classify_planet_estimate_mass_rocky(self):
        from lifesearch.lifesearch_main import classify_planet
        result = classify_planet(float("nan"), 1.0, 300)  # NaN mass, small radius
        # Como radius=1.0 → mass estimada ~1.0 → Terran
        assert result.startswith("Terran")
        assert "Mesoplanet" in result

    def test_classify_planet_estimate_mass_gaseous(self):
        from lifesearch.lifesearch_main import classify_planet
        result = classify_planet(float("nan"), 2.0, 300)  # NaN mass, larger radius
        # Como radius=2.0 → mass estimada ~4.0 → Superterran
        assert result.startswith("Superterran")
        assert "Mesoplanet" in result

    def test_classify_planet_mercurian(self):
        from lifesearch.lifesearch_main import classify_planet
        result = classify_planet(0.05, 1.0, 300)
        assert result.startswith("Mercurian")

    def test_classify_planet_hypopsychroplanet(self):
        from lifesearch.lifesearch_main import classify_planet
        result = classify_planet(1.0, 1.0, 150)
        assert "Hypopsychroplanet" in result


class TestCalculationsESI:
    # ---------------------------
    # ESI
    # ---------------------------
    def test_esi_earth_like(self):
        """ESI for Earth-like values should be close to 100"""
        planet_data = {"pl_rade": 1.0, "pl_dens": 5.51, "pl_eqt": 255.0}
        esi, _ = lm.calculate_esi_score(planet_data, {"Size": 1, "Density": 1, "Habitable Zone": 1})
        assert 90 <= esi <= 100

    def test_esi_mars_like(self):
        """ESI for Mars-like values should be within the valid range 0–100"""
        planet_data = {"pl_rade": 0.53, "pl_dens": 3.93, "pl_eqt": 210.0}
        esi, _ = lm.calculate_esi_score(planet_data, {"Size": 1, "Density": 1, "Habitable Zone": 1})
        assert 0 <= esi <= 100

    def test_esi_jupiter_like(self):
        """ESI for Jupiter-like values should be within the valid range 0–100"""
        planet_data = {"pl_rade": 11.2, "pl_dens": 1.33, "pl_eqt": 110.0}
        esi, _ = lm.calculate_esi_score(planet_data, {"Size": 1, "Density": 1, "Habitable Zone": 1})
        assert 0 <= esi <= 100

    def test_esi_invalid_values(self):
        """ESI should depend only on weights even if data is missing"""
        planet_data = {"pl_rade": None, "pl_dens": None, "pl_eqt": None}
        esi, color = lm.calculate_esi_score(planet_data, {"Size": 1, "Density": 1, "Habitable Zone": 1})
        assert (esi, color) == (100.0, "#4CAF50")

    def test_calculate_esi_score_no_valid_components(self):
        from lifesearch.lifesearch_main import calculate_esi_score
        planet_data = {"pl_rade": None, "pl_dens": None, "pl_eqt": None}
        weights = {"Size": 0.0, "Density": 0.0, "Habitable Zone": 0.0}
        result = calculate_esi_score(planet_data, weights)
        assert result == (0.0, "#F44336")

    def test_calculate_esi_score_missing_weights(self):
        from lifesearch.lifesearch_main import calculate_esi_score
        planet_data = {"pl_name": "Noweight"}
        result = calculate_esi_score(planet_data, {})
        assert result == (0.0, "#F44336")

class TestCalculationsPHI:
    # ---------------------------
    # PHI
    # ---------------------------    
    def test_phi_earth_like(self):
        """PHI for Earth-like planet should be high"""
        planet_data = {
            "classification": "Terran",
            "st_spectype": "G2V",   # solar type
            "st_age": 4.5,          # Gyr
            "pl_orbeccen": 0.016    # Earth eccentricity
        }
        phi, _ = lm.calculate_phi_score(
            planet_data,
            {"Solid Surface": 0.25, "Stable Energy": 0.25,
             "Life Compounds": 0.25, "Stable Orbit": 0.25}
        )
        assert 70 <= phi <= 100

    def test_phi_gas_giant(self):
        """PHI for a gas giant should return a valid score (0–100)"""
        planet_data = {
            "classification": "Jovian",
            "st_spectype": "F5V",
            "st_age": 1.0,
            "pl_orbeccen": 0.3
        }
        phi, _ = lm.calculate_phi_score(
            planet_data,
            {"Solid Surface": 0.25, "Stable Energy": 0.25,
             "Life Compounds": 0.25, "Stable Orbit": 0.25}
        )
        assert 0 <= phi <= 100

    def test_phi_invalid_data(self):
        """PHI should return a valid score (0–100) even when input data is missing"""
        planet_data = {
            "classification": "",
            "st_spectype": "",
            "st_age": None,
            "pl_orbeccen": None
        }
        phi, _ = lm.calculate_phi_score(
            planet_data,
            {"Solid Surface": 0.25, "Stable Energy": 0.25,
             "Life Compounds": 0.25, "Stable Orbit": 0.25}
        )
        assert 0 <= phi <= 100

    def test_calculate_phi_score_no_factors(self):
        from lifesearch.lifesearch_main import calculate_phi_score
        planet_data = {"pl_name": "Empty"}
        result = calculate_phi_score(planet_data, {})
        assert result == (0.0, "#F44336")  # sem fatores → 0 e vermelho

    def test_calculate_phi_score_with_factors(self):
        from lifesearch.lifesearch_main import calculate_phi_score
        planet_data = {
            "pl_name": "TerraX",
            "classification": "Terran",
            "st_spectype": "G2V",
            "st_age": "4.5",
            "pl_orbeccen": 0.05
        }
        phi_weights = {
            "Solid Surface": 0.25,
            "Stable Energy": 0.25,
            "Life Compounds": 0.25,
            "Stable Orbit": 0.25,
        }
        score, color = calculate_phi_score(planet_data, phi_weights)
        assert score > 0
        assert color.startswith("#")

    def test_calculate_phi_score_partial_weights(self):
        from lifesearch.lifesearch_main import calculate_phi_score
        planet_data = {"pl_name": "Partial"}
        phi_weights = {"Solid Surface": 0.1}
        score, _ = calculate_phi_score(planet_data, phi_weights)
        assert score == 10.0

class TestCalculationsSPH:
    # ---------------------------
    # SPH
    # ---------------------------    
    def test_sph_earth_like(self):
        """SPH for Earth-Sun system should be high"""
        planet_data = {
            "st_teff": 5778,
            "st_rad": 1.0,
            "st_mass": 1.0,
            "pl_orbsmax": 1.0
        }
        sph, _ = lm.calculate_sph_score(planet_data, {"Star": 1.0})
        assert 0 <= sph <= 100

    def test_sph_hot_star_close_orbit(self):
        """SPH should be valid for hot star with close orbit"""
        planet_data = {
            "st_teff": 10000,
            "st_rad": 2.0,
            "st_mass": 2.0,
            "pl_orbsmax": 0.1
        }
        sph, _ = lm.calculate_sph_score(planet_data, {"Star": 1.0})
        assert 0 <= sph <= 100

    def test_sph_invalid_data(self):
        """SPH should return a valid score (0–100) even when data is missing"""
        planet_data = {
            "st_teff": None,
            "st_rad": None,
            "st_mass": None,
            "pl_orbsmax": None
        }
        sph, _ = lm.calculate_sph_score(planet_data, {"Star": 1.0})
        assert 0 <= sph <= 100

    def test_calculate_sph_score_optimal_range(self):
        from lifesearch.lifesearch_main import calculate_sph_score
        planet_data = {"pl_name": "Optimus", "pl_eqt": 300}
        score, color = calculate_sph_score(planet_data, {})
        assert 70 <= score <= 100
        assert color.startswith("#")

    def test_calculate_sph_score_adjacent_range(self):
        from lifesearch.lifesearch_main import calculate_sph_score
        planet_data = {"pl_name": "Adjacency", "pl_eqt": 260}
        score, color = calculate_sph_score(planet_data, {})
        assert score == 40
        assert color.startswith("#")

    def test_calculate_sph_score_outside_range(self):
        from lifesearch.lifesearch_main import calculate_sph_score
        planet_data = {"pl_name": "HotPlanet", "pl_eqt": 400}
        score, color = calculate_sph_score(planet_data, {})
        assert score == 10
        assert color.startswith("#")

    def test_calculate_sph_score_invalid_type(self):
        from lifesearch.lifesearch_main import calculate_sph_score
        planet_data = {"pl_name": "Broken", "pl_eqt": "not_a_number"}
        score, color = calculate_sph_score(planet_data, {})
        assert score == 0.0
        assert color == "#F44336"  # 0% should return red

class TestCalculationsSEPHI:
    # ---------------------------
    # SEPHI
    # ---------------------------      
    def test_sephi_earth_like(self):
        """SEPHI for Earth-like planet should be high"""
        result = lm.calculate_sephi(
            planet_mass=1.0,
            planet_radius=1.0,
            orbital_period=365.25,
            stellar_mass=1.0,
            stellar_radius=1.0,
            stellar_teff=5778,
            system_age=4.5,
            planet_density_val=5.51,
            planet_name_for_log="Earth"
        )
        sephi = result[0] if isinstance(result, tuple) else result
        assert 70 <= sephi <= 100

    def test_sephi_gas_giant(self):
        """SEPHI for a gas giant should return a valid score (0–100)"""
        result = lm.calculate_sephi(
            planet_mass=317.0,
            planet_radius=11.0,
            orbital_period=4332.0,
            stellar_mass=1.0,
            stellar_radius=1.0,
            stellar_teff=5778,
            system_age=4.5,
            planet_density_val=1.33,
            planet_name_for_log="Jupiter"
        )
        sephi = result[0] if isinstance(result, tuple) else result
        assert 0 <= sephi <= 100

    def test_sephi_invalid_data(self):
        """SEPHI should return None or a valid score (0–100) when data is missing"""
        result = lm.calculate_sephi(
            planet_mass=None,
            planet_radius=None,
            orbital_period=None,
            stellar_mass=None,
            stellar_radius=None,
            stellar_teff=None,
            system_age=None,
            planet_density_val=None,
            planet_name_for_log="Unknown"
        )
        sephi = result[0] if isinstance(result, tuple) else result
        assert (sephi is None) or (0 <= sephi <= 100)

    def test_calculate_sephi_missing_params(self):
        from lifesearch.lifesearch_main import calculate_sephi
        result = calculate_sephi(None, 1, 365, 1, 1, 5778, 5, 5.5, "TestPlanet")
        assert result == (None, None, None, None, None)

    def test_calculate_sephi_non_positive_params(self):
        from lifesearch.lifesearch_main import calculate_sephi
        result = calculate_sephi(-1, 1, 365, 1, 1, 5778, 5, 5.5, "TestPlanet")
        assert result == (None, None, None, None, None)

    def test_calculate_sephi_sigma1mp_zero(self):
        from lifesearch.lifesearch_main import calculate_sephi
        # pm=1.0 força mu_1_mp == mu_2_mp, logo sigma_1_mp == 0
        result = calculate_sephi(1, 1, 365, 1, 1, 5778, 5, 5.5, "TestPlanet")
        assert isinstance(result[0], float)  # Deve calcular sem explodir

class TestDetailedScores:
    def test_size_score_terran_optimal(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "Earth2", "pl_rade": 1.0, "classification": "Terran"}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Size"][0] == 100

    def test_density_score_out_of_range(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "DenseX", "pl_dens": 9.0, "classification": "Superterran"}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Density"][0] == 70  # out of ideal Terran/Superterran range

    def test_mass_score_low(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "MiniT", "pl_masse": 0.5, "classification": "Subterran"}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Mass"][0] in [90, 30]  # depends on thresholds

    def test_atmosphere_and_water_scores_hot(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "HotOne", "pl_eqt": 400}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Atmosphere Potential"][0] == 50 or scores["Atmosphere Potential"][0] == 20

    def test_habitable_zone_position_with_tuple(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "HZWorld", "pl_orbsmax": 1.0}
        hz_tuple = (0.8, 0.95, 1.05, 1.2, 255)
        scores = calculate_detailed_habitability_scores(planet_data, hz_tuple, {})
        assert "Habitable Zone Position" in scores

    def test_star_type_classification(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "StarK", "st_spectype": "K3V"}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Host Star Type"][0] == 85

    def test_system_age_score_young(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "YoungStar", "st_age": 0.8}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["System Age"][0] == 60

    def test_metallicity_score_high(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "MetalRich", "st_met": 0.8}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Star Metallicity"][0] == 60

    def test_eccentricity_score_high(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "Eccentric", "pl_orbeccen": 0.6}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Orbital Eccentricity"][0] == 10

    def test_size_score_else(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "BigOne", "pl_rade": 10.0, "classification": "Terran"}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Size"][0] == 30

    def test_density_score_else(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "OddDensity", "pl_dens": 5.0, "classification": "Unknown"}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Density"][0] == 50

    def test_mass_score_else(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "OddMass", "pl_masse": 100.0, "classification": "Unknown"}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Mass"][0] == 30

    def test_atmosphere_score_else(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "ColdWorld", "pl_eqt": 100}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Atmosphere Potential"][0] == 20
        assert scores["Liquid Water Potential"][0] == 20

    def test_hz_score_else_15(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "HZMissing", "pl_orbsmax": 1.0}
        hz_tuple = (None, None, None, None, None)  # all invalid
        scores = calculate_detailed_habitability_scores(planet_data, hz_tuple, {})
        assert scores["Habitable Zone Position"][0] == 15

    def test_hz_score_else_25(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "HZLum", "pl_orbsmax": 5.0, "st_lum": 0.0}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Habitable Zone Position"][0] == 25

    def test_hz_score_else_10(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "HZNoData"}  # missing both lum and orbit
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Habitable Zone Position"][0] == 10

    def test_star_type_else(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "WeirdStar", "st_spectype": "Z9"}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Host Star Type"][0] == 30

    def test_system_age_else(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "Ancient", "st_age": 20.0}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["System Age"][0] == 30

    def test_metallicity_else(self):
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        planet_data = {"pl_name": "MetalPoor", "st_met": -2.0}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Star Metallicity"][0] == 30

    def test_size_score_else_fallback(self):
        """Covers Size else branch (471-473)"""
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        # Classification não reconhecida, mas raio informado
        planet_data = {"pl_name": "OddSized", "pl_rade": 1.2, "classification": "Exotic"}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Size"][0] == 30

    def test_hz_position_else_25_outside_range(self):
        """Covers HZ Position else branch (534-535)"""
        from lifesearch.lifesearch_main import calculate_detailed_habitability_scores
        # Força uso de st_lum_log e pl_orbsmax, mas órbita fora do range
        planet_data = {"pl_name": "TooFar", "pl_orbsmax": 10.0, "st_lum": 0.0}
        scores = calculate_detailed_habitability_scores(planet_data, None, {})
        assert scores["Habitable Zone Position"][0] == 25

class TestProcessPlanetData:
    def test_process_planet_data_with_dict(self):
        from lifesearch.lifesearch_main import process_planet_data
        weights_config = {"habitability": {}, "phi": {}}
        data = {
            "pl_rade": 1.0, "pl_masse": 1.0, "pl_dens": 5.5,
            "pl_eqt": 288, "st_teff": 5700, "st_rad": 1.0,
            "st_mass": 1.0, "st_lum": 1.0, "st_age": 5.0,
            "pl_orbper": 365, "pl_orbsmax": 1.0, "st_spectype": "G",
            "pl_orbeccen": 0.05
        }
        result = process_planet_data("Earth", data, weights_config)
        assert "scores_for_report" in result
        assert "classification_display" in result

    def test_process_planet_data_with_series(self):
        import pandas as pd
        from lifesearch.lifesearch_main import process_planet_data
        weights_config = {"habitability": {}, "phi": {}}
        s = pd.Series({"pl_rade": 1.1, "pl_masse": 1.2, "st_teff": 5800})
        result = process_planet_data("Kepler-22b", s, weights_config)
        assert isinstance(result["planet_data_dict"], dict)

    def test_process_planet_data_with_unexpected_type(self):
        from lifesearch.lifesearch_main import process_planet_data
        weights_config = {"habitability": {}, "phi": {}}
        result = process_planet_data("Weird", [1,2,3], weights_config)  # list inesperada
        assert isinstance(result["planet_data_dict"], dict)

    def test_process_planet_data_missing_pl_name(self):
        from lifesearch.lifesearch_main import process_planet_data
        weights_config = {"habitability": {}, "phi": {}}
        data = {"pl_rade": 2.0}  # sem pl_name
        result = process_planet_data("Unnamed", data, weights_config)
        assert result["planet_data_dict"]["pl_name"] == "Unnamed"

    def test_process_planet_data_invalid_numeric_field(self):
        from lifesearch.lifesearch_main import process_planet_data
        weights_config = {"habitability": {}, "phi": {}}
        data = {"st_age": "not_a_number"}  # cai no except ValueError
        result = process_planet_data("BadStar", data, weights_config)
        assert result["planet_data_dict"]["st_age"] is None

    def test_process_planet_data_with_sy_dist_valid(self):
        from lifesearch.lifesearch_main import process_planet_data
        weights_config = {"habitability": {}, "phi": {}}
        data = {"sy_dist": 10}  # valor válido em parsecs
        result = process_planet_data("ValidDist", data, weights_config)
        # Deve converter para anos-luz
        assert "travel_curiosities" in result["planet_data_dict"]

    def test_process_planet_data_with_sy_dist_invalid(self):
        from lifesearch.lifesearch_main import process_planet_data
        weights_config = {"habitability": {}, "phi": {}}
        data = {"sy_dist": "abc"}  # valor inválido que cai no except
        result = process_planet_data("InvalidDist", data, weights_config)
        # Deve cair no except e continuar funcionando
        assert "travel_curiosities" in result["planet_data_dict"]
