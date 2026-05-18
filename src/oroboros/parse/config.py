from __future__ import annotations

"""Configuration values used when parsing headers with clang."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ParserConfig:
    """Store clang invocation and parser behavior settings."""

    # Include directories forwarded to clang via `-I...`.
    include_dirs: list[Path] = field(default_factory=list)
    # Preprocessor definitions forwarded to clang via `-D...`.
    defines: list[str] = field(default_factory=list)
    # Preprocessor undefines forwarded to clang via `-U...`.
    undefines: list[str] = field(default_factory=list)
    # Extra raw command-line arguments passed through to clang.
    extra_args: list[str] = field(default_factory=list)
    # Optional C++ language standard such as `c++17` or `c++20`.
    cxx_standard: str | None = None
    # Optional explicit path to the libclang shared library file.
    clang_library_file: Path | None = None
    # Whether to ask clang to parse comments beyond documentation commands.
    parse_all_comments: bool = True
    # Whether to validate the resulting semantic model before returning it.
    validate_model: bool = True
