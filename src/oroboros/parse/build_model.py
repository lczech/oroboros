from __future__ import annotations

"""Materialize the semantic model from one parsed clang translation unit."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from ..diagnostics import Diagnostic, DiagnosticReport
from ..model import CppElement, CppModule, NamedCppType
from .config import ParserConfig
from .clang_walk import visit_cursor

if TYPE_CHECKING:
    from .cursor_data import CursorTokenInfo


# ==================================================================================================
#     Build Results
# ==================================================================================================


@dataclass(slots=True)
class BuildContext:
    """Store shared mutable state while walking one translation unit."""

    # ----------
    # Prior input for the build.

    # Active project headers whose declarations should be materialized.
    active_headers: set[Path]
    # All known project headers, including inactive ones, when provided by the caller.
    known_project_headers: set[Path]
    # Parser configuration used while building and resolving the module.
    config: ParserConfig

    # ----------
    # Mutable state accumulated during the build.

    # Internal clang-USR registry for already materialized semantic elements.
    usr_to_element: dict[str, CppElement] = field(default_factory=dict)
    # Token cache grouped by source file for comment recovery and local syntax recovery.
    file_tokens_by_path: dict[Path, list[CursorTokenInfo]] = field(default_factory=dict)
    # Parsed clang translation unit used for token-based comment recovery.
    translation_unit: Any | None = None
    # Deferred named-type declaration links to resolve after the clang walk.
    pending_type_declaration_links: list[PendingTypeDeclarationLink] = field(default_factory=list)

    # ----------
    # Output results accumulated during the build.

    # Structured diagnostics gathered while enriching repeated declarations.
    report: DiagnosticReport = field(default_factory=DiagnosticReport)
    # Counts of unsupported libclang cursor kinds skipped during the walk.
    skipped_kind_counts: Counter[str] = field(default_factory=Counter)


@dataclass(slots=True)
class BuildResult:
    """Store one built semantic module plus parser-side diagnostics."""

    # Semantic module materialized from one clang translation unit.
    module: CppModule
    # Structured diagnostics gathered during the parser-side model build.
    report: DiagnosticReport = field(default_factory=DiagnosticReport)


@dataclass(slots=True)
class PendingTypeDeclarationLink:
    """Store one deferred `NamedCppType` to declaration-USR link to resolve later."""

    cpp_type: NamedCppType
    declaration_usr: str


# ==================================================================================================
#     Public Builder
# ==================================================================================================


def build_module_from_clang(
    translation_unit: Any,
    headers: Sequence[Path],
    config: ParserConfig,
    *,
    known_project_headers: Sequence[Path] | None = None,
) -> BuildResult:
    """Build one semantic module from a parsed clang translation unit."""

    module = CppModule(name="module")
    normalized_headers = [header.resolve() for header in headers]
    normalized_known_project_headers = (
        {header.resolve() for header in known_project_headers}
        if known_project_headers is not None
        else set(normalized_headers)
    )
    module.cpp.header_files.extend(normalized_headers)

    context = BuildContext(
        active_headers={header.resolve() for header in normalized_headers},
        known_project_headers=normalized_known_project_headers,
        config=config,
        translation_unit=translation_unit,
    )
    root_cursor = translation_unit.cursor
    for child_cursor in root_cursor.get_children():
        visit_cursor(child_cursor, module, context)
    _resolve_pending_type_declaration_links(context)
    _record_skipped_cursor_kind_warning(context)

    return BuildResult(
        module=module,
        report=context.report.copy(),
    )


def _resolve_pending_type_declaration_links(context: BuildContext) -> None:
    """Link deferred `NamedCppType` references to already built semantic declarations."""

    for pending_link in context.pending_type_declaration_links:
        if pending_link.cpp_type.declaration is not None:
            continue

        declaration = context.usr_to_element.get(pending_link.declaration_usr)
        if declaration is None:
            continue

        pending_link.cpp_type.declaration = declaration


def _record_skipped_cursor_kind_warning(context: BuildContext) -> None:
    """Summarize unsupported skipped cursor kinds as one parser diagnostic."""

    if not context.skipped_kind_counts:
        return

    rendered_counts = ", ".join(
        f"{kind_name} ({count})"
        for kind_name, count in sorted(context.skipped_kind_counts.items())
    )
    context.report.add(
        Diagnostic(
            severity="warning",
            stage="parse",
            code="parse.skipped_cursor_kinds",
            message=f"Skipped unsupported libclang cursor kinds: {rendered_counts}",
        )
    )
