import pytest

from epubgen.styles import (
    DEFAULT_NAMES,
    EXTRA_NAMES,
    REQUIRED_SECTIONS,
    list_default_styles,
    load_style,
)


@pytest.mark.parametrize("name", DEFAULT_NAMES + EXTRA_NAMES)
def test_load_style(name):
    s = load_style(name)
    assert s.name == name
    assert s.guide
    assert s.css
    for section in REQUIRED_SECTIONS:
        assert section in s.guide, f"{name} missing {section}"


def test_list_defaults_excludes_extras():
    names = [n for n, _ in list_default_styles()]
    assert set(names) == set(DEFAULT_NAMES)
    for extra in EXTRA_NAMES:
        assert extra not in names


def test_unknown_style_raises():
    from epubgen.errors import ConfigError

    with pytest.raises(ConfigError):
        load_style("does-not-exist")
