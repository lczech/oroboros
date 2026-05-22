from __future__ import annotations

"""Configuration values used when parsing headers with clang."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(slots=True)
class ParserConfig:
    """Store clang invocation and parser behavior settings."""

    # ------------------------------------------------------------------------------
    #     Project Inputs
    # ------------------------------------------------------------------------------

    # Include directories forwarded to clang via `-I...`.
    include_dirs: list[Path] = field(default_factory=list)
    # Preprocessor definitions forwarded to clang via `-D...`.
    defines: list[str] = field(default_factory=list)
    # Preprocessor undefines forwarded to clang via `-U...`.
    undefines: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------------------
    #     Compiler And Toolchain
    # ------------------------------------------------------------------------------

    # Language mode passed to clang via `-x...`.
    language: str = "c++"
    # Optional C++ language standard such as `c++17` or `c++20`.
    cxx_standard: str | None = None
    # Extra raw command-line arguments passed through to clang.
    extra_args: list[str] = field(default_factory=list)

    # Whether to probe `toolchain_compiler` for builtin clang settings.
    # When enabled, Oroboros fills `resource_dir` and, if still empty,
    # `system_include_dirs` from that compiler's reported defaults.
    auto_detect_toolchain: bool = True
    # Compiler executable queried when `auto_detect_toolchain` is enabled.
    toolchain_compiler: str = "clang++"

    # Optional explicit clang builtin header resource directory.
    # If unset and `auto_detect_toolchain=True`, this is filled from
    # `toolchain_compiler -print-resource-dir`.
    resource_dir: Path | None = None
    # System include directories forwarded to clang via `-isystem ...`.
    # If this list is empty and `auto_detect_toolchain=True`, Oroboros fills it
    # from the compiler's verbose include-search output.
    system_include_dirs: list[Path] = field(default_factory=list)
    # Optional explicit path to the libclang shared library file.
    clang_library_file: Path | None = None

    # ------------------------------------------------------------------------------
    #     Parser Behavior
    # ------------------------------------------------------------------------------

    # How to resolve conflicting comment text across repeated declarations.
    comment_conflict_policy: Literal["longer", "first", "last", "append"] = "longer"
    # Whether to validate the resulting semantic model before returning it.
    validate_model: bool = True
