"""Tests for configuration."""

from ipoe_forge.config import NGA_SOURCES, PUBLIC_SOURCES, SLOPE_THRESHOLDS


def test_public_sources_have_topo_and_imagery():
    assert "topo" in PUBLIC_SOURCES
    assert "imagery" in PUBLIC_SOURCES


def test_nga_sources_need_auth():
    for src in NGA_SOURCES.values():
        assert src.needs_auth is True


def test_tile_source_url_template():
    src = PUBLIC_SOURCES["topo"]
    url = src.url_template.format(z=13, x=4000, y=3000)
    assert "13" in url
    assert "4000" in url
    assert "3000" in url


def test_slope_thresholds_ordering():
    assert SLOPE_THRESHOLDS["unrestricted_max_deg"] < SLOPE_THRESHOLDS["restricted_max_deg"]
    assert SLOPE_THRESHOLDS["restricted_max_deg"] == SLOPE_THRESHOLDS["severely_restricted_min_deg"]
