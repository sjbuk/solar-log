import datetime as dt
import math

import pytest

from solarlog_server.analysis import calibration, pv_model, reference, thermal_model
from solarlog_server.analysis.solar import cos_incidence, daylight_seconds, sun_position

JUNE_NOON = 1782043200  # 2026-06-21 12:00 UTC
DEC_NOON = 1797854400  # 2026-12-21 12:00 UTC


# --------------------------------------------------------------------------- solar
def test_sun_position_matches_noaa():
    london = sun_position(JUNE_NOON, 51.5074, -0.1278)
    assert london.elevation == pytest.approx(61.9, abs=0.5)
    assert london.azimuth == pytest.approx(180, abs=5)
    edinburgh = sun_position(DEC_NOON, 55.9533, -3.1883)
    assert edinburgh.elevation == pytest.approx(10.4, abs=0.5)
    morning = sun_position(JUNE_NOON - 5 * 3600, 51.5074, -0.1278)
    assert 60 < morning.azimuth < 100  # east-ish at 07:00 UTC


def test_cos_incidence_and_daylight():
    sun = sun_position(JUNE_NOON, 51.5074, -0.1278)
    # A south panel tilted at (90 - elevation) faces the sun.
    assert cos_incidence(sun, 90 - sun.elevation, 180) == pytest.approx(1.0, abs=0.01)
    assert cos_incidence(sun, 90, 0) < 0  # north-facing wall: sun behind
    day = JUNE_NOON - 12 * 3600
    assert daylight_seconds(day, day + 86400, 51.5074, -0.1278) / 3600 == pytest.approx(16.6, abs=0.3)


# --------------------------------------------------------------------------- PV model
def test_pv_power_stc_and_temperature():
    p = pv_model.PvParams()
    assert pv_model.pv_power_per_kwp(1000, 25, p) == pytest.approx(0.86)
    assert pv_model.pv_power_per_kwp(1000, 50, p) == pytest.approx(0.86 * 0.9)
    assert pv_model.pv_power_per_kwp(0, 25, p) == 0
    assert pv_model.module_temperature(800, 20, None) == pytest.approx(45)
    assert pv_model.module_temperature(800, None, 33) == 33
    assert pv_model.module_temperature(800, None, None) == 25


def test_integrate_skips_gaps():
    # 1000 W/m2 for one hour at 60 s steps -> 1000 Wh, then a gap, then another 10 min
    series = [(t, 1000.0) for t in range(0, 3601, 60)] + [(t, 1000.0) for t in range(10000, 10601, 60)]
    total, covered = pv_model.integrate(series, max_gap_s=300)
    assert covered == 3600 + 600
    assert total == pytest.approx(1000 * (3600 + 600) / 3600)


def test_energy_one_hour_at_stc():
    samples = [(t, 1000.0, None, 25.0) for t in range(0, 3601, 60)]
    kwh, _ = pv_model.energy_kwh_per_kwp(samples)
    assert kwh == pytest.approx(0.86)


# --------------------------------------------------------------------------- thermal
def test_thermal_model():
    fp = thermal_model.FLAT_PLATE
    # dT = 0 -> eta0 * G
    assert thermal_model.useful_heat_w_m2(800, 50, 50, fp) == pytest.approx(0.78 * 800)
    dt_ = 40
    expected = 0.78 * 800 - 3.5 * dt_ - 0.015 * dt_ * dt_
    assert thermal_model.useful_heat_w_m2(800, 10, 50, fp) == pytest.approx(expected)
    assert thermal_model.useful_heat_w_m2(50, 0, 60, fp) == 0  # losses exceed gain
    # Evacuated tubes beat flat plates when cold
    assert thermal_model.useful_heat_w_m2(300, 0, 60, thermal_model.EVACUATED_TUBE) > \
        thermal_model.useful_heat_w_m2(300, 0, 60, fp)


# --------------------------------------------------------------------------- calibration
def test_hourly_means_hour_end_keys():
    samples = [(3600 + 60 * i, 100.0) for i in range(1, 61)]  # 01:01 .. 02:00
    means = calibration.hourly_means(samples)
    assert means == {7200: 100.0}
    assert calibration.hourly_means([(60, 1.0)]) == {}  # too few samples


def test_fit_factor_ignores_shaded_hours():
    true_k = 5.2
    clear = [(g / true_k, g) for g in (400, 500, 600, 700, 800, 900)]
    shaded = [(g / true_k * 0.4, g) for g in (500, 600, 700)]  # shading cuts Isc
    k = calibration.fit_factor(clear + shaded)
    assert k == pytest.approx(true_k, rel=0.05)
    assert calibration.fit_factor(clear[:3]) is None
    assert calibration.default_factor(200) == 5.0


# --------------------------------------------------------------------------- reference
PVGIS_FIXTURE = {
    "outputs": {"monthly": {"fixed": [
        {"month": m, "E_d": ed, "E_m": round(ed * days, 2), "H(i)_d": 0, "H(i)_m": 0, "SD_m": 0}
        for m, ed, days in zip(range(1, 13),
                               [0.8, 1.5, 2.4, 3.4, 3.9, 4.0, 3.9, 3.4, 2.8, 1.8, 1.0, 0.6],
                               [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    ]}}
}


def test_azimuth_conventions():
    assert reference.compass_to_south_zero(180) == 0
    assert reference.compass_to_south_zero(90) == -90  # east
    assert reference.compass_to_south_zero(270) == 90  # west
    assert reference.compass_to_south_zero(0) == 180
    assert "aspect=-90" in reference.pvgis_url(51.5, -0.1, 35, 90)


def test_parse_pvgis_and_compare():
    months = reference.parse_pvgis(PVGIS_FIXTURE)
    assert len(months) == 12 and months[5].e_d == 4.0
    daily = [(dt.date(2026, 6, d), 3.2, 1.0) for d in range(1, 11)]  # 80 % of PVGIS
    daily += [(dt.date(2026, 6, 11), 0.1, 0.2)]  # low coverage, ignored
    rows, annual = reference.compare_months(daily, months)
    june = rows[5]
    assert june.days == 10
    assert june.site_factor == pytest.approx(0.8)
    assert annual == pytest.approx(0.8 * sum(m.e_m for m in months))
    _, none = reference.compare_months([], months)
    assert none is None


def test_parse_open_meteo():
    data = {"hourly": {"time": ["2026-06-21T12:00", "2026-06-21T13:00"],
                       "global_tilted_irradiance": [850.0, None]}}
    assert reference.parse_open_meteo(data) == {JUNE_NOON: 850.0}
    url = reference.open_meteo_url(51.5, -0.1, 35, 180, dt.date(2026, 6, 1), dt.date(2026, 6, 30))
    assert "global_tilted_irradiance" in url and "azimuth=0" in url
    assert math.isfinite(len(url))
