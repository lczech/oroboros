from __future__ import annotations

"""Alias semantic model objects and helpers."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from .availability import CppAvailability
from .comment import CppDoc, PyDoc
from .element import CppElement
from .location import CppLocationInfo
from .type import CppType, NamedCppType, cpp_types_equivalent
from .visibility import CppVisibility

if TYPE_CHECKING:
    from .class_ import CppClass


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppAliasCppFacet:
    """Store parsed C++ details for one alias or typedef declaration."""

    original_name: str | None = None
    target: CppType | None = None
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    comment: str | None = None
    doc: CppDoc | None = None
    availability: CppAvailability | None = None
    visibility: CppVisibility | None = None
    kind: Literal["using", "typedef"] | None = None


@dataclass(slots=True)
class CppAliasBindFacet:
    """Store binding settings for one alias declaration."""

    active: bool | None = None


@dataclass(slots=True)
class CppAliasPyFacet:
    """Store Python-facing choices for one alias declaration."""

    name: str | None = None
    doc: PyDoc | None = None


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppAlias(CppElement):
    """Represent one alias or typedef declaration in the semantic tree."""

    cpp: CppAliasCppFacet = field(default_factory=CppAliasCppFacet)
    bind: CppAliasBindFacet = field(default_factory=CppAliasBindFacet)
    py: CppAliasPyFacet = field(default_factory=CppAliasPyFacet)


# ==================================================================================================
#     Lookup
# ==================================================================================================


def find_aliases(
    scope: CppElement,
    target: CppType | CppClass,
) -> list[CppAlias]:
    """Find alias declarations in one subtree that target one class or type."""

    from .lookup import _iter_subtree

    target_names = _target_names(target)
    aliases: list[CppAlias] = []

    for element in _iter_subtree(scope):
        if not isinstance(element, CppAlias):
            continue
        alias_target = element.cpp.target
        if alias_target is None:
            continue
        if _alias_target_matches(alias_target, target, target_names):
            aliases.append(element)

    return aliases


def _target_names(target: CppType | CppClass) -> set[str]:
    """Collect declaration names that may identify one aliased class target."""

    if isinstance(target, CppType):
        return set()

    names: set[str] = {target.qualified_name, target.name}
    if target.cpp.original_name is not None:
        names.add(target.cpp.original_name)
    return names


def _alias_target_matches(
    alias_target: CppType,
    target: CppType | CppClass,
    target_names: set[str],
) -> bool:
    """Check whether one alias target refers to the requested class or type."""

    if isinstance(target, CppType):
        return cpp_types_equivalent(alias_target, target)

    return _type_refers_to_class(alias_target, target, target_names)


def _type_refers_to_class(
    cpp_type: CppType,
    target: CppClass,
    target_names: set[str],
    *,
    visited_alias_ids: set[int] | None = None,
) -> bool:
    """Check whether one type value names one concrete class declaration."""

    if visited_alias_ids is None:
        visited_alias_ids = set()

    if isinstance(cpp_type, NamedCppType):
        declaration = cpp_type.declaration
        if declaration is not None:
            if declaration.qualified_name == target.qualified_name:
                return True
            if isinstance(declaration, CppAlias):
                alias_id = id(declaration)
                if alias_id in visited_alias_ids:
                    return False
                if declaration.cpp.target is not None and _type_refers_to_class(
                    declaration.cpp.target,
                    target,
                    target_names,
                    visited_alias_ids=visited_alias_ids | {alias_id},
                ):
                    return True
        if cpp_type.name in target_names:
            return True
        if cpp_type.canonical is not None:
            return _type_refers_to_class(
                cpp_type.canonical,
                target,
                target_names,
                visited_alias_ids=visited_alias_ids,
            )
    return False
