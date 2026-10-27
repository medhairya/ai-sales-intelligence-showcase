"""Input and output guardrails applied around every LLM call.

Input checks run before the request leaves the gateway:
  * empty / oversized prompts are rejected
  * common prompt-injection phrases are blocked
  * emails and phone numbers are redacted so PII never reaches the provider

Output checks run on the model's reply before it reaches the user:
  * any PII the model echoes back is redacted
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s-]?)?(?:\d[\s-]?){9,11}\d(?!\w)")

INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all|any|the) (previous|prior|above) instructions",
        r"disregard (the )?system prompt",
        r"reveal (your|the) (system prompt|instructions)",
        r"you are now (in )?developer mode",
    )
]


class GuardrailViolation(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class GuardrailResult:
    text: str
    redactions: list[str] = field(default_factory=list)


def redact_pii(text: str) -> GuardrailResult:
    redactions: list[str] = []

    def _sub(pattern: re.Pattern[str], label: str, value: str) -> str:
        def repl(_: re.Match[str]) -> str:
            redactions.append(label)
            return f"[{label}]"

        return pattern.sub(repl, value)

    text = _sub(EMAIL_RE, "EMAIL", text)
    text = _sub(PHONE_RE, "PHONE", text)
    return GuardrailResult(text=text, redactions=redactions)


def check_input(prompt: str, max_chars: int) -> GuardrailResult:
    if not prompt or not prompt.strip():
        raise GuardrailViolation("empty_prompt")
    if len(prompt) > max_chars:
        raise GuardrailViolation("prompt_too_long")
    for pattern in INJECTION_PATTERNS:
        if pattern.search(prompt):
            raise GuardrailViolation("prompt_injection")
    return redact_pii(prompt)


def check_output(reply: str) -> GuardrailResult:
    return redact_pii(reply)
