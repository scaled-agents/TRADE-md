"""TRADE.md document parser.

Splits a TRADE.md file into YAML front matter and markdown prose sections,
returning a TradeDoc dataclass. No semantic validation here — that's the
linter's job.
"""
from __future__ import annotations

import importlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CustomIndicatorRef:
    """A single entry from ``custom_indicators:`` in front matter."""

    module: str
    as_name: str
    version_pin: str | None = None


@dataclass
class TradeDoc:
    """Parsed TRADE.md document.

    Attributes:
        front_matter: Raw YAML front matter as a dict.
        prose_sections: Ordered dict-like of H2 section title -> body text.
        raw_text: Original file contents.
        source_path: Path on disk, if parsed from a file.
        custom_indicators: Parsed ``custom_indicators:`` block.
    """
    front_matter: dict[str, Any]
    prose_sections: dict[str, str]
    raw_text: str
    source_path: Path | None = None
    custom_indicators: list[CustomIndicatorRef] = field(default_factory=list)

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

    @property
    def strategy_dir(self) -> Path | None:
        """Directory containing the TRADE.md, or None for string-parsed docs."""
        if self.source_path is not None:
            return self.source_path.parent
        return None

    def load_custom_indicators(self) -> dict[str, Any]:
        """Import each registered custom indicator module and return metadata.

        Returns ``{as_name: IndicatorMetadata}`` dict. Raises ImportError or
        ValueError on failures.
        """
        from .indicator import IndicatorMetadata

        strategy_dir = self.strategy_dir
        if not strategy_dir:
            raise ValueError(
                "Cannot load custom indicators without a strategy directory"
            )

        result: dict[str, IndicatorMetadata] = {}
        added_to_path = False
        str_dir = str(strategy_dir)

        if str_dir not in sys.path:
            sys.path.insert(0, str_dir)
            added_to_path = True

        try:
            for ref in self.custom_indicators:
                try:
                    mod = importlib.import_module(ref.module)
                except ImportError as e:
                    raise ImportError(
                        f"Cannot import custom indicator module {ref.module!r} "
                        f"from {strategy_dir}: {e}"
                    ) from e

                # Find the decorated function.
                meta = _find_indicator_metadata(mod, ref.module)
                result[ref.as_name] = meta
        finally:
            if added_to_path and str_dir in sys.path:
                sys.path.remove(str_dir)

        return result


def _find_indicator_metadata(mod: Any, module_name: str) -> Any:
    """Find the single @indicator-decorated function in a module."""
    from .indicator import IndicatorMetadata

    decorated = []
    for attr_name in dir(mod):
        obj = getattr(mod, attr_name)
        if callable(obj) and hasattr(obj, "_trade_md_metadata"):
            meta = obj._trade_md_metadata
            if isinstance(meta, IndicatorMetadata):
                decorated.append(meta)

    if len(decorated) == 0:
        raise ValueError(
            f"Module {module_name!r} has no @indicator-decorated function"
        )
    if len(decorated) > 1:
        raise ValueError(
            f"Module {module_name!r} has {len(decorated)} @indicator-decorated "
            f"functions; exactly one is required"
        )
    return decorated[0]


_FRONT_MATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)
_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)


def _parse_custom_indicators(
    fm: dict[str, Any], spec_version: str | None,
) -> list[CustomIndicatorRef]:
    """Parse the ``custom_indicators:`` block from front matter."""
    raw = fm.get("custom_indicators")
    if raw is None:
        return []

    # v0.1 strict mode — custom_indicators block is not allowed.
    if spec_version == "0.1":
        raise ValueError(
            "custom_indicators block is not allowed when trade_md_spec is '0.1'. "
            "Bump to '0.2' or remove the spec version declaration."
        )

    if not isinstance(raw, list):
        raise ValueError("custom_indicators must be a list of indicator entries")

    refs: list[CustomIndicatorRef] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"custom_indicators[{i}] must be a mapping")
        module = entry.get("module")
        as_name = entry.get("as")
        if not module or not as_name:
            raise ValueError(
                f"custom_indicators[{i}] requires 'module' and 'as' fields"
            )
        refs.append(CustomIndicatorRef(
            module=str(module),
            as_name=str(as_name),
            version_pin=str(entry["version_pin"]) if "version_pin" in entry else None,
        ))
    return refs


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

    spec_version = front_matter.get("trade_md_spec")
    custom_refs = _parse_custom_indicators(front_matter, spec_version)
    prose_sections = _split_sections(body)

    return TradeDoc(
        front_matter=front_matter,
        prose_sections=prose_sections,
        raw_text=text,
        source_path=source_path,
        custom_indicators=custom_refs,
    )


def parse_file(path: str | Path) -> TradeDoc:
    """Parse a TRADE.md file from disk.

    Accepts either a file path or a directory path. When given a directory,
    resolves to ``<dir>/TRADE.md``.
    """
    p = Path(path)
    if p.is_dir():
        p = p / "TRADE.md"
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
