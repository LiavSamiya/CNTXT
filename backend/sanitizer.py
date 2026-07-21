"""Local, deterministic data transformation for ShieldAI.

No content is sent to an external model during detection. The detector is
deliberately explainable: policy dictionaries, regular expressions, checksum
validation, and a stable in-request placeholder map.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class DetectedEntity:
    entity_type: str
    value: str
    placeholder: str
    detector: str


@dataclass(frozen=True)
class _Match:
    start: int
    end: int
    entity_type: str
    value: str
    detector: str
    priority: int


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")
IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
API_KEY_RE = re.compile(r"\b(?:sk|pk|ghp|xox[baprs])-?[A-Za-z0-9_\-]{16,}\b", re.I)
# The optional magnitude is kept in the same optional group as its preceding
# space. This prevents a match such as "$15M " from swallowing the separator
# before the next word during replacement.
AMOUNT_RE = re.compile(r"(?<!\w)(?:USD\s*)?\$\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s?[KMB])?\b", re.I)
GPS_RE = re.compile(r"(?<!\d)-?\d{1,2}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}(?!\d)")
CREDIT_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _canonical(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _luhn_valid(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        number = int(digit)
        if index % 2:
            number = number * 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


class Sanitizer:
    """Produce stable, typed replacements for a single gateway request."""

    def __init__(self, policy: dict):
        self.policy = policy
        self._by_value: dict[tuple[str, str], str] = {}
        self._reverse_map: dict[str, str] = {}
        self._counters: dict[str, int] = {}
        self._entities: list[DetectedEntity] = []

    def _placeholder(self, entity_type: str, value: str, detector: str) -> str:
        key = (entity_type, _canonical(value))
        existing = self._by_value.get(key)
        if existing:
            return existing
        next_index = self._counters.get(entity_type, 0) + 1
        self._counters[entity_type] = next_index
        placeholder = f"[{entity_type}_{next_index}]"
        self._by_value[key] = placeholder
        self._reverse_map[placeholder] = value
        self._entities.append(
            DetectedEntity(entity_type=entity_type, value=value, placeholder=placeholder, detector=detector)
        )
        return placeholder

    def _dictionary_matches(self, text: str) -> Iterable[_Match]:
        for value, entity_type in self.policy.get("protected_terms", {}).items():
            for match in re.finditer(re.escape(value), text, flags=re.IGNORECASE):
                yield _Match(match.start(), match.end(), entity_type, match.group(0), "policy dictionary", 100)

    @staticmethod
    def _regex_matches(text: str) -> Iterable[_Match]:
        patterns = (
            (JWT_RE, "TOKEN", "JWT pattern", 95),
            (API_KEY_RE, "API_KEY", "API key pattern", 94),
            (EMAIL_RE, "EMAIL", "email pattern", 80),
            (IPV4_RE, "SERVER", "IPv4 pattern", 72),
            (GPS_RE, "LOCATION", "GPS pattern", 82),
            (AMOUNT_RE, "AMOUNT", "currency pattern", 75),
            (PHONE_RE, "PHONE", "phone pattern", 70),
        )
        for pattern, entity_type, detector, priority in patterns:
            for match in pattern.finditer(text):
                yield _Match(match.start(), match.end(), entity_type, match.group(0), detector, priority)
        for match in CREDIT_CARD_RE.finditer(text):
            if _luhn_valid(match.group(0)):
                yield _Match(match.start(), match.end(), "CREDIT_CARD", match.group(0), "Luhn-validated card", 98)

    @staticmethod
    def _non_overlapping(matches: list[_Match]) -> list[_Match]:
        selected: list[_Match] = []
        # Security-sensitive and dictionary hits win before generic regexes.
        for candidate in sorted(matches, key=lambda item: (-item.priority, -(item.end - item.start), item.start)):
            overlaps = any(candidate.start < item.end and candidate.end > item.start for item in selected)
            if not overlaps:
                selected.append(candidate)
        return sorted(selected, key=lambda item: item.start)

    def sanitize(self, text: str) -> str:
        matches = self._non_overlapping([*self._dictionary_matches(text), *self._regex_matches(text)])
        # Allocate identifiers in reading order, then edit from the end so
        # string indices remain valid. This gives the first person mentioned
        # `[PERSON_1]`, which makes the transformed context easier to follow.
        replacements = [
            (match, self._placeholder(match.entity_type, match.value, match.detector))
            for match in matches
        ]
        output = text
        for match, placeholder in reversed(replacements):
            output = output[:match.start] + placeholder + output[match.end:]
        return output

    def rehydrate(self, text: str) -> str:
        """Replace only placeholders issued by this exact request instance."""
        output = text
        for placeholder, original in self._reverse_map.items():
            output = output.replace(placeholder, original)
        return output

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self._reverse_map)

    @property
    def entities(self) -> list[dict]:
        return [asdict(entity) for entity in self._entities]
