import pytest

from jevgrep.config import ConfigError, load_config

ENV = {
    "JEVGREP_API_KEY": "sk-test",
    "JEVGREP_BASE_URL": "https://ai-gateway.vercel.sh/v4/ai",
    "JEVGREP_MODEL": "typesafe-ai/jev",
}


def test_loads_from_environment():
    config = load_config(ENV)

    assert config.api_key == "sk-test"
    assert config.endpoint == "https://ai-gateway.vercel.sh/v4/ai/evaluation-model"
    assert config.model == "typesafe-ai/jev"


def test_base_url_and_model_have_defaults():
    config = load_config({"JEVGREP_API_KEY": "sk-test"})

    assert config.endpoint.endswith("/v4/ai/evaluation-model")
    assert config.model == "typesafe-ai/jev"


def test_trailing_slashes_in_the_base_url_are_normalised():
    config = load_config({**ENV, "JEVGREP_BASE_URL": "https://ai-gateway.vercel.sh/v4/ai///"})

    assert config.endpoint == "https://ai-gateway.vercel.sh/v4/ai/evaluation-model"


def test_a_missing_api_key_is_a_config_error():
    with pytest.raises(ConfigError) as excinfo:
        load_config({})

    # The message must name every variable that would have worked, not just one.
    message = str(excinfo.value)
    assert "JEVUTILS_API_KEY" in message
    assert "JEVGREP_API_KEY" in message
    assert "TYPESAFE_API_KEY" in message


def test_a_blank_api_key_is_a_config_error():
    with pytest.raises(ConfigError):
        load_config({"JEVGREP_API_KEY": "   "})


def test_a_non_http_base_url_is_a_config_error():
    with pytest.raises(ConfigError):
        load_config({**ENV, "JEVGREP_BASE_URL": "ftp://example.com"})


def test_jevutils_variables_are_accepted():
    config = load_config({"JEVUTILS_API_KEY": "sk-suite", "JEVUTILS_MODEL": "m"})

    assert config.api_key == "sk-suite"
    assert config.model == "m"


def test_jevutils_wins_over_the_older_names():
    env = {
        "JEVUTILS_API_KEY": "sk-new",
        "JEVGREP_API_KEY": "sk-old",
        "TYPESAFE_API_KEY": "sk-older",
    }

    assert load_config(env).api_key == "sk-new"


def test_the_old_jevgrep_names_keep_working_after_the_rename():
    assert load_config({"JEVGREP_API_KEY": "sk-old"}).api_key == "sk-old"


def test_typesafe_variables_are_accepted_as_a_fallback():
    config = load_config({"TYPESAFE_API_KEY": "sk-fallback", "TYPESAFE_MODEL": "typesafe-ai/jev"})

    assert config.api_key == "sk-fallback"


def test_jevgrep_variables_win_over_the_typesafe_fallback():
    config = load_config({"JEVGREP_API_KEY": "sk-own", "TYPESAFE_API_KEY": "sk-fallback"})

    assert config.api_key == "sk-own"


def test_the_api_key_is_not_leaked_by_repr():
    assert "sk-test" not in repr(load_config(ENV))
