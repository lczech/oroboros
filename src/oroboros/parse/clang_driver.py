from __future__ import annotations

"""Low-level clang invocation and translation-unit construction for parsing."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..diagnostics import Diagnostic
from ..model import SourceLocation
from .config import ParserConfig
from .toolchain import _resolve_parser_config_toolchain


_SYNTHETIC_FILENAME = "oroboros_synthetic_translation_unit.hpp"


# ==================================================================================================
#     Driver Result
# ==================================================================================================


@dataclass(slots=True)
class ClangDriverResult:
    """Store one parsed clang translation unit plus collected diagnostics."""

    translation_unit: Any
    diagnostics: list[Diagnostic] = field(default_factory=list)
    synthetic_source: str = ""
    synthetic_filename: str = _SYNTHETIC_FILENAME


# ==================================================================================================
#     Public Driver
# ==================================================================================================


def parse_with_clang(
    headers: Sequence[Path],
    config: ParserConfig,
) -> ClangDriverResult:
    """Build one synthetic translation unit that includes the given headers."""

    normalized_headers = [header.resolve() for header in headers]
    synthetic_source = build_synthetic_include_source(normalized_headers)
    resolved_config = _resolve_parser_config_toolchain(config)
    clang_arguments = build_clang_arguments(resolved_config)

    cindex = _load_clang_cindex(resolved_config)
    index = cindex.Index.create()
    translation_unit = index.parse(
        path=_SYNTHETIC_FILENAME,
        args=clang_arguments,
        unsaved_files=[(_SYNTHETIC_FILENAME, synthetic_source)],
    )

    return ClangDriverResult(
        translation_unit=translation_unit,
        diagnostics=_collect_diagnostics(translation_unit.diagnostics),
        synthetic_source=synthetic_source,
        synthetic_filename=_SYNTHETIC_FILENAME,
    )


# ------------------------------------------------------------------------------
#     Synthetic Input
# ------------------------------------------------------------------------------


def build_synthetic_include_source(headers: Sequence[Path]) -> str:
    """Build one synthetic include source that includes all active headers in order."""

    lines = [f'#include "{_normalize_include_path(header)}"' for header in headers]
    if not lines:
        return "\n"
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------
#     Clang Invocation
# ------------------------------------------------------------------------------


def build_clang_arguments(config: ParserConfig) -> list[str]:
    """Translate parser configuration into libclang command-line arguments."""

    arguments: list[str] = []

    arguments.append(f"-x{config.language}")
    arguments.append("-fparse-all-comments")

    if config.cxx_standard is not None:
        arguments.append(f"-std={config.cxx_standard}")

    if config.resource_dir is not None:
        arguments.append(f"-resource-dir={config.resource_dir}")

    arguments.extend(f"-I{include_dir}" for include_dir in config.include_dirs)
    for include_dir in config.system_include_dirs:
        arguments.extend(["-isystem", str(include_dir)])
    arguments.extend(f"-D{define}" for define in config.defines)
    arguments.extend(f"-U{undefine}" for undefine in config.undefines)
    arguments.extend(config.extra_args)
    return arguments


# ==================================================================================================
#     Clang Integration
# ==================================================================================================


def _load_clang_cindex(config: ParserConfig) -> Any:
    """Import clang.cindex and optionally point it at one explicit libclang file."""

    try:
        from clang import cindex
    except ImportError as error:
        raise RuntimeError(
            "libclang Python bindings are not available. Install the 'clang' package "
            "or configure a working Python environment for clang.cindex."
        ) from error

    if config.clang_library_file is not None:
        cindex.Config.set_library_file(str(config.clang_library_file))

    return cindex


# ==================================================================================================
#     Diagnostics
# ==================================================================================================


def _collect_diagnostics(diagnostics: Sequence[Any]) -> list[Diagnostic]:
    """Convert libclang diagnostics into small public diagnostic value objects."""

    return [_convert_diagnostic(diagnostic) for diagnostic in diagnostics]


def _convert_diagnostic(diagnostic: Any) -> Diagnostic:
    """Convert one libclang diagnostic into the public result representation."""

    location = _convert_source_location(getattr(diagnostic, "location", None))
    return Diagnostic(
        severity=_normalize_diagnostic_severity(getattr(diagnostic, "severity", None)),
        stage="clang",
        code="clang.diagnostic",
        message=str(diagnostic.spelling),
        locations=[] if location is None else [location],
    )


def _convert_source_location(location: Any) -> SourceLocation | None:
    """Convert one libclang source location into the semantic-model value object."""

    if location is None:
        return None

    file_object = getattr(location, "file", None)
    if file_object is None:
        return None

    file_name = getattr(file_object, "name", None)
    if file_name is None:
        return None

    return SourceLocation(
        file=Path(file_name).resolve(),
        line=int(getattr(location, "line", 0)),
        column=int(getattr(location, "column", 0)),
    )


def _normalize_diagnostic_severity(severity: Any) -> str:
    """Map one libclang severity value to the public string form."""

    severity_map = {
        1: "note",
        2: "warning",
        3: "error",
        4: "fatal",
    }
    return severity_map.get(severity, "warning")


# ------------------------------------------------------------------------------
#     Path Rendering
# ------------------------------------------------------------------------------


def _normalize_include_path(path: Path) -> str:
    """Render one include path in a stable forward-slash form for clang."""

    return str(path.resolve()).replace("\\", "/")
