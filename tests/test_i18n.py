import re
import string
from html.parser import HTMLParser

import pytest

from i18n import LANGS, T, button_actions, region_name, t
from tbsa import Region

ALLOWED_TAGS = {"b", "i", "a"}


def _fields(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


@pytest.mark.parametrize("key", sorted(T))
def test_every_text_has_all_languages_with_same_placeholders(key):
    assert set(T[key]) == set(LANGS)
    assert len({frozenset(_fields(T[key][lang])) for lang in LANGS}) == 1


class _TagChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []

    def handle_starttag(self, tag, attrs):
        assert tag in ALLOWED_TAGS, tag
        self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack.pop() == tag, tag


@pytest.mark.parametrize("key", sorted(T))
@pytest.mark.parametrize("lang", LANGS)
def test_texts_are_valid_telegram_html(key, lang):
    text = T[key][lang]
    assert not re.search(r"&(?!amp;|lt;|gt;)", text), "unescaped &"
    checker = _TagChecker()
    checker.feed(text)
    assert checker.stack == []


@pytest.mark.parametrize("lang", LANGS)
def test_every_region_has_a_name(lang):
    names = {region_name(r, lang) for r in Region}
    assert len(names) == len(Region)


def test_region_names():
    assert region_name(Region.LEFT_FOREARM_FRONT, "en") == "Forearm (left, front)"
    assert region_name(Region.RIGHT_HAND_PALM, "hi") == "हाथ (दाएँ, हथेली)"
    assert region_name(Region.HEAD_FRONT, "hinglish") == "Chehra"


def test_button_labels_map_back_to_actions():
    actions = button_actions()
    assert actions["🛡 बचाव"] == "btn_prevention"
    assert actions["📍 Paas ke hospital"] == "btn_hospitals"
    assert actions["🩹 First aid"] == "btn_first_aid"


def test_missing_language_falls_back_to_english():
    assert t("fr", "reset_done") == T["reset_done"]["en"]
