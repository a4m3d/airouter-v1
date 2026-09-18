import logging
import re

# Redaction: never let credentials reach logs. Scrubs common secret shapes.
_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"(?i)(authorization|api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
]

REDACTED = "***REDACTED***"


def scrub(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    for pat in _PATTERNS:
        text = pat.sub(REDACTED, text)
    return text


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = scrub(record.msg)
            if record.args:
                record.args = tuple(scrub(a) if isinstance(a, str) else a for a in record.args)
        except Exception:
            pass
        return True


def setup_logging(level: str = "INFO"):
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    handler.addFilter(RedactionFilter())
    # Replace handlers so redaction always applies
    root.handlers = [handler]
    return logging.getLogger("router")
