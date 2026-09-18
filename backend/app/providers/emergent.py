import asyncio

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

from app.config import SUPPORTED_MODELS
from app.providers.base import ProviderAdapter


def flatten_messages(messages):
    """Flatten an OpenAI-style messages array into (system_message, prompt).

    The emergentintegrations LlmChat takes a system_message + a single UserMessage per
    stateless call, so we fold the transcript into one prompt. We do NOT persist history
    inside the library; the caller (coding agent) sends the full context each request.
    """
    system_parts, convo = [], []
    for m in messages or []:
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in (None, "text")
            )
        content = content or ""
        if role == "system":
            system_parts.append(content)
        else:
            convo.append((role, content))

    system_message = "\n\n".join([p for p in system_parts if p]) or "You are a helpful AI assistant."
    if len(convo) <= 1:
        prompt = convo[0][1] if convo else ""
    else:
        lines = []
        for role, content in convo:
            tag = "User" if role == "user" else ("Assistant" if role == "assistant" else role.capitalize())
            lines.append(f"{tag}: {content}")
        prompt = "\n\n".join(lines) + "\n\nAssistant:"
    return system_message, prompt


class EmergentAdapter(ProviderAdapter):
    name = "emergent"

    async def chat(self, *, api_key, session_id, system_message, prompt, provider, model, timeout):
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system_message,
        ).with_model(provider, model)
        resp = await asyncio.wait_for(
            chat.send_message(UserMessage(text=prompt)), timeout=timeout
        )
        if isinstance(resp, str):
            return resp
        # Defensive: some builds may return an object with .text / .content
        for attr in ("text", "content", "message"):
            val = getattr(resp, attr, None)
            if isinstance(val, str):
                return val
        return str(resp)

    async def stream(self, *, api_key, session_id, system_message, prompt, provider, model):
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system_message,
        ).with_model(provider, model)
        async for event in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(event, TextDelta):
                yield event.content
            elif isinstance(event, StreamDone):
                break

    def supported_models(self) -> dict:
        return SUPPORTED_MODELS
