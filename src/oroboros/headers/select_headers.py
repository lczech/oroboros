from __future__ import annotations

"""Select active headers from a discovered project header list.

This module takes the header inventory found by ``find_headers`` and applies a
user-maintained activation header on top of it. The activation header is a
normal-looking C++ header file whose ``#include`` lines can be commented or
uncommented to disable or enable individual project headers.

It also provides helpers to write or update such activation headers. This lets
users grow bindings incrementally: newly discovered headers can be added to the
activation file automatically, while existing user choices are preserved.
"""

from dataclasses import dataclass, replace
from pathlib import Path
import re
import sys
from typing import TextIO
import warnings

from .model import HeaderFile, HeaderSelection


INCLUDE_RE = re.compile(
    r"""
    ^\s*
    (?P<comment>//\s*)?
    \#\s*include
    \s*
    (?P<open><|")
    (?P<path>[^>"]+)
    (?P<close>>|")
    (?:\s*//.*)?
    \s*$
    """,
    re.VERBOSE,
)


def _normalize_header_path(path: str) -> str:
    return path.replace("\\", "/").strip()


@dataclass(frozen=True, slots=True)
class ActivationHeaderUpdateResult:
    """Describe how an activation header changed during an update."""

    activation_header: Path
    header_files: list[HeaderFile]
    added_headers: list[Path]
    removed_headers: list[Path]
    created_file: bool
    updated_file: bool


def _read_activation_map(activation_header: str | Path) -> dict[str, bool]:
    activation_path = Path(activation_header)
    activation_map: dict[str, bool] = {}

    for line in activation_path.read_text(encoding="utf-8").splitlines():
        match = INCLUDE_RE.match(line)
        if match is None:
            continue

        open_delimiter = match.group("open")
        close_delimiter = match.group("close")
        if (open_delimiter, close_delimiter) not in {("<", ">"), ('"', '"')}:
            continue

        include_path = _normalize_header_path(match.group("path"))
        activation_map[include_path] = match.group("comment") is None

    return activation_map


def parse_activation_header(
    header_files: list[HeaderFile],
    activation_header: str | Path,
) -> list[HeaderFile]:
    """Apply active and inactive selections from an activation header file."""

    activation_map = _read_activation_map(activation_header)

    missing_headers = [
        header_file.relative_path.as_posix()
        for header_file in header_files
        if header_file.relative_path.as_posix() not in activation_map
    ]
    if missing_headers:
        warnings.warn(
            "Headers missing from activation header: " + ", ".join(missing_headers),
            stacklevel=2,
        )

    selected_headers = [
        replace(
            header_file,
            active=activation_map.get(header_file.relative_path.as_posix(), False),
        )
        for header_file in header_files
    ]
    return selected_headers


def select_active_headers(
    selection: HeaderSelection,
    activation_header: str | Path,
) -> HeaderSelection:
    """Apply one activation header to a known project-header selection."""

    return HeaderSelection(
        header_files=parse_activation_header(selection.known_headers, activation_header),
    )


def _render_activation_header(
    header_files: list[HeaderFile],
    *,
    with_sections: bool = False,
) -> str:
    """Render one activation header file without writing it yet."""

    lines = ["#pragma once", ""]
    current_directory: str | None = None

    for header_file in header_files:
        header_directory = header_file.relative_path.parent.as_posix()

        if with_sections and header_directory != current_directory:
            if len(lines) > 2:
                lines.append("")

            section_name = header_directory if header_directory != "." else "(root)"
            lines.extend(
                [
                    "// ---------------------------------------------------------------------",
                    f"//   {section_name}",
                    "// ---------------------------------------------------------------------",
                    "",
                ]
            )
            current_directory = header_directory

        include_line = f'#include <{header_file.relative_path.as_posix()}>'
        if not header_file.active:
            include_line = f"// {include_line}"
        lines.append(include_line)

    return "\n".join(lines) + "\n"


def write_activation_header(
    header_files: list[HeaderFile],
    target_file: str | Path,
    *,
    with_sections: bool = False,
) -> None:
    """Write a C++ activation header file from a discovered header list."""

    target_path = Path(target_file)
    rendered_text = _render_activation_header(
        header_files,
        with_sections=with_sections,
    )
    target_path.write_text(rendered_text, encoding="utf-8")


def update_activation_header(
    header_files: list[HeaderFile],
    target_file: str | Path,
    *,
    with_sections: bool = False,
    default_active: bool = False,
) -> ActivationHeaderUpdateResult:
    """Update an activation header while preserving existing user selections."""

    target_path = Path(target_file)
    created_file = not target_path.exists()

    existing_activation_map = (
        _read_activation_map(target_path)
        if target_path.exists()
        else {}
    )
    inventory_paths = [header_file.relative_path for header_file in header_files]
    inventory_path_strings = {path.as_posix() for path in inventory_paths}
    existing_path_strings = set(existing_activation_map)

    added_headers = [
        path for path in inventory_paths
        if path.as_posix() not in existing_path_strings
    ]
    removed_headers = [
        Path(path_string) for path_string in existing_activation_map
        if path_string not in inventory_path_strings
    ]

    selected_headers = [
        replace(
            header_file,
            active=existing_activation_map.get(
                header_file.relative_path.as_posix(),
                default_active,
            ),
        )
        for header_file in header_files
    ]

    previous_content = target_path.read_text(encoding="utf-8") if target_path.exists() else None
    updated_content = _render_activation_header(
        selected_headers,
        with_sections=with_sections,
    )
    updated_file = previous_content != updated_content
    if updated_file:
        target_path.write_text(updated_content, encoding="utf-8")

    return ActivationHeaderUpdateResult(
        activation_header=target_path,
        header_files=selected_headers,
        added_headers=added_headers,
        removed_headers=removed_headers,
        created_file=created_file,
        updated_file=updated_file,
    )


def print_update_report(
    update_result: ActivationHeaderUpdateResult,
    *,
    stream: TextIO | None = None,
) -> None:
    """Print a concise human-readable summary of an activation header update."""

    output_stream = stream if stream is not None else sys.stdout
    summary = (
        f"Activation header: {update_result.activation_header} "
        f"(created={update_result.created_file}, updated={update_result.updated_file})"
    )
    print(summary, file=output_stream)

    if update_result.added_headers:
        print("Added headers:", file=output_stream)
        for header_path in update_result.added_headers:
            print(f"  {header_path.as_posix()}", file=output_stream)

    if update_result.removed_headers:
        print("Removed headers:", file=output_stream)
        for header_path in update_result.removed_headers:
            print(f"  {header_path.as_posix()}", file=output_stream)

    if not update_result.added_headers and not update_result.removed_headers:
        print("No header list changes.", file=output_stream)
