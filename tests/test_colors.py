"""Colour decisions: when to emit ANSI, and which colour a number earns."""

import pytest

from jevgrep.colors import CONFIDENT, RESET, UNSURE, WAVERING, confidence_color, should_color


def test_never_means_never_even_on_a_tty():
    assert should_color("never", isatty=True, env={}) is False


def test_always_means_always_even_when_piped():
    assert should_color("always", isatty=False, env={}) is True


def test_auto_follows_the_tty():
    assert should_color("auto", isatty=True, env={}) is True
    assert should_color("auto", isatty=False, env={}) is False


def test_no_color_is_honoured_over_auto():
    assert should_color("auto", isatty=True, env={"NO_COLOR": "1"}) is False


def test_no_color_is_honoured_even_when_empty():
    # The NO_COLOR convention is presence-based, not value-based.
    assert should_color("auto", isatty=True, env={"NO_COLOR": ""}) is False


def test_always_overrides_no_color_because_the_user_asked_explicitly():
    assert should_color("always", isatty=True, env={"NO_COLOR": "1"}) is True


def test_a_dumb_terminal_gets_no_colour():
    assert should_color("auto", isatty=True, env={"TERM": "dumb"}) is False


def test_an_unknown_when_value_is_rejected():
    with pytest.raises(ValueError):
        should_color("sometimes", isatty=True, env={})


@pytest.mark.parametrize("value", [1.0, 0.95, 0.9])
def test_high_values_read_as_confident(value):
    assert confidence_color(value) == CONFIDENT


@pytest.mark.parametrize("value", [0.89, 0.75, 0.7])
def test_middling_values_read_as_wavering(value):
    assert confidence_color(value) == WAVERING


@pytest.mark.parametrize("value", [0.69, 0.16, 0.0])
def test_low_values_read_as_unsure(value):
    assert confidence_color(value) == UNSURE


def test_a_missing_value_reads_as_unsure():
    assert confidence_color(None) == UNSURE


def test_every_colour_is_a_distinct_escape_sequence():
    assert len({CONFIDENT, WAVERING, UNSURE}) == 3
    assert all(c.startswith("\033[") for c in (CONFIDENT, WAVERING, UNSURE, RESET))
