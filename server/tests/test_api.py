import datetime as dt

import simulate_device
from conftest import DEVICE, SITE

JUNE_DAY = 1781913600  # 2026-06-20 00:00 UTC


def body(records, device=DEVICE, site=SITE):
    return {"device": device, "fw": "test", "rssi": -70, "vbat_mV": 3900, "site": site, "records": records}


def test_upload_requires_token(client, auth):
    rec = [[0, JUNE_DAY + 43200, 1500, 2500, 2000, 3900, 0]]
    assert client.post("/api/v1/upload", json=body(rec)).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert client.post("/api/v1/upload", json=body(rec), headers=bad).status_code == 401
    other = client.post("/api/v1/upload", json=body(rec, device="unknown"), headers=auth)
    assert other.status_code == 401


def test_upload_idempotent_and_ack(client, auth):
    recs = [[i, JUNE_DAY + 43200 + 60 * i, 1500, 2500, None, 3900, 0] for i in range(5)]
    r = client.post("/api/v1/upload", json=body(recs), headers=auth)
    assert r.status_code == 200
    assert r.json() == {"last_seq": 4, "stored": 5}
    r = client.post("/api/v1/upload", json=body(recs[2:]), headers=auth)  # resend
    assert r.json() == {"last_seq": 4, "stored": 0}
    r = client.post("/api/v1/upload", json=body([]), headers=auth)  # heartbeat
    assert r.json()["last_seq"] == 4

    data = client.get(f"/api/v1/devices/{DEVICE}/data").json()
    assert len(data) == 5
    assert data[0]["isc_ma"] == 150.0
    assert data[0]["tamb"] is None
    assert data[0]["irradiance"] == round(150.0 * 1000 / 190, 1)

    devs = client.get("/api/v1/devices").json()
    assert devs[0]["id"] == DEVICE and devs[0]["tilt"] == 35.0 and devs[0]["last_rssi"] == -70


def test_upload_validation(client, auth):
    bad_row = [[0, 1, 2]]
    assert client.post("/api/v1/upload", json=body(bad_row), headers=auth).status_code == 422
    too_many = [[i, JUNE_DAY + i, 0, None, None, 3900, 0] for i in range(501)]
    assert client.post("/api/v1/upload", json=body(too_many), headers=auth).status_code == 422


def test_simulated_week_end_to_end(client, auth):
    rows = list(simulate_device.generate(JUNE_DAY, 7, SITE["lat"], SITE["lon"], SITE["tilt"], SITE["azimuth"]))

    def post(b):
        r = client.post("/api/v1/upload", json=b, headers=auth)
        assert r.status_code == 200, r.text
        return r.json()

    assert simulate_device.upload(rows, post, DEVICE, SITE) == len(rows)

    daily = client.get(f"/api/v1/devices/{DEVICE}/daily").json()
    assert len(daily) == 7
    for d in daily:
        assert d["coverage"] > 0.95
        # UK June: overcast ~1, clear ~5.5 kWh/kWp per day
        assert 0.3 < d["pv_kwh_per_kwp"] < 6.5
        assert d["insolation_kwh_m2"] > d["pv_kwh_per_kwp"]  # PR < 1
        assert d["thermal_tube_kwh_m2"] > 0

    s = client.get(f"/api/v1/devices/{DEVICE}/summary", params={"reference": "false"}).json()
    assert s["days_logged"] == 7 and s["days_full_coverage"] == 7
    assert s["calibration"]["source"] == "nominal"
    assert s["annual_estimate_kwh_per_kwp"] is None  # needs PVGIS

    csv = client.get(f"/api/v1/devices/{DEVICE}/data.csv", params={"start": "2026-06-21", "end": "2026-06-22"})
    lines = csv.text.strip().splitlines()
    assert lines[0].startswith("seq,utc,isc_mA")
    assert all("2026-06-21" in ln for ln in lines[1:])

    page = client.get(f"/devices/{DEVICE}")
    assert page.status_code == 200 and DEVICE in page.text
    assert DEVICE in client.get("/").text


def test_summary_with_cached_pvgis(client, auth, monkeypatch):
    from solarlog_server.analysis import reference
    from test_analysis import PVGIS_FIXTURE

    calls = []

    def fake_fetch(*a, **k):
        calls.append(a)
        return reference.parse_pvgis(PVGIS_FIXTURE)

    monkeypatch.setattr(reference, "fetch_pvgis", fake_fetch)
    rows = list(simulate_device.generate(JUNE_DAY, 3, SITE["lat"], SITE["lon"], SITE["tilt"], SITE["azimuth"]))
    simulate_device.upload(rows, lambda b: client.post("/api/v1/upload", json=b, headers=auth).json(), DEVICE, SITE)
    s1 = client.get(f"/api/v1/devices/{DEVICE}/summary").json()
    s2 = client.get(f"/api/v1/devices/{DEVICE}/summary").json()
    assert len(calls) == 1  # second call served from cache
    assert s1 == s2
    june = next(m for m in s1["months"] if m["month"] == 6)
    assert june["days"] == 3 and june["site_factor"] > 0
    assert s1["annual_estimate_kwh_per_kwp"] > 0
    assert s1["pvgis_annual_kwh_per_kwp"] == round(sum(m.e_m for m in reference.parse_pvgis(PVGIS_FIXTURE)), 1)


def test_manual_calibration(client, auth):
    client.post("/api/v1/upload", json=body([[0, JUNE_DAY + 43200, 1000, None, None, 3900, 0]]), headers=auth)
    r = client.post(f"/api/v1/devices/{DEVICE}/calibration", json={"factor": 6.0})
    assert r.json() == {"factor": 6.0}
    assert client.get(f"/api/v1/devices/{DEVICE}/data").json()[0]["irradiance"] == 600.0
    r = client.post(f"/api/v1/devices/{DEVICE}/calibration", json={"factor": None, "isc_stc_ma": 200})
    assert r.json() == {"factor": 5.0}
    assert client.get("/api/v1/devices/nope/daily").status_code == 404


def test_unsynced_and_invalid_records_excluded(client, auth):
    t = JUNE_DAY + 43200
    recs = [[0, t, 1500, None, None, 3900, 1 << 5], [1, t + 60, 1500, None, None, 3900, 1 << 4]]
    client.post("/api/v1/upload", json=body(recs), headers=auth)
    assert client.get(f"/api/v1/devices/{DEVICE}/daily").json() == []
    assert dt.date(2026, 6, 20)  # sanity: fixture date
