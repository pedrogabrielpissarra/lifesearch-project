# LifeSearch (Gaia Arkadia) Formulas

This document lists the primary mathematical formulas used in the LifeSearch (Gaia Arkadia) program to evaluate exoplanet habitability. The formulas are based on data from the NASA Exoplanet Archive, HWC (`hwc.csv`), and HZGallery (`table-hzgallery.csv`). Each formula is presented in LaTeX, followed by an explanation of its function and application in habitability analysis.

## 1. Earth Similarity Index (ESI)

**Formula**:

\[
S_i = 1 - \left| \frac{x_i - x_{i,\text{Earth}}}{x_i + x_{i,\text{Earth}}} \right|
\]

\[
\text{scaled_component}_i = S_i + (1 - S_i) \cdot \frac{w_i}{\text{max_weight}}
\]

\[
\text{ESI} = \left( \frac{\sum \text{scaled_component}_i}{N} \right) \cdot 100
\]

**Parameters**:
- \(x_i\): Planet parameters (radius \(r\), density \(d\), equilibrium temperature \(T\)).
- \(x_{i,\text{Earth}}\): Earth values (\(r = 1.0 \, R_\oplus\), \(d = 5.51 \, \text{g/cm}^3\), \(T = 255 \, \text{K}\)).
- \(w_i\): User-adjustable weights (0.0 to 1.0, initialized with \(S_i\)).
- \(\text{max_weight}\): 1.0.
- \(N\): Number of valid parameters (e.g., 3 for radius, density, temperature).

**Explanation**:
The ESI measures an exoplanet's similarity to Earth by comparing radius, density, and equilibrium temperature. Each parameter is normalized relative to Earth, and adjustable weights allow users to modify their relative importance. The ESI ranges from 0 to 100%, with 100% achieved when all weights are 1.0 (adjusted perfect similarity) and the HWC real value (e.g., 33.33% for Kepler-477 b) reflected by initial weights based on actual similarities. Used in reports to indicate general habitability potential.

## 2. Planetary Habitability Index (PHI)

**Formula**:

\[
S_i = \begin{cases} 
0.8 & \text{if Terran or Superterran (Solid Surface)} \\
0.7 & \text{if G/K star and } 1.0 < \text{age} < 8.0 \, \text{Gyr (Stable Energy)} \\
0.0 & \text{(Life Compounds)} \\
0.9 & \text{if } e < 0.2 \, \text{(Stable Orbit)} \\
0.0 & \text{otherwise}
\end{cases}
\]

\[
\text{scaled_component}_i = S_i + (1 - S_i) \cdot \frac{w_i}{\text{max_weight}}
\]

\[
\text{PHI} = \left( \frac{\sum \text{scaled_component}_i}{N} \right) \cdot 100
\]

**Parameters**:
- \(S_i\): Factor score \(i\) (0.0, 0.7, 0.8, or 0.9, as defined above).
- \(w_i\): User-adjustable weights (0.0 to 0.25, initialized with \(\frac{S_i}{4} \cdot \frac{\text{PHI}_{\text{HWC}}}{100}\)).
- \(\text{max_weight}\): 0.25.
- \(N\): 4 (Solid Surface, Stable Energy, Life Compounds, Stable Orbit).

**Explanation**:
The PHI assesses habitability based on four factors: presence of a solid surface, energy stability, availability of life-essential compounds (currently not automatically assessed), and orbital stability. Each factor has a base score, interpolated to 1.0 based on the adjustable weight. The PHI ranges from 0 to 100%, with 100% achieved when all weights are 0.25, and the HWC real value (e.g., 42.5% for Kepler-477 b) reflected by scaled initial weights. Used in reports and interactively adjustable.

## 3. Standard Primary Habitability (SPH)

**Formula**:

\[
\text{SPH} = \begin{cases} 
70 + \left(1 - \frac{|T - 298.15|}{298.15 - 273.15}\right) \cdot 30 & \text{if } 273.15 \leq T \leq 323.15 \\
40 & \text{if } 250 \leq T < 273.15 \text{ or } 323.15 < T \leq 373.15 \\
10 & \text{otherwise}
\end{cases}
\]

**Parameters**:
- \(T\): Planet equilibrium temperature (K, measured or calculated).
- \(T_{\text{mid}} = 298.15 \, \text{K}\) (average of 273.15 and 323.15 K).

**Explanation**:
The SPH evaluates the planet's thermal suitability for liquid water, with higher scores for temperatures between 273.15 and 323.15 K, optimal for Earth-like life. Lower scores are assigned for temperatures near the ideal range, and a minimal score for extreme conditions. Used in reports to complement ESI and PHI, indicating potential for favorable thermal conditions.

## 4. Statistical-likelihood Exo-Planetary Habitability Index (SEPHI)

**Formula**:

\[
\text{SEPHI} = \sqrt[4]{L_1 \cdot L_2 \cdot L_3 \cdot L_4}
\]

- **L1 (Telluric Planet)**:

\[
\mu_1 = m^{0.27}, \quad \mu_2 = m^{0.5}, \quad \sigma_1 = \frac{\mu_2 - \mu_1}{3}
\]

\[
L_1 = \begin{cases} 
1 & \text{if } r \leq \mu_1 \\
\exp\left(-0.5 \cdot \left(\frac{r - \mu_1}{\sigma_1}\right)^2\right) & \text{if } \mu_1 < r < \mu_2 \\
0 & \text{otherwise}
\end{cases}
\]

- **L2 (Atmosphere and Gravity)**:

\[
v_e = \sqrt{\frac{m}{r^2} \cdot r}, \quad v_{e,\text{rel}} = \frac{v_e}{v_{e,\text{Earth}}}, \quad v_{e,\text{Earth}} = \sqrt{\frac{1}{1^2} \cdot 1}
\]

\[
L_2 = \begin{cases} 
\exp\left(-0.5 \cdot \left(\frac{v_{e,\text{rel}} - 1}{\sigma_{21}}\right)^2\right) & \text{if } v_{e,\text{rel}} < 1 \\
\exp\left(-0.5 \cdot \left(\frac{v_{e,\text{rel}} - 1}{\sigma_{22}}\right)^2\right) & \text{otherwise}
\end{cases}
\]

\[
\sigma_{21} = \frac{1 - 0}{3}, \quad \sigma_{22} = \frac{8.66 - 1}{3}
\]

- **L3 (Surface Liquid Water)**:

\[
L = \left(\frac{R}{R_\odot}\right)^2 \cdot \left(\frac{T}{T_\odot}\right)^4, \quad T_\odot = 5778 \, \text{K}
\]

\[
a = \left(\frac{G M P^2}{4\pi^2}\right)^{1/3}, \quad G = 6.67430 \times 10^{-11} \, \text{m}^3 \text{kg}^{-1} \text{s}^{-2}
\]

\[
S_{\text{eff}} = S_{\text{eff},\odot} + a(T - 5780) + b(T - 5780)^2 + c(T - 5780)^3 + d(T - 5780)^4
\]

\[
d_i = \sqrt{\frac{L}{S_{\text{eff},i}}}
\]

\[
L_3 = \begin{cases} 
1 & \text{if } d_2 \leq a \leq d_3 \\
\exp\left(-0.5 \cdot \left(\frac{a - d_2}{\sigma_{31}}\right)^2\right) & \text{if } d_1 \leq a < d_2 \\
\exp\left(-0.5 \cdot \left(\frac{a - d_3}{\sigma_{32}}\right)^2\right) & \text{if } d_3 < a \leq d_4 \\
0 & \text{otherwise}
\end{cases}
\]

\[
\sigma_{31} = \frac{d_2 - d_1}{3}, \quad \sigma_{32} = \frac{d_4 - d_3}{3}
\]

- Coeficientes (Kopparapu et al., 2013):
  - Recent Venus (\(d_1\)): \(S_{\text{eff},\odot} = 1.766\), \(a = 1.335 \times 10^{-4}\), etc.
  - Runaway Greenhouse (\(d_2\)): \(S_{\text{eff},\odot} = 1.038\), etc.
  - Maximum Greenhouse (\(d_3\)): \(S_{\text{eff},\odot} = 0.3438\), etc.
  - Early Mars (\(d_4\)): \(S_{\text{eff},\odot} = 0.3179\), etc.

- **L4 (Magnetic Field)**:

\[
a_{\text{lock}} \approx \left(\frac{M_{\text{star}}}{M_\odot}\right)^{1/3} \cdot \left(\frac{\rho_{\text{planet}}}{\rho_{\text{Earth}}}\right)^{-1/3} \cdot \left(\frac{t}{10 \, \text{Gyr}}\right)^{1/6} \cdot 0.06 \, \text{AU}
\]

\[
M_n = \alpha \cdot \rho_{0n}^{0.5} \cdot r_{0n}^{10/3} \cdot F_n^{1/3}
\]

\[
L_4 = \begin{cases} 
1 & \text{if } M_n \geq 1 \\
\exp\left(-0.5 \cdot \left(\frac{M_n - 1}{\sigma_4}\right)^2\right) & \text{otherwise}
\end{cases}
\]

\[
\sigma_4 = \frac{1 - 0}{3}
\]

**Parameters**:
- \(m\): Planet mass (\(M_\oplus\)).
- \(r\): Planet radius (\(R_\oplus\)).
- \(P\): Orbital period (days).
- \(M_{\text{star}}\): Stellar mass (\(M_\odot\)).
- \(R\): Stellar radius (\(R_\odot\)).
- \(T\): Stellar temperature (K).
- \(t\): System age (Gyr).
- \(\rho_{\text{planet}}\): Planet density (\(\rho_{\text{Earth}} = 5.51 \, \text{g/cm}^3\)).
- \(\alpha\): 0.05 (tidally locked) or 1.0 (non-tidally locked).
- For telluric planets: \(\rho_{0n} = 1.0\), \(r_{0n} = \beta_1\), \(F_n = \beta_1\), \(\beta_1 = r\).
- For others: adjusted values (e.g., \(\rho_{0n} = 0.16\) for gaseous).

**Explanation**:
The SEPHI calculates the statistical likelihood of habitability by combining four sub-indices: \(L_1\) (rocky planet), \(L_2\) (atmosphere retention), \(L_3\) (surface liquid water), and \(L_4\) (magnetic field). It ranges from 0 to 100%, used in detailed reports to assess habitability potential based on physical and orbital properties.

## 5. Equilibrium Temperature

**Formula**:

\[
T_{\text{eq}} = T_{\text{eff}} \cdot \left( \frac{R_{\text{star}}}{2 a} \right)^{0.5} \cdot (1 - A)^{0.25}
\]

**Parameters**:
- \(T_{\text{eff}}\): Stellar temperature (K, from `st_teff` or default 5778 K).
- \(R_{\text{star}}\): Stellar radius (\(R_\odot\), from `st_rad` or default 1.0).
- \(a\): Semi-major axis (AU, from `pl_orbsmax` or default 1.0).
- \(A\): Planet albedo (fixed at 0.3).

**Explanation**:
Calculates a planet's equilibrium temperature, assuming radiative equilibrium, when the measured temperature (`pl_eqt`) is unavailable. Used in ESI, PHI, and planet classification (Hypopsychroplanet, Mesoplanet, etc.) to assess habitability conditions. Adjusts stellar temperature by orbital distance and albedo to estimate surface temperature.

## 6. Habitable Zone Boundaries

**Formula**:

\[
d_{\text{in}} = \sqrt{\frac{L}{S_{\text{in}}}}, \quad d_{\text{out}} = \sqrt{\frac{L}{S_{\text{out}}}
\]

\[
d_{\text{in, opt}} = d_{\text{in}} \cdot 0.75, \quad d_{\text{out, opt}} = d_{\text{out}} \cdot 1.25
\]

**Parameters**:
- \(L\): Stellar luminosity (\(L_\odot\), calculated as \(L = 10^{\text{st_lum}}\)).
- \(S_{\text{in}}\): Inner effective solar flux (1.1).
- \(S_{\text{out}}\): Outer effective solar flux (0.53).

**Explanation**:
Determines the inner and outer boundaries of the conservative (\(d_{\text{in}}\), \(d_{\text{out}}\)) and optimistic (\(d_{\text{in, opt}}\), \(d_{\text{out, opt}}\)) habitable zones where liquid water may exist. Compares the planet’s semi-major axis (`pl_orbsmax`) to these boundaries to assess habitability zone placement. Used to score the "Habitable Zone Position" factor and visualize orbits in reports.

## 7. Planet Classification by Mass

**Formula**:

\[
\text{Class} = \begin{cases} 
\text{Asteroidan} & \text{if } m < 0.00001 \, M_\oplus \\
\text{Mercurian} & \text{if } 0.00001 \leq m < 0.1 \, M_\oplus \\
\text{Subterran} & \text{if } 0.1 \leq m < 0.5 \, M_\oplus \\
\text{Terran} & \text{if } 0.5 \leq m < 2 \, M_\oplus \\
\text{Superterran} & \text{if } 2 \leq m < 10 \, M_\oplus \\
\text{Neptunian} & \text{if } 10 \leq m < 50 \, M_\oplus \\
\text{Jovian} & \text{if } 50 \leq m < 5000 \, M_\oplus \\
\text{Unknown} & \text{otherwise}
\end{cases}
\]

\[
m = \begin{cases} 
r^{3.33} & \text{if } r < 1.5 \, R_\oplus \\
r^{2.0} & \text{otherwise}
\end{cases}
\]

**Parameters**:
- \(m\): Planet mass (\(M_\oplus\), from `pl_masse` or estimated).
- \(r\): Planet radius (\(R_\oplus\), from `pl_rade`).

**Explanation**:
Classifies the planet by mass into categories indicating type (rocky, gaseous, etc.). If mass (`pl_masse`) is unavailable, it is estimated from radius using approximate empirical relations. The classification defines the planet’s type (e.g., Superterran for Kepler-477 b) and influences habitability scores, such as "Solid Surface" in PHI.

## 8. Planet Classification by Temperature

**Formula**:

\[
\text{TempClass} = \begin{cases} 
\text{Hypopsychroplanet (Very Cold)} & \text{if } T < 170 \, \text{K} \\
\text{Psychroplanet (Cold)} & \text{if } 170 \leq T < 220 \, \text{K} \\
\text{Mesoplanet (Temperate 1)} & \text{if } 220 \leq T < 273 \, \text{K} \\
\text{Mesoplanet (Temperate 2 - Optimal)} & \text{if } 273 \leq T < 323 \, \text{K} \\
\text{Thermoplanet (Warm)} & \text{if } 323 \leq T < 373 \, \text{K} \\
\text{Hyperthermoplanet (Hot)} & \text{if } T \geq 373 \, \text{K} \\
\text{Unknown} & \text{if } T \text{ is missing or } T < 0
\end{cases}
\]

**Parameters**:
- \(T\): Equilibrium temperature (from `pl_eqt` or calculated via \(T_{\text{eq}}\)).

**Explanation**:
Classifies the planet by temperature to indicate thermal conditions, emphasizing "Mesoplanet (Temperate 2)" (273–323 K) as ideal for liquid water. Used in reports to form the complete classification (e.g., Superterran | Hyperthermoplanet for Kepler-477 b) and influence scores like "Atmosphere Potential" and "Liquid Water Potential".

## 9. Habitability Scores

**Formula**:

\[
\text{Score}_{\text{factor}} = \text{BaseScore}_{\text{factor}}
\]

**Parameters**:
- \(\text{BaseScore}_{\text{factor}}\): Base value (0-100) defined by rules:
  - Size: 100 (Terran, 0.8 ≤ \(r\) ≤ 1.5), 90 (Subterran/Superterran), 70 (Neptunian), 30 (Mercurian/Jovian).
  - Density: 100 (Terran, 4.5 ≤ \(d\) ≤ 6.5), 90 (3.0 ≤ \(d\) ≤ 8.0), 70 (outside ideal), 50 (others).
  - Habitable Zone: 95 (conservative zone), 65 (optimistic zone), 20 (outside).
  - Atmosphere/Water: 90 (273 < \(T\) ≤ 373 K), 50 (200-273 K or 373-450 K), 20 (others).
  - Presence of Moons: 80 (Terran/Superterran), 30 (others).
  - Magnetic Activity: 80 (mass > 1 \(M_\oplus\), G/K type), 60 (medium), 40 (low).
  - System Age: 90 (1.0 ≤ \(t\) ≤ 8.0 Gyr), 60 (0.5-1.0 or 8.0-10.0 Gyr), 30 (others).
  - Orbital Eccentricity: 95 (\(e \leq 0.1\)), 70 (\(e \leq 0.3\)), 40 (\(e \leq 0.5\)), 10 (others).
  - Host Star Type: 95 (G type), 85 (K), 70 (F), 60 (M), 30 (others).
  - Star Metallicity: 90 (-0.5 ≤ \(\text{met} \leq 0.5\)), 60 (-1.0 or 1.0), 30 (others).
- Weights (\(w_{\text{factor}}\)) are applied only in ESI and PHI calculations.

**Explanation**:
Calculates individual scores for habitability factors (Size, Density, Habitable Zone, etc.) based on planet conditions, without direct weight multiplication. Each factor is scored from 0 to 100 based on specific rules, reflecting specific habitability aspects. Used in detailed reports, while ESI and PHI provide aggregate metrics.

## 10. Travel Times

**Formula**:

\[
t = \frac{d}{v}
\]

**Parameters**:
- \(d\): Planet distance in light-years (from `sy_dist` converted by \(d = \text{sy_dist} \cdot 3.26156\)).
- \(v\): Velocities (fraction of light speed):
  - Current technology: \(0.000057 \, c\).
  - 20% light speed: \(0.20 \, c\).
  - Near light speed: \(0.9999 \, c\).

**Explanation**:
Estimates travel time to the planet under three velocity scenarios, from current technology to relativistic speeds. Used in reports as a curiosity, highlighting exploration feasibility (e.g., 20999868.8 years, 5985.0 years, 1197.1 years for Kepler-477 b).

## 11. Size and Density Comparison

**Formula**:

\[
r_{\text{comp}} = r
\]

\[
d_{\text{comp}} = \frac{d}{d_{\text{Earth}}}, \quad d_{\text{Earth}} = 5.51 \, \text{g/cm}^3
\]

**Parameters**:
- \(r\): Planet radius (\(R_\oplus\), from `pl_rade`).
- \(d\): Planet density (\(\text{g/cm}^3\), from `pl_dens`).

**Explanation**:
Compares the planet’s radius and density to Earth’s to contextualize physical properties. The program reports `pl_rade` and `pl_dens` directly (e.g., 2.07 \(R_\oplus\), 3.06 \(\text{g/cm}^3\) for Kepler-477 b), and relative density (\(d_{\text{comp}}\)) can be inferred by dividing by Earth’s value. Used in reports for intuitive reference.

## 12. Weight Pre-filling

**Formula**:

- ESI:
  \[
  w_{i,\text{initial}} = 1 - \left| \frac{x_i - x_{i,\text{Earth}}}{x_i + x_{i,\text{Earth}}} \right|
  \]

- PHI:
  \[
  w_{i,\text{initial}} = \frac{S_i}{4} \cdot \frac{\text{PHI}_{\text{HWC}}}{100}
  \]

**Parameters**:
- ESI:
  - \(x_i\): Radius (\(r\)), density (\(d\)), equilibrium temperature (\(T\)).
  - \(x_{i,\text{Earth}}\): \(r = 1.0 \, R_\oplus\), \(d = 5.51 \, \text{g/cm}^3\), \(T = 255 \, \text{K}\).
- PHI:
  - \(S_i\): Factor score \(i\) (0.0, 0.7, 0.8, or 0.9, as defined in PHI).
  - \(\text{PHI}_{\text{HWC}}\): HWC real PHI value (e.g., 42.5% for Kepler-477 b).
  - 4: Maximum sum of factor scores assuming all are 1.0.

**Explanation**:
Sets initial weights for ESI (Size, Density, Habitable Zone) and PHI (Solid Surface, Stable Energy, Life Compounds, Stable Orbit) factors based on HWC real values. For ESI, weights are the actual similarities; for PHI, weights are scaled proportionally to the real PHI divided by the maximum factor score sum. These weights are pre-filled in the configuration interface (`configure.html`), allowing users to adjust values to increase (up to 100%) or decrease indices.

## 13. Initial Weight Restoration

**Formula**:

\[
w_{i,\text{reset}} = \begin{cases} 
\text{INITIAL_HAB_WEIGHTS}[i] & \text{if ESI factor} \\
\text{INITIAL_PHI_WEIGHTS}[i] & \text{if PHI factor} \\
w_{i,\text{default}} & \text{if initial value is undefined}
\end{cases}
\]

**Parameters**:
- \(\text{INITIAL_HAB_WEIGHTS}\): Initial ESI weights (e.g., 0.75, 0.83, 0.36 for Kepler-477 b).
- \(\text{INITIAL_PHI_WEIGHTS}\): Initial PHI weights (e.g., 0.085, 0.0, 0.0, 0.096 for Kepler-477 b).
- \(w_{i,\text{default}}\): 1.0 (ESI) or 0.25 (PHI).

**Explanation**:
The "Reset to Defaults" button in the configuration interface (`configure.html`) restores the weights of ESI and PHI factors to their pre-filled initial values, reflecting the HWC real values (e.g., ESI = 33.33%, PHI = 42.5% for Kepler-477 b). This allows users to revert to initial conditions after adjustments, ensuring consistency with HWC data.
