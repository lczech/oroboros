from __future__ import annotations

"""Materialize the semantic model from one parsed clang translation unit."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..model import CppElement, CppModule, NamedCppType
from .config import ParserConfig
from .clang_walk import visit_cursor


# ==================================================================================================
#     Build Results
# ==================================================================================================


@dataclass(slots=True)
class BuildResult:
    """Store one built semantic module plus skipped parser cursor-kind counts."""

    module: CppModule
    semantic_warnings: list[str] = field(default_factory=list)
    skipped_kind_counts: dict[str, int] = field(default_factory=dict)

    @property
    def warnings(self) -> list[str]:
        """Return user-facing parser warnings derived from skipped cursor kinds."""

        warnings = list(self.semantic_warnings)
        if not self.skipped_kind_counts:
            return warnings

        rendered_counts = ", ".join(
            f"{kind_name} ({count})"
            for kind_name, count in self.skipped_kind_counts.items()
        )
        warnings.append(f"Skipped unsupported libclang cursor kinds: {rendered_counts}")
        return warnings


@dataclass(slots=True)
class PendingTypeDeclarationLink:
    """Store one deferred `NamedCppType` to declaration-USR link to resolve later."""

    cpp_type: NamedCppType
    declaration_usr: str


@dataclass(slots=True)
class BuildContext:
    """Store shared mutable state while walking one translation unit."""

    # Active project headers whose declarations should be materialized.
    active_headers: set[Path]
    # Parser configuration used while building and resolving the module.
    config: ParserConfig
    # Internal clang-USR registry for already materialized semantic elements.
    usr_to_element: dict[str, CppElement] = field(default_factory=dict)
    # Deferred named-type declaration links to resolve after the clang walk.
    pending_type_declaration_links: list[PendingTypeDeclarationLink] = field(default_factory=list)
    # User-facing semantic warnings gathered while enriching repeated declarations.
    semantic_warnings: list[str] = field(default_factory=list)
    # Counts of unsupported libclang cursor kinds skipped during the walk.
    skipped_kind_counts: Counter[str] = field(default_factory=Counter)


# ==================================================================================================
#     Public Builder
# ==================================================================================================


def build_module_from_clang(
    translation_unit: Any,
    headers: Sequence[Path],
    config: ParserConfig,
) -> BuildResult:
    """Build one semantic module from a parsed clang translation unit."""

    module = CppModule(name="module")
    normalized_headers = [header.resolve() for header in headers]
    module.cpp.header_files.extend(normalized_headers)

    context = BuildContext(
        active_headers={header.resolve() for header in normalized_headers},
        config=config,
    )
    root_cursor = translation_unit.cursor
    for child_cursor in root_cursor.get_children():
        visit_cursor(child_cursor, module, context)
    _resolve_pending_type_declaration_links(context)

    return BuildResult(
        module=module,
        semantic_warnings=list(context.semantic_warnings),
        skipped_kind_counts=dict(sorted(context.skipped_kind_counts.items())),
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
