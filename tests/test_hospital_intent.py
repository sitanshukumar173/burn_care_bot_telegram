import pytest

from hospitals import parse_hospital_request


@pytest.mark.parametrize("text, place", [
    ("nearby hospital", None),
    ("📍 hospital near me", None),
    ("hospitals", None),
    ("burn hospital", None),
    ("Find hospitals near IIT Patna", "IIT Patna"),
    ("which is the nearest hospital in Bihta?", "Bihta"),
    ("show doctors around Danapur please", "Danapur"),
    ("where is a burn unit in Patna", "Patna"),
    ("burn hospital in Danapur", "Danapur"),
    ("मेरे पास अस्पताल", None),
    ("नजदीकी हॉस्पिटल", None),
    ("Bihta mein hospital", "Bihta"),
    ("Patna ke paas burn hospital batao", "Patna"),
    ("koi aspatal Danapur me hai kya?", "Danapur"),
    ("paas ka hospital batao", None),
    ("mere ghar ke paas hospital", None),
    ("hospital kahan hai", None),
    ("बिहटा में अस्पताल", "बिहटा"),
    ("पटना के पास अस्पताल बताओ", "पटना"),
])
def test_detects_hospital_requests(text, place):
    assert parse_hospital_request(text) == (True, place)


@pytest.mark.parametrize("text", [
    "I burned my hand with hot oil, what should I do?",
    "should I go to hospital for a small blister on my finger?",
    "when should a burn be seen by a doctor",
    "who won the cricket match",
    "should I go to hospital in case of large blisters?",
    "kya mujhe hospital jaana chahiye?",
    "क्या मुझे अस्पताल जाना चाहिए?",
    "garam tel se haath jal gaya, kya karun?",
])
def test_ignores_other_messages(text):
    assert parse_hospital_request(text)[0] is False
