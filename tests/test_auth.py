"""Tests for auth and source resolution."""

from unittest.mock import patch

from ipoe_forge.auth import resolve_sources
from ipoe_forge.config import NGA_SOURCES, PUBLIC_SOURCES
from ipoe_forge.models import AuthMode


def test_public_mode_returns_public():
    sources, msg = resolve_sources(AuthMode.PUBLIC)
    assert sources == PUBLIC_SOURCES
    assert "public" in msg.lower()


@patch("ipoe_forge.auth._test_nga_pki", return_value=False)
@patch("ipoe_forge.auth._test_nga_reachable", return_value=True)
@patch("ipoe_forge.auth._detect_pki_certs", return_value={"method": "test"})
def test_auto_mode_fallback_when_pki_fails(mock_certs, mock_reachable, mock_pki):
    sources, _msg = resolve_sources(AuthMode.AUTO)
    assert sources == PUBLIC_SOURCES


@patch("ipoe_forge.auth._test_nga_pki", return_value=True)
@patch("ipoe_forge.auth._test_nga_reachable", return_value=True)
@patch("ipoe_forge.auth._detect_pki_certs", return_value={"method": "test"})
def test_auto_mode_pki_success(mock_certs, mock_reachable, mock_pki):
    sources, _msg = resolve_sources(AuthMode.AUTO)
    assert sources == NGA_SOURCES


@patch("ipoe_forge.auth._test_nga_reachable", return_value=False)
@patch("ipoe_forge.auth._detect_pki_certs", return_value={"method": "test"})
def test_pki_mode_unreachable_raises(mock_certs, mock_reachable):
    import pytest
    with pytest.raises(ConnectionError, match="unreachable"):
        resolve_sources(AuthMode.PKI)
