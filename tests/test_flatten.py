from app.providers.emergent import flatten_messages


def test_single_user_message():
    sys, prompt = flatten_messages([{"role": "user", "content": "Hello"}])
    assert prompt == "Hello"
    assert "helpful" in sys.lower()


def test_system_extracted():
    sys, prompt = flatten_messages([
        {"role": "system", "content": "You are a coding agent."},
        {"role": "user", "content": "Write a function"},
    ])
    assert sys == "You are a coding agent."
    assert prompt == "Write a function"


def test_multi_turn_transcript_preserved():
    sys, prompt = flatten_messages([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "next step"},
    ])
    assert "User: hi" in prompt
    assert "Assistant: hello" in prompt
    assert prompt.strip().endswith("Assistant:")


def test_openai_content_parts():
    sys, prompt = flatten_messages([
        {"role": "user", "content": [{"type": "text", "text": "part one"}]},
    ])
    assert "part one" in prompt
