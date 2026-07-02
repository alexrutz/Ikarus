"""Navdata, geodesy and procedure tests."""

import math

import pytest

from ikarus.nav import geo, procedures
from ikarus.nav.database import NavDatabase


@pytest.fixture(scope="module")
def db():
    return NavDatabase()


def test_geo_dist_bearing():
    # EDDF -> EDDM is ~160 nm on a southeasterly course
    d = geo.dist_nm(50.0267, 8.5584, 48.3538, 11.7861)
    assert 155 < d < 170
    b = geo.bearing_deg(50.0267, 8.5584, 48.3538, 11.7861)
    assert 120 < b < 135


def test_geo_cross_track_sign():
    # point right of a northbound leg has positive XTK
    xtk = geo.cross_track_nm(50.0, 8.1, 49.5, 8.0, 50.5, 8.0)
    assert xtk > 3
    xtk_left = geo.cross_track_nm(50.0, 7.9, 49.5, 8.0, 50.5, 8.0)
    assert xtk_left < -3


def test_geo_destination_roundtrip():
    lat, lon = geo.destination(50.0, 8.0, 135.0, 60.0)
    assert abs(geo.dist_nm(50.0, 8.0, lat, lon) - 60.0) < 0.2
    assert abs(geo.bearing_deg(50.0, 8.0, lat, lon) - 135.0) < 1.0


def test_airport_and_runways(db):
    eddf = db.airport("EDDF")
    assert eddf is not None
    assert abs(eddf.lat - 50.027) < 0.01
    rwys = {r.ident for r in db.runways("EDDF")}
    assert {"25L", "25R", "07C"} <= rwys
    r25l = db.runway("EDDF", "25L")
    assert abs(r25l.heading_true - 249.6) < 1


def test_navaid_lookup(db):
    rid = db.navaid("RID", near=(50.0, 8.5))
    assert rid is not None and abs(rid.lat - 49.78) < 0.05
    by_freq = db.navaid_by_freq(112200, 50.0, 8.5)
    assert by_freq is not None and by_freq.ident == "RID"


def test_procedures_load():
    eddf = procedures.load_airport("EDDF")
    assert "RIDAR7S" in eddf.sids
    assert "ILS25L" in eddf.approaches
    appr = eddf.approaches["ILS25L"]
    assert appr.runway == "25L"
    assert appr.loc_freq_khz == 111150
    sid = eddf.sids["RIDAR7S"]
    assert sid.legs[0].fix == "OBOKA"
    assert sid.legs[1].alt_above == 5000


def test_magvar_plausible():
    assert 1 < geo.magvar_deg(50.0, 8.6) < 6        # Frankfurt ~3.5E
    assert 11 < geo.magvar_deg(37.6, -122.4) < 16   # SFO ~13E
