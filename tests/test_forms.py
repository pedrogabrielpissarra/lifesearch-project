import pytest
from flask import Flask
from app.forms import PlanetSearchForm, HabitabilityWeightsForm, PHIWeightsForm


@pytest.fixture
def app():
    """Create Flask app instance and WTForms configuration for testing."""
    app = Flask(__name__)
    app.config["WTF_CSRF_ENABLED"] = False
    app.secret_key = "test_secret"
    return app


class TestForms:
    def test_planet_search_form_valid(self, app):
        """Form should validate with valid planet names and parameter overrides."""
        with app.test_request_context(method="POST", data={
            "planet_names": "Kepler-452 b",
            "parameter_overrides": "Kepler-452 b: pl_rade=2.4"
        }):
            form = PlanetSearchForm()
            assert form.validate() is True
            assert "Kepler-452 b" in form.planet_names.data

    def test_planet_search_form_invalid_without_names(self, app):
        """Form should fail validation if no planet names are provided."""
        with app.test_request_context(method="POST", data={"planet_names": ""}):
            form = PlanetSearchForm()
            assert form.validate() is False
            assert "Please enter at least one planet name." in form.planet_names.errors

    def test_habitability_weights_form_defaults(self, app):
        """All weights in HabitabilityWeightsForm should be between 0 and 1 by default."""
        with app.test_request_context(method="POST"):
            form = HabitabilityWeightsForm()
            for field_name in form.factors.keys():
                field = getattr(
                    form,
                    field_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
                )
                assert 0 <= field.data <= 1

    def test_phi_weights_form_defaults(self, app):
        """All weights in PHIWeightsForm should default to 0.25."""
        with app.test_request_context(method="POST"):
            form = PHIWeightsForm()
            for field_name in form.phi_factors.keys():
                field = getattr(
                    form,
                    field_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
                )
                assert field.data == 0.25

    def test_invalid_weight_value(self, app):
        """Form should fail validation if a weight is outside the 0-1 range."""
        with app.test_request_context(method="POST", data={"habitable_zone": 2}):
            form = HabitabilityWeightsForm()
            form.validate()
            assert "Weight must be between 0 and 1." in form.habitable_zone.errors
