from __future__ import annotations

"""Helpers for discovering clang-compatible system include settings."""

from dataclasses import dataclass, field, replace
from pathlib import Path
import subprocess

from .config import ParserConfig


# ==================================================================================================
#     Toolchain Data
# ==================================================================================================


@dataclass(slots=True)
class CompilerToolchain:
    """Store compiler-derived include and resource settings for the parser."""

    resource_dir: Path | None = None
    system_include_dirs: list[Path] = field(default_factory=list)


# ==================================================================================================
#     Public Toolchain Detection
# ==================================================================================================


def detect_compiler_toolchain(
    compiler: str = "clang++",
    *,
    language: str = "c++",
) -> CompilerToolchain:
    """Detect the resource directory and system include paths for one compiler."""

    try:
        resource_dir = _detect_resource_dir(compiler)
        include_output = _run_compiler_include_probe(compiler, language=language)
    except FileNotFoundError as error:
        raise RuntimeError(
            "Toolchain autodetection is enabled, but the compiler "
            f"{compiler!r} was not found. Install that compiler, point "
            "`toolchain_compiler` at a working compiler executable, or disable "
            "`auto_detect_toolchain` and set `resource_dir` plus "
            "`system_include_dirs` manually."
        ) from error
    except (OSError, subprocess.CalledProcessError) as error:
        details = _format_subprocess_error(error)
        raise RuntimeError(
            "Failed to detect parser toolchain settings from compiler "
            f"{compiler!r}.{details} Disable `auto_detect_toolchain` and set "
            "`resource_dir` plus `system_include_dirs` manually if needed."
        ) from error

    system_include_dirs = _parse_system_include_dirs(include_output)
    return CompilerToolchain(
        resource_dir=resource_dir,
        system_include_dirs=system_include_dirs,
    )


# ==================================================================================================
#     Parser Config Resolution
# ==================================================================================================


def _resolve_parser_config_toolchain(
    config: ParserConfig,
) -> ParserConfig:
    """Return one parser config with optional auto-detected toolchain settings."""

    updated_config = replace(config)

    if not updated_config.auto_detect_toolchain:
        return updated_config

    needs_resource_dir = updated_config.resource_dir is None
    needs_system_includes = not updated_config.system_include_dirs
    if not needs_resource_dir and not needs_system_includes:
        return updated_config

    toolchain = detect_compiler_toolchain(
        updated_config.toolchain_compiler,
        language=updated_config.language,
    )

    if updated_config.resource_dir is None:
        updated_config.resource_dir = toolchain.resource_dir

    if not updated_config.system_include_dirs:
        updated_config.system_include_dirs = list(toolchain.system_include_dirs)

    return updated_config


# ==================================================================================================
#     Compiler Probes
# ==================================================================================================


def _detect_resource_dir(compiler: str) -> Path | None:
    """Ask one compiler for its clang builtin header resource directory."""

    completed_process = subprocess.run(
        [compiler, "-print-resource-dir"],
        check=True,
        capture_output=True,
        text=True,
    )
    output = completed_process.stdout.strip()
    if not output:
        return None
    return Path(output).resolve()


def _run_compiler_include_probe(compiler: str, *, language: str) -> str:
    """Run one compiler preprocessor probe and return its verbose search output."""

    completed_process = subprocess.run(
        [compiler, "-x", language, "-E", "-v", "-"],
        check=True,
        input="",
        capture_output=True,
        text=True,
    )
    return completed_process.stderr


# ==================================================================================================
#     Probe Output Parsing
# ==================================================================================================


def _parse_system_include_dirs(verbose_output: str) -> list[Path]:
    """Parse one compiler `-E -v` output block into system include directories."""

    start_marker = "#include <...> search starts here:"
    end_marker = "End of search list."

    lines = verbose_output.splitlines()
    include_lines: list[str] = []
    collecting = False

    for line in lines:
        stripped_line = line.strip()
        if stripped_line == start_marker:
            collecting = True
            continue
        if stripped_line == end_marker:
            break
        if collecting:
            include_lines.append(stripped_line)

    include_dirs: list[Path] = []
    seen_paths: set[Path] = set()
    for line in include_lines:
        if not line or line.startswith("(") or line.startswith("ignoring "):
            continue

        include_dir = Path(line).resolve()
        if include_dir in seen_paths:
            continue
        seen_paths.add(include_dir)
        include_dirs.append(include_dir)

    return include_dirs


# ==================================================================================================
#     Error Reporting
# ==================================================================================================


def _format_subprocess_error(error: OSError | subprocess.CalledProcessError) -> str:
    """Render one compiler-probing failure into a short message fragment."""

    if isinstance(error, subprocess.CalledProcessError):
        stderr = (error.stderr or "").strip()
        stdout = (error.stdout or "").strip()
        output = stderr or stdout
        if output:
            first_line = output.splitlines()[0].strip()
            return f" First compiler message: {first_line}"
        return ""

    message = str(error).strip()
    if not message:
        return ""
    return f" {message}"
