from __future__ import annotations

"""Discover project header inventories for later selection and parsing.

This module provides filesystem- and include-driven helpers that collect
project headers as ``HeaderFile`` records. ``discover_headers()`` wraps those
helpers and returns one ``HeaderSelection`` with every discovered header active
by default.

These are convenience helpers, not the only supported workflow. Callers may
build ``HeaderFile`` or ``HeaderSelection`` inputs by other means when they
need more control.
"""

import re
from pathlib import Path
from typing import Iterable
from .selection import HeaderFile, HeaderSelection


# ==================================================================================================
#     Public Functions
# ==================================================================================================


def find_all_headers(directory: str | Path) -> list[HeaderFile]:
    """Recursively collect all header files from a base directory."""

    base_dir = _normalize_path(Path(directory))
    header_files = [
        _to_header_file(path, base_dir)
        for path in sorted(base_dir.rglob("*"))
        if _is_header_file(path)
    ]
    return header_files


def find_included_headers(base_dir: str | Path, header_file: str | Path) -> list[HeaderFile]:
    """Collect included project headers in preorder, starting from one header file."""

    resolved_base_dir = _normalize_path(Path(base_dir))
    root_header_path = Path(header_file)
    if not root_header_path.is_absolute():
        root_header_path = resolved_base_dir / root_header_path
    root_header = _normalize_path(root_header_path)

    discovered_headers: list[HeaderFile] = []
    visited_paths: set[Path] = set()

    def _visit(path: Path) -> None:
        resolved_path = _normalize_path(path)

        if _is_within_directory(resolved_path, resolved_base_dir):
            if resolved_path in visited_paths:
                return

            visited_paths.add(resolved_path)
            discovered_headers.append(
                _to_header_file(resolved_path, resolved_base_dir)
            )

        for include_path in _iter_include_paths(resolved_path):
            resolved_include_path = _resolve_include_path(
                include_path=include_path,
                including_file=resolved_path,
                base_dir=resolved_base_dir,
            )
            if resolved_include_path is None:
                continue

            _visit(resolved_include_path)

    _visit(root_header)
    return discovered_headers


def discover_headers(
    base_dir: str | Path,
    *,
    umbrella_header: str | Path | None = None,
) -> HeaderSelection:
    """Build one header selection from a base directory and optional umbrella header."""

    header_files = (
        find_all_headers(base_dir)
        if umbrella_header is None
        else find_included_headers(base_dir, umbrella_header)
    )
    return HeaderSelection(header_files=header_files)


# ==================================================================================================
#     Internal Helpers
# ==================================================================================================


HEADER_EXTENSIONS = frozenset({".h", ".hh", ".hpp", ".hxx", ".h++"})
INCLUDE_RE = re.compile(
    r"""
    ^\s*
    \#\s*include
    \s*
    (?P<open><|")
    (?P<path>[^>"]+)
    (?P<close>>|")
    """,
    re.VERBOSE,
)


def _normalize_path(path: Path) -> Path:
    return path.resolve()


def _is_header_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in HEADER_EXTENSIONS


def _is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _to_header_file(path: Path, base_dir: Path) -> HeaderFile:
    resolved_path = _normalize_path(path)
    return HeaderFile(
        full_path=resolved_path,
        relative_path=resolved_path.relative_to(base_dir),
    )


def _iter_include_paths(header_file: Path) -> Iterable[str]:
    for line in header_file.read_text(encoding="utf-8").splitlines():
        stripped_line = line.lstrip()
        if stripped_line.startswith("//"):
            continue

        match = INCLUDE_RE.match(line)
        if match is None:
            continue

        open_delimiter = match.group("open")
        close_delimiter = match.group("close")
        if (open_delimiter, close_delimiter) not in {("<", ">"), ('"', '"')}:
            continue

        yield match.group("path").strip()


def _resolve_include_path(include_path: str, including_file: Path, base_dir: Path) -> Path | None:
    candidate_paths = (
        including_file.parent / include_path,
        base_dir / include_path,
    )

    for candidate_path in candidate_paths:
        resolved_path = _normalize_path(candidate_path)
        if _is_header_file(resolved_path) and _is_within_directory(resolved_path, base_dir):
            return resolved_path

    return None
