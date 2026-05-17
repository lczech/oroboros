from __future__ import annotations

"""Lightweight alias metadata for semantic model scopes."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .comment import CppDoc
from .location import SourceLocation
from .type import CppType
from .visibility import CppVisibility

if TYPE_CHECKING:
    from .class_ import CppClass
    from .element import CppElement
    from .template_ import CppClassTemplate


# ==================================================================================================
#     Alias Info
# ==================================================================================================


@dataclass(slots=True)
class CppAliasInfo:
    """Store one scoped alias or typedef as lightweight C++ metadata."""

    name: str
    qualified_name: str | None = None
    target: CppType | None = None
    location: SourceLocation | None = None
    comment: str | None = None
    doc: CppDoc | None = None
    visibility: CppVisibility | None = None
    kind: Literal["using", "typedef"] | None = None


# ==================================================================================================
#     Lookup
# ==================================================================================================


def find_aliases(
    scope: CppElement,
    target: CppType | CppClass,
) -> list[CppAliasInfo]:
    """Find aliases for one type or class across one semantic subtree."""

    target_names = _target_names(target)
    aliases: list[CppAliasInfo] = []

    for nested_scope in _iter_alias_scopes(scope):
        cpp_facet = getattr(nested_scope, "cpp", None)
        if cpp_facet is None:
            continue
        for alias in getattr(cpp_facet, "aliases", []):
            if alias.target is None:
                continue
            if alias.target.render() in target_names:
                aliases.append(alias)

    return aliases


def _target_names(target: CppType | CppClass) -> set[str]:
    """Collect the rendered names that may identify one aliased target."""

    if isinstance(target, CppType):
        return {target.render()}

    names: set[str] = {target.qualified_name, target.name}
    if target.cpp.original_name is not None:
        names.add(target.cpp.original_name)
    return names


def _iter_alias_scopes(scope: CppElement) -> list[CppElement]:
    """Collect scopes whose `.cpp` facet can contain alias metadata."""

    scopes: list["CppElement"] = [scope]

    for namespaces in [getattr(scope, "namespaces", [])]:
        for namespace in namespaces:
            scopes.extend(_iter_alias_scopes(namespace))

    for classes in [getattr(scope, "classes", [])]:
        for cls in classes:
            scopes.extend(_iter_alias_scopes(cls))

    class_templates = getattr(scope, "class_templates", [])
    for template in class_templates:
        scopes.extend(_iter_class_template_alias_scopes(template))

    return scopes


def _iter_class_template_alias_scopes(template: CppClassTemplate) -> list[CppElement]:
    """Collect alias-bearing scopes reachable from one class template family."""

    declaration = getattr(template, "declaration", None)
    if declaration is None:
        return []
    return _iter_alias_scopes(declaration)
