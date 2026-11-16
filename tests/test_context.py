from types import SimpleNamespace

from bot import MAX_HISTORY_MESSAGES, _hospital_follow_up, _trim_history


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
