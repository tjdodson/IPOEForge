"""PKI/cert detection and source resolution with public fallback."""

from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional

import httpx

from .config import NGA_SOURCES, PUBLIC_SOURCES, TileSource
from .models import AuthMode

logger = logging.getLogger(__name__)

_NGA_TEST_URLS = [
    "https://map.nga.mil/",
    "https://websvcs.geo.nga.mil/",
]


def _detect_pki_certs() -> Optional[dict]:
    """Attempt to detect DoD PKI certificates from the system."""
    system = platform.system()

    if system == "Darwin":
        try:
            result = subprocess.run(
                ["security", "find-certificate", "-a", "-c", "DoD", "-p"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return {"method": "keychain", "available": True}
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    elif system == "Linux":
        for p in [
            Path("/etc/pki/tls/certs/ca-bundle.crt"),
            Path("/etc/ssl/certs/ca-certificates.crt"),
        ]:
            if p.exists():
                return {"method": "file", "path": str(p), "available": True}
    elif system == "Windows":
        try:
            result = subprocess.run(
                ["certutil", "-generateSSTFromCA", "-store", "Root", "roots.sst", "NUL"],
                capture_output=True, timeout=10,
            )
            if result.returncode == 0:
                return {"method": "windows_store", "available": True}
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return None


def _test_nga_reachable(timeout: float = 5.0) -> bool:
    """Quick HEAD request to check if NGA services are reachable."""
    for url in _NGA_TEST_URLS:
        try:
            resp = httpx.head(url, timeout=timeout, follow_redirects=True)
            if resp.status_code < 500:
                return True
        except (httpx.TimeoutException, httpx.ConnectError):
            continue
    return False


def _test_nga_pki(timeout: float = 10.0) -> bool:
    """Test if NGA services respond with PKI auth (not 401/403)."""
    for url in _NGA_TEST_URLS:
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            if resp.status_code == 200:
                return True
            elif resp.status_code in (401, 403):
                return False
        except (httpx.TimeoutException, httpx.ConnectError):
            continue
    return False


def resolve_sources(mode: AuthMode) -> tuple[dict[str, TileSource], str]:
    """Determine which tile sources to use based on auth mode."""
    has_pki = _detect_pki_certs() is not None

    if has_pki and mode in (AuthMode.PKI, AuthMode.AUTO):
        if _test_nga_reachable():
            if mode == AuthMode.PKI or _test_nga_pki():
                return NGA_SOURCES, "Using NGA/PKI sources"
            else:
                return PUBLIC_SOURCES, "NGA PKI auth failed — using public sources"
        elif mode == AuthMode.PKI:
            raise ConnectionError(
                "PKI mode requested but NGA services are unreachable. "
                "Check network/VPN or use --mode auto/public."
            )

    if mode == AuthMode.AUTO:
        return PUBLIC_SOURCES, "NGA not reachable — using public sources"

    return PUBLIC_SOURCES, "Using public/open sources"
