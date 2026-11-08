import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tools"))

from solarlog_server.app import create_app  # noqa: E402

TOKEN = "s3cret"
DEVICE = "dev-1"
SITE = {"lat": 51.5074, "lon": -0.1278, "tilt": 35.0, "azimuth": 180.0}


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "t.db"), {DEVICE: TOKEN}, tz="Europe/London")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {TOKEN}"}
