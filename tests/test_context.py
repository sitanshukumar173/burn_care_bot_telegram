from bot import MAX_HISTORY_MESSAGES, _trim_history


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
