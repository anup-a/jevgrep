"""httpx pins certifi and ignores SSL_CERT_FILE, which breaks behind a TLS-inspecting proxy."""

import shutil
import ssl
from pathlib import Path

import pytest

from jevgrep.client import build_verify
from jevgrep.config import ConfigError


@pytest.fixture
def bundle(tmp_path) -> str:
    """A copy of the system CA bundle, so build_verify has something real to load."""
    target = tmp_path / "ca.pem"
    shutil.copyfile(Path(ssl.get_default_verify_paths().openssl_cafile), target)
    return str(target)


def test_no_bundle_configured_falls_back_to_default_verification():
    assert build_verify({}) is True


def test_ssl_cert_file_is_honoured(bundle):
    assert isinstance(build_verify({"SSL_CERT_FILE": bundle}), ssl.SSLContext)


def test_jevgrep_ca_bundle_wins_over_ssl_cert_file(bundle):
    env = {"JEVGREP_CA_BUNDLE": bundle, "SSL_CERT_FILE": "/does/not/exist"}

    assert isinstance(build_verify(env), ssl.SSLContext)


def test_a_bundle_path_that_does_not_exist_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        build_verify({"JEVGREP_CA_BUNDLE": str(tmp_path / "missing.pem")})


def test_a_blank_bundle_value_is_ignored():
    assert build_verify({"SSL_CERT_FILE": "   "}) is True


def test_verification_is_never_silently_disabled(bundle):
    context = build_verify({"SSL_CERT_FILE": bundle})

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
