"""Local, project-scoped placeholder memory.

The store is deliberately behind the gateway boundary. It lets the same
protected entity retain the same placeholder across related requests without
ever exposing the original value to an MCP client or external model.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


PLACEHOLDER_RE = re.compile(r"^\[([A-Z_]+)_(\d+)\]$")


@dataclass(frozen=True)
class MemoryEntry:
    entity_type: str
    canonical_value: str
    original_value: str
    placeholder: str


class ProjectMemoryStore:
    def __init__(self, database_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self.database_path = database_path or root / "data" / "project_memory.db"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS placeholder_memory (
                    project_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    canonical_value TEXT NOT NULL,
                    original_value TEXT NOT NULL,
                    placeholder TEXT NOT NULL,
                    PRIMARY KEY (project_id, entity_type, canonical_value),
                    UNIQUE (project_id, placeholder)
                )
                """
            )

    @staticmethod
    def _canonical(value: str) -> str:
        return " ".join(value.casefold().split())

    def load(self, project_id: str) -> list[MemoryEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT entity_type, canonical_value, original_value, placeholder "
                "FROM placeholder_memory WHERE project_id = ? ORDER BY placeholder",
                (project_id,),
            ).fetchall()
        return [MemoryEntry(*row) for row in rows]

    def remember(self, project_id: str, mapping: dict[str, str]) -> None:
        """Persist only the mappings used in a completed local request."""
        entries: list[tuple[str, str, str, str, str]] = []
        for placeholder, original_value in mapping.items():
            match = PLACEHOLDER_RE.match(placeholder)
            if not match:
                continue
            entity_type = match.group(1)
            entries.append((project_id, entity_type, self._canonical(original_value), original_value, placeholder))
        if not entries:
            return
        with self._connect() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO placeholder_memory "
                "(project_id, entity_type, canonical_value, original_value, placeholder) VALUES (?, ?, ?, ?, ?)",
                entries,
            )

    def count(self, project_id: str) -> int:
        with self._connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM placeholder_memory WHERE project_id = ?", (project_id,)).fetchone()[0]
            )

