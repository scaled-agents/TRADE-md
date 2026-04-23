"""TRADE.md document parser.

Splits a TRADE.md file into YAML front matter and markdown prose sections,
returning a TradeDoc dataclass. No semantic validation here — that's the
linter's job.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TradeDoc:
    """Parsed TRADE.md document.

    Attributes:
        front_matter: Raw YAML front matter as a dict.
        prose_sections: Ordered dict-like of H2 section title -> body text.
        raw_text: Original file contents.
        source_path: Path on disk, if parsed from a file.
    """
    front_matter: dict[str, Any]
    prose_sections: dict[str, str]
    raw_text: str
    source_path: Path | None = None

    @property
    def name(self) -> str:
        return self.front_matter.get("name", "")

    @property
    def version(self) -> str:
        return str(self.front_matter.get("version", ""))

    @property
    def signals(self) -> dict[str, Any]:
        return self.front_matter.get("signals", {}) or {}

    @property
    def indicators(self) -> dict[str, Any]:
        return self.front_matter.get("indicators", {}) or {}

    @property
    def risk(self) -> dict[str, Any]:
        return self.front_matter.get("risk", {}) or {}

    @property
    def market(self) -> dict[str, Any]:
        return self.front_matter.get("market", {}) or {}

    @property
    def sizing(self) -> dict[str, Any]:
        return self.front_matter.get("sizing", {}) or {}


_FRONT_MATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)
_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)


def parse_string(text: str, source_path: Path | None = None) -> TradeDoc:
    """Parse a TRADE.md file from a string.

    Raises:
        ValueError: if the file has no YAML front matter delimited by `---`.
        yaml.YAMLError: if the front matter is not valid YAML.
    """
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        raise ValueError(
            "TRADE.md must begin with YAML front matter delimited by `---` lines"
        )
    fm_raw = match.group("fm")
    body = match.group("body")

    front_matter = yaml.safe_load(fm_raw) or {}
    if not isinstance(front_matter, dict):
        raise ValueError("Front matter must be a YAML mapping")

    prose_sections = _split_sections(body)

    return TradeDoc(
        front_matter=front_matter,
        prose_sections=prose_sections,
        raw_text=text,
        source_path=source_path,
    )


def parse_file(path: str | Path) -> TradeDoc:
    """Parse a TRADE.md file from disk."""
    p = Path(path)
    return parse_string(p.read_text(encoding="utf-8"), source_path=p)


def _split_sections(body: str) -> dict[str, str]:
    """Split markdown body on H2 headings, returning {title: body_text}."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    if not matches:
        return sections

    for i, m in enumerate(matches):
        title = m.group("title").strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[title] = body[start:end].strip()
    return sections
