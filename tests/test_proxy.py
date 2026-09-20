"""httpx inherits the macOS *system* proxy, which silently reroutes API traffic.

On a dev machine that is usually a local debugging proxy (Bifrost, Charles, mitmproxy)
whose generated certificates OpenSSL 3 refuses. An explicit HTTPS_PROXY is a deliberate
choice and is honoured; a system-wide setting is not.
"""

from jevgrep.client import build_proxy


def test_no_proxy_configured():
    assert build_proxy({}) is None


def test_https_proxy_is_honoured():
    assert build_proxy({"HTTPS_PROXY": "http://gw.example:3128"}) == "http://gw.example:3128"


def test_lowercase_https_proxy_is_honoured():
    assert build_proxy({"https_proxy": "http://gw.example:3128"}) == "http://gw.example:3128"


def test_all_proxy_is_a_fallback():
    assert build_proxy({"ALL_PROXY": "http://gw.example:3128"}) == "http://gw.example:3128"


def test_https_proxy_wins_over_all_proxy():
    env = {"HTTPS_PROXY": "http://specific:1", "ALL_PROXY": "http://general:2"}

    assert build_proxy(env) == "http://specific:1"


def test_blank_values_are_ignored():
    assert build_proxy({"HTTPS_PROXY": "   "}) is None
