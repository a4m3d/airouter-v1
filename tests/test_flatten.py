from app.providers.emergent import split_messages


def test_single_user_message():
    sys, initial, last = split_messages([{"role": "user", "content": "Hello"}])
    assert last == "Hello"
    assert initial == []
    assert "helpful" in sys.lower()


def test_system_extracted():
    sys, initial, last = split_messages([
        {"role": "system", "content": "You are a coding agent."},
        {"role": "user", "content": "Write a function"},
    ])
    assert sys == "You are a coding agent."
    assert last == "Write a function"


def test_multi_turn_roles_preserved():
    sys, initial, last = split_messages([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "next step"},
    ])
    assert initial == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    assert last == "next step"


def test_openai_content_parts():
    sys, initial, last = split_messages([
        {"role": "user", "content": [{"type": "text", "text": "part one"}]},
    ])
    assert "part one" in last
