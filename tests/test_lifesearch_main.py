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
        """Deve retornar a cor correta (paleta Material Design) para diferentes valores percentuais"""
        assert lm.get_color_for_percentage(value) == expected

    # ---------------------------
    # calculate_travel_times
    # ---------------------------
    def test_calculate_travel_times(self):
        """Deve calcular tempos de viagem válidos para distância em anos-luz"""
        times = lm.calculate_travel_times(10)
        assert isinstance(times, dict)
        assert "scenario_1_time" in times
        assert "scenario_2_time" in times
        assert "scenario_3_time" in times
        for v in times.values():
            assert isinstance(v, str)
            assert v != ""

    def test_calculate_travel_times_invalid(self):
        """Deve retornar strings descritivas mesmo para entrada inválida (ex: None)"""
        times = lm.calculate_travel_times(None)
        assert isinstance(times, dict)
        for v in times.values():
            assert isinstance(v, str)
            assert v != ""  # não esperamos 'N/A', mas pelo menos string não vazia

    # ---------------------------
    # classify_planet
    # ---------------------------
    def test_classify_planet_terran(self):
        """Deve classificar como Terran planet para valores próximos da Terra"""
        classification = lm.classify_planet(radius_earth=1.0, mass_earth=1.0, temp_k=288)
        assert "Terran" in classification or "Earth-like" in classification

    def test_classify_planet_jovian(self):
        """Deve classificar como Jovian planet para valores grandes"""
        classification = lm.classify_planet(radius_earth=11.0, mass_earth=317.0, temp_k=120)
        assert "Jovian" in classification

    def test_classify_planet_unknown(self):
        """Deve retornar classificação descritiva Unknown quando não há dados suficientes"""
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