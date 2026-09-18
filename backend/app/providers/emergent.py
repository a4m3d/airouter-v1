import asyncio

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

from app.config import SUPPORTED_MODELS
from app.providers.base import ProviderAdapter

DEFAULT_MAX_TOKENS = 8192


def split_messages(messages):
    """Split an OpenAI-style messages array into:
       system_message (str), initial_messages (role-structured history), last_text (str).

    We keep real roles (crucial for agentic clients like Cline) instead of flattening,
    passing prior turns via LlmChat(initial_messages=...) and sending the final user turn.
    """
    system_parts, convo = [], []
    for m in messages or []:
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") in (None, "text")
            )
        content = content if isinstance(content, str) else ("" if content is None else str(content))
        if role == "system":
            system_parts.append(content)
        else:
            # map tool/function results to user turns for provider-neutral text protocol
            r = "assistant" if role == "assistant" else "user"
            convo.append({"role": r, "content": content})

    system_message = "\n\n".join([p for p in system_parts if p]) or "You are a helpful AI assistant."
    if not convo:
        return system_message, [], ""
    last_text = convo[-1]["content"]
    initial = convo[:-1]
    return system_message, initial, last_text


def _build(api_key, session_id, messages, provider, model, max_tokens):
    system_message, initial, last_text = split_messages(messages)
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_message,
        initial_messages=initial or None,
    ).with_model(provider, model).with_params(max_tokens=max_tokens or DEFAULT_MAX_TOKENS)
    return chat, last_text


class EmergentAdapter(ProviderAdapter):
    name = "emergent"

    async def chat(self, *, api_key, session_id, messages, provider, model, timeout, max_tokens=None):
        chat, last_text = _build(api_key, session_id, messages, provider, model, max_tokens)
        resp = await asyncio.wait_for(chat.send_message(UserMessage(text=last_text)), timeout=timeout)
        if isinstance(resp, str):
            return resp
        for attr in ("text", "content", "message"):
            val = getattr(resp, attr, None)
            if isinstance(val, str):
                return val
        return str(resp)

    async def stream(self, *, api_key, session_id, messages, provider, model, max_tokens=None):
        chat, last_text = _build(api_key, session_id, messages, provider, model, max_tokens)
        async for event in chat.stream_message(UserMessage(text=last_text)):
            if isinstance(event, TextDelta):
                yield event.content
            elif isinstance(event, StreamDone):
                break

    def supported_models(self) -> dict:
        return SUPPORTED_MODELS
