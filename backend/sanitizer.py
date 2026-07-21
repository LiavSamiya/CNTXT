"""Local, deterministic data transformation for ShieldAI.

No content is sent to an external model during detection. The detector is
deliberately explainable: policy dictionaries, regular expressions, checksum
validation, and a stable in-request placeholder map.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

from .project_memory import MemoryEntry


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
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)")
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

    def __init__(self, policy: dict, remembered_mappings: Sequence[MemoryEntry] = ()):
        self.policy = policy
        self._active_types: set[str] = set(policy.get("active_entity_types", set()))
        self._by_value: dict[tuple[str, str], str] = {}
        self._original_by_placeholder: dict[str, str] = {}
        self._reverse_map: dict[str, str] = {}
        self._counters: dict[str, int] = {}
        self._entities: list[DetectedEntity] = []
        self._seen_entity_placeholders: set[str] = set()
        for entry in remembered_mappings:
            self._by_value[(entry.entity_type, entry.canonical_value)] = entry.placeholder
            self._original_by_placeholder[entry.placeholder] = entry.original_value
            number_match = re.search(r"_(\d+)\]$", entry.placeholder)
            if number_match:
                self._counters[entry.entity_type] = max(self._counters.get(entry.entity_type, 0), int(number_match.group(1)))

    def _is_active(self, entity_type: str) -> bool:
        """Check whether the entity type is enabled by the current policy."""
        # When no explicit filter is set, allow everything (backward compat).
        if not self._active_types:
            return True
        return entity_type in self._active_types

    def _placeholder(self, entity_type: str, value: str, detector: str) -> str:
        key = (entity_type, _canonical(value))
        existing = self._by_value.get(key)
        if existing:
            original_value = self._original_by_placeholder.get(existing, value)
            self._reverse_map[existing] = original_value
            if existing not in self._seen_entity_placeholders:
                self._entities.append(DetectedEntity(entity_type=entity_type, value=original_value, placeholder=existing, detector=detector))
                self._seen_entity_placeholders.add(existing)
            return existing
        next_index = self._counters.get(entity_type, 0) + 1
        self._counters[entity_type] = next_index
        placeholder = f"[{entity_type}_{next_index}]"
        self._by_value[key] = placeholder
        self._original_by_placeholder[placeholder] = value
        self._reverse_map[placeholder] = value
        self._entities.append(
            DetectedEntity(entity_type=entity_type, value=value, placeholder=placeholder, detector=detector)
        )
        self._seen_entity_placeholders.add(placeholder)
        return placeholder

    def _dictionary_matches(self, text: str) -> Iterable[_Match]:
        for value, entity_type in self.policy.get("protected_terms", {}).items():
            if not self._is_active(entity_type):
                continue
            for match in re.finditer(re.escape(value), text, flags=re.IGNORECASE):
                yield _Match(match.start(), match.end(), entity_type, match.group(0), "policy dictionary", 100)

    def _regex_matches(self, text: str) -> Iterable[_Match]:
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
            if not self._is_active(entity_type):
                continue
            for match in pattern.finditer(text):
                yield _Match(match.start(), match.end(), entity_type, match.group(0), detector, priority)
        if self._is_active("CREDIT_CARD"):
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
