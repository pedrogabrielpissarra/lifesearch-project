from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional, Regexp

class PlanetSearchForm(FlaskForm):
    """Form for searching planets and optionally overriding parameters."""
    planet_names = TextAreaField(
        'Planet Names (separated by comma or new line)', 
        validators=[DataRequired(message="Please enter at least one planet name.")],
        render_kw={"rows": 3, "placeholder": "E.g.: Kepler-452 b, TRAPPIST-1 e, Proxima Cen b"}
    )
    parameter_overrides = TextAreaField(
        'Parameter Overrides (optional)',
        validators=[Optional()],
        render_kw={"rows": 5, "placeholder": "Format: PlanetName: param1=value1; param2=value2\nE.g.: Kepler-452 b: pl_rade=2.4; st_age=6.0\nTRAPPIST-1 e: pl_eqt=250"}
    )
    submit = SubmitField('Search Planets')

class HabitabilityWeightsForm(FlaskForm):
    """Form for configuring the weights of habitability factors."""
    factors = {
        "Habitable Zone": "Weight for Habitable Zone",
        "Size": "Weight for Size (Radius)",
        "Density": "Weight for Density",
        "Atmosphere": "Weight for Atmosphere",
        "Water": "Weight for Water",
        "Presence of Moons": "Weight for Presence of Moons",
        "Magnetic Activity": "Weight for Magnetic Activity (Star)",
        "System Age": "Weight for System Age"
    }

    for field_name, label_text in factors.items():
        form_field_name = field_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        field = FloatField(
            label_text, 
            validators=[Optional(), NumberRange(min=0, max=1, message="Weight must be between 0 and 1.")],
            default=1.0,
            render_kw={"step": "0.01"}
        )
        locals()[form_field_name] = field
    
    submit_weights = SubmitField('Save Weights')

class PHIWeightsForm(FlaskForm):
    """Form for configuring the weights of PHI (Planet Habitability Index) factors."""
    phi_factors = {
        "Solid Surface": "Weight for Solid Surface (PHI)",
        "Stable Energy": "Weight for Stable Energy (PHI)",
        "Life Compounds": "Weight for Life Compounds (PHI)",
        "Stable Orbit": "Weight for Stable Orbit (PHI)"
    }

    for field_name, label_text in phi_factors.items():
        form_field_name = field_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        field = FloatField(
            label_text,
            validators=[Optional(), NumberRange(min=0, max=1, message="Weight must be between 0 and 1.")],
            default=0.25,
            render_kw={"step": "0.01"}
        )
        locals()[form_field_name] = field

    submit_phi_weights = SubmitField('Save PHI Weights')

