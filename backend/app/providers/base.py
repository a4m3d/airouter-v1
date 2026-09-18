from abc import ABC, abstractmethod


class ProviderAdapter(ABC):
    """Provider abstraction. Add new providers by implementing this interface;
    the routing/failover engine is provider-neutral."""

    name: str = "base"

    @abstractmethod
    async def chat(self, *, api_key, session_id, system_message, prompt, provider, model, timeout):
        """Return assistant text for a non-streaming completion. Raises on error."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, *, api_key, session_id, system_message, prompt, provider, model):
        """Async generator yielding text deltas. Raises on error."""
        raise NotImplementedError

    @abstractmethod
    def supported_models(self) -> dict:
        raise NotImplementedError
