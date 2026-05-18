from __future__ import annotations

"""Materialize the semantic model from one parsed clang translation unit."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..model import CppElement, CppModule
from .clang_walk import visit_cursor


# ==================================================================================================
#     Build Results
# ==================================================================================================


@dataclass(slots=True)
class ModuleBuildResult:
    """Store one built semantic module plus skipped parser cursor-kind counts."""

    module: CppModule
    skipped_kind_counts: dict[str, int] = field(default_factory=dict)

    @property
    def warnings(self) -> list[str]:
        """Return user-facing parser warnings derived from skipped cursor kinds."""

        if not self.skipped_kind_counts:
            return []

        rendered_counts = ", ".join(
            f"{kind_name} ({count})"
            for kind_name, count in self.skipped_kind_counts.items()
        )
        return [f"Skipped unsupported libclang cursor kinds: {rendered_counts}"]


@dataclass(slots=True)
class ModuleBuildContext:
    """Store shared mutable state while walking one translation unit."""

    active_headers: set[Path]
    usr_to_element: dict[str, CppElement] = field(default_factory=dict)
    skipped_kind_counts: Counter[str] = field(default_factory=Counter)


# ==================================================================================================
#     Public Builder
# ==================================================================================================


def build_module_from_clang(
    translation_unit: Any,
    headers: Sequence[Path],
) -> ModuleBuildResult:
    """Build one semantic module from a parsed clang translation unit."""

    module = CppModule(name="module")
    normalized_headers = [header.resolve() for header in headers]
    module.cpp.header_files.extend(normalized_headers)

    context = ModuleBuildContext(
        active_headers={header.resolve() for header in normalized_headers},
    )
    root_cursor = translation_unit.cursor
    for child_cursor in root_cursor.get_children():
        visit_cursor(child_cursor, module, context)

    return ModuleBuildResult(
        module=module,
        skipped_kind_counts=dict(sorted(context.skipped_kind_counts.items())),
    )
