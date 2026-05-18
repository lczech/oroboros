from __future__ import annotations

"""Lookup helpers for finding semantic model elements inside one subtree."""

from dataclasses import fields as dataclass_fields
from typing import Iterator

from .element import CppElement


# ==================================================================================================
#     Errors
# ==================================================================================================


class ModelLookupError(LookupError):
    """Report failed or ambiguous semantic-model lookup operations."""


# ==================================================================================================
#     Public Lookup
# ==================================================================================================


def find_all_by_qualified_name(
    scope: CppElement,
    qualified_name: str,
    *,
    types: type[CppElement] | tuple[type[CppElement], ...] | None = None,
) -> list[CppElement]:
    """Find all elements in one subtree with one semantic qualified name."""

    normalized_name = _normalize_qualified_name(qualified_name)
    return [
        element
        for element in _iter_subtree(scope)
        if _matches_type(element, types) and element.qualified_name == normalized_name
    ]


def find_one_by_qualified_name(
    scope: CppElement,
    qualified_name: str,
    *,
    types: type[CppElement] | tuple[type[CppElement], ...] | None = None,
) -> CppElement:
    """Find exactly one element in one subtree with one semantic qualified name."""

    normalized_name = _normalize_qualified_name(qualified_name)
    matches = find_all_by_qualified_name(scope, normalized_name, types=types)
    return _require_one_match(
        scope,
        matches,
        query_description=f"qualified name {normalized_name!r}",
        types=types,
    )


def find_all_by_name(
    scope: CppElement,
    name: str,
    *,
    types: type[CppElement] | tuple[type[CppElement], ...] | None = None,
) -> list[CppElement]:
    """Find all elements in one subtree with one unqualified semantic name."""

    return [
        element
        for element in _iter_subtree(scope)
        if _matches_type(element, types) and element.name == name
    ]


def find_one_by_name(
    scope: CppElement,
    name: str,
    *,
    types: type[CppElement] | tuple[type[CppElement], ...] | None = None,
) -> CppElement:
    """Find exactly one element in one subtree with one unqualified semantic name."""

    matches = find_all_by_name(scope, name, types=types)
    return _require_one_match(
        scope,
        matches,
        query_description=f"name {name!r}",
        types=types,
    )


# ==================================================================================================
#     Internal Helpers
# ==================================================================================================


def _iter_subtree(scope: CppElement) -> Iterator[CppElement]:
    """Yield one node followed by all descendants reachable from it."""

    yield scope

    for _, child in _iter_direct_child_nodes(scope, scope._describe_node()):
        yield from _iter_subtree(child)


def _iter_direct_child_nodes(
    node: CppElement,
    path: str,
    errors: list[str] | None = None,
) -> list[tuple[str, CppElement]]:
    """Collect direct child element references declared on one node."""

    children: list[tuple[str, CppElement]] = []

    for dataclass_field in dataclass_fields(node):
        field_name = dataclass_field.name
        if field_name == "owner":
            continue

        value = getattr(node, field_name)
        if isinstance(value, CppElement):
            children.append((f"{path}.{field_name}", value))
            continue

        if isinstance(value, list):
            for index, item in enumerate(value):
                item_path = f"{path}.{field_name}[{index}]"
                if isinstance(item, CppElement):
                    children.append((item_path, item))
                    continue
                if errors is not None:
                    errors.append(
                        f"{item_path} contains {type(item).__name__}, expected a CppElement."
                    )

    return children


def _normalize_qualified_name(qualified_name: str) -> str:
    """Normalize one user-facing qualified-name query for semantic lookup."""

    normalized_name = qualified_name.strip()
    while normalized_name.startswith("::"):
        normalized_name = normalized_name[2:]
    return normalized_name


def _matches_type(
    element: CppElement,
    types: type[CppElement] | tuple[type[CppElement], ...] | None,
) -> bool:
    """Return whether one element matches one optional type filter."""

    if types is None:
        return True
    return isinstance(element, types)


def _require_one_match(
    scope: CppElement,
    matches: list[CppElement],
    *,
    query_description: str,
    types: type[CppElement] | tuple[type[CppElement], ...] | None,
) -> CppElement:
    """Return the only lookup match or raise a descriptive lookup error."""

    if len(matches) == 1:
        return matches[0]

    type_description = _describe_types(types)
    scope_description = scope._describe_node()

    if not matches:
        raise ModelLookupError(
            f"No element with {query_description} was found under {scope_description}{type_description}."
        )

    match_descriptions = ", ".join(
        f"{type(match).__name__}({match.qualified_name!r})"
        for match in matches
    )
    raise ModelLookupError(
        f"Expected exactly one element with {query_description} under {scope_description}"
        f"{type_description}, but found {len(matches)}: {match_descriptions}."
    )


def _describe_types(
    types: type[CppElement] | tuple[type[CppElement], ...] | None,
) -> str:
    """Render one optional lookup type filter into a short message suffix."""

    if types is None:
        return ""
    if isinstance(types, tuple):
        type_names = ", ".join(type_.__name__ for type_ in types)
        return f" matching ({type_names})"
    return f" matching {types.__name__}"
