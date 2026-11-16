from types import SimpleNamespace

from bot import (
    MAX_HISTORY_MESSAGES,
    _apply_side_correction,
    _hospital_follow_up,
    _hospital_tags,
    _record_findings,
    _trim_history,
)
from hospitals import Place
from llm import ImageFindings, RegionFinding
from llm import _normalize_vision_payload
from tbsa import Depth, Region, RegionBurn, BurnCase


def test_context_keeps_only_three_latest_exchanges():
    history = [
        (role, f"{role}-{i}")
        for i in range(5)
        for role in ("user", "model")
    ]

    _trim_history(history)

    assert len(history) == MAX_HISTORY_MESSAGES
    assert history == [
        ("user", "user-2"),
        ("model", "model-2"),
        ("user", "user-3"),
        ("model", "model-3"),
        ("user", "user-4"),
        ("model", "model-4"),
    ]


def test_context_trimming_does_not_change_short_history():
    history = [("user", "question"), ("model", "answer")]

    _trim_history(history)

    assert history == [("user", "question"), ("model", "answer")]


def test_hospital_follow_up_prefers_listed_burn_unit():
    context = SimpleNamespace(
        user_data={
            "last_hospitals": [
                {"name": "Nearest Hospital", "distance_km": 2.0, "burn_unit": False, "major": False},
                {"name": "Burn Centre", "distance_km": 8.0, "burn_unit": True, "major": False},
            ]
        },
        bot_data={"config": SimpleNamespace(emergency_numbers="112")},
    )

    answer = _hospital_follow_up("which one is best?", context)

    assert answer is not None
    assert "Burn Centre" in answer


def test_hospital_tags_show_all_matching_categories():
    place = Place(
        name="Specialist Hospital",
        kind="hospital",
        lat=0,
        lon=0,
        distance_km=1,
        phone=None,
        burn_unit=True,
        major=True,
    )

    tags = _hospital_tags(place, "en")

    assert "BURN-CARE SPECIALIST" in tags
    assert "Major/government" in tags


def test_side_correction_moves_hand_and_forearm_to_left():
    case = BurnCase(
        burns={
            Region.RIGHT_HAND_BACK: RegionBurn(Region.RIGHT_HAND_BACK, 0.8, Depth.SUPERFICIAL_PARTIAL),
            Region.RIGHT_FOREARM_BACK: RegionBurn(Region.RIGHT_FOREARM_BACK, 0.2, Depth.SUPERFICIAL_PARTIAL),
        }
    )

    corrected = _apply_side_correction("But this is left hand", case)

    assert corrected == "left"
    assert set(case.burns) == {Region.LEFT_HAND_BACK, Region.LEFT_FOREARM_BACK}


def test_confirmed_side_replaces_model_placeholder_side():
    context = SimpleNamespace(
        user_data={},
        bot_data={"config": SimpleNamespace(emergency_numbers="112")},
    )
    findings = ImageFindings(
        is_burn=True,
        description="Burn on the back of a hand.",
        regions=[
            RegionFinding(
                region=Region.RIGHT_HAND_BACK,
                fraction=0.5,
                depth=Depth.SUPERFICIAL_PARTIAL,
            )
        ],
        circumferential=False,
        red_flags=[],
        side_uncertain=True,
    )

    case = _record_findings(context, findings, "left")

    assert set(case.burns) == {Region.LEFT_HAND_BACK}


def test_vision_payload_normalizes_bare_region_and_marks_side_uncertain():
    payload = {
        "is_burn": True,
        "description": "Visible burn on the hand.",
        "regions": [{"region": "hand_back", "fraction": 0.5, "depth": "superficial_partial"}],
        "circumferential": False,
        "red_flags": [],
    }

    normalized = _normalize_vision_payload(payload)

    assert normalized["regions"][0]["region"] == "right_hand_back"
    assert normalized["side_uncertain"] is True
