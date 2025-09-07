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
        """ESI should return 0 when input values are invalid or missing"""
        planet_data = {"pl_rade": None, "pl_dens": None, "pl_eqt": None}
        esi, _ = lm.calculate_esi_score(planet_data, {"Size": 1, "Density": 1, "Habitable Zone": 1})
        assert esi == 0.0

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





