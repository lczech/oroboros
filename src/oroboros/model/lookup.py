from __future__ import annotations

"""Lookup helpers for finding semantic model elements inside one subtree."""

from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Generic, Iterator, TypeVar

from .element import CppElement


ElementT = TypeVar("ElementT", bound=CppElement)


# ==================================================================================================
#     Errors
# ==================================================================================================


class ModelLookupError(LookupError):
    """Report failed or ambiguous semantic-model lookup operations."""


# ==================================================================================================
#     Find Functions
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


def find(
    scope: CppElement,
    query: str,
    *,
    types: type[CppElement] | tuple[type[CppElement], ...] | None = None,
) -> CppElement:
    """Find exactly one element by either qualified or unqualified semantic name."""

    if "::" in query:
        return find_one_by_qualified_name(scope, query, types=types)
    return find_one_by_name(scope, query, types=types)


def find_all(
    scope: CppElement,
    query: str,
    *,
    types: type[CppElement] | tuple[type[CppElement], ...] | None = None,
) -> list[CppElement]:
    """Find all elements by either qualified or unqualified semantic name."""

    if "::" in query:
        return find_all_by_qualified_name(scope, query, types=types)
    return find_all_by_name(scope, query, types=types)


def find_direct_child(
    scope: CppElement,
    name: str,
) -> CppElement | list[CppElement]:
    """Find one direct child by semantic name across all immediate child collections."""

    matches = [
        child
        for _, child in _iter_direct_child_elements(scope, scope._describe_element())
        if child.name == name
    ]
    if not matches:
        raise ModelLookupError(
            f"No direct child named {name!r} exists under {scope._describe_element()}."
        )

    if len(matches) == 1:
        return matches[0]

    if _all_overloadable(matches):
        return matches

    return _require_one_match(
        scope,
        matches,
        query_description=f"direct child name {name!r}",
        types=None,
    )


def direct_child_names(scope: CppElement) -> list[str]:
    """Return the unique names of all direct child declarations under one scope."""

    return list(
        dict.fromkeys(
            child.name
            for _, child in _iter_direct_child_elements(scope, scope._describe_element())
        )
    )


# ==================================================================================================
#     Name Views
# ==================================================================================================


def make_named_child_view(
    owner: CppElement,
    container: object,
    field_name: str,
    *,
    return_many: bool = False,
) -> NamedChildView[CppElement]:
    """Create one name-indexed view over one owned child collection."""

    return NamedChildView(owner, container, field_name, return_many=return_many)


class NamedChildView(Generic[ElementT]):
    """Provide lightweight name-indexed access over one owned child collection."""

    def __init__(
        self,
        owner: CppElement,
        container: object,
        field_name: str,
        *,
        return_many: bool = False,
    ) -> None:
        self._owner = owner
        self._container = container
        self._field_name = field_name
        self._return_many = return_many

    def __getitem__(self, name: str) -> ElementT | list[ElementT]:
        """Return one child by name, or all overloads when configured to do so."""

        matches = self._matches_for_name(name)
        if self._return_many:
            if not matches:
                raise ModelLookupError(
                    f"No child named {name!r} exists in {self._owner._describe_element()}.{self._field_name}."
                )
            return matches

        return _require_one_match(
            self._owner,
            matches,
            query_description=f"{self._field_name.rstrip('s')} name {name!r}",
            types=None,
        )

    def __contains__(self, name: object) -> bool:
        """Return whether the owned collection contains at least one child by this name."""

        if not isinstance(name, str):
            return False
        return bool(self._matches_for_name(name))

    def keys(self) -> list[str]:
        """Return the unique child names present in this view."""

        return list(dict.fromkeys(child.name for child in self._items()))

    def _items(self) -> list[ElementT]:
        """Return the underlying owned child list."""

        value = getattr(self._container, self._field_name, None)
        if isinstance(value, list):
            return list(value)
        return []

    def _matches_for_name(self, name: str) -> list[ElementT]:
        """Return all child elements whose semantic name matches exactly."""

        return [
            child
            for child in self._items()
            if child.name == name
        ]


# ==================================================================================================
#     Internal Helpers
# ==================================================================================================


def _iter_subtree(scope: CppElement) -> Iterator[CppElement]:
    """Yield one element followed by all descendants reachable from it."""

    yield scope

    for _, child in _iter_direct_child_elements(scope, scope._describe_element()):
        yield from _iter_subtree(child)


def _iter_direct_child_elements(
    element: CppElement,
    path: str,
    errors: list[str] | None = None,
) -> list[tuple[str, CppElement]]:
    """Collect direct child element references declared on one element."""

    return _collect_direct_child_elements(
        element,
        path,
        errors=errors,
        skip_owner=True,
        path_owner=element,
    )


def _collect_direct_child_elements(
    value: object,
    path: str,
    *,
    errors: list[str] | None,
    skip_owner: bool,
    path_owner: CppElement | None,
) -> list[tuple[str, CppElement]]:
    """Collect direct child elements reachable from one dataclass-backed value."""

    children: list[tuple[str, CppElement]] = []

    if not is_dataclass(value) or isinstance(value, type):
        return children

    for dataclass_field in dataclass_fields(value):
        field_name = dataclass_field.name
        if skip_owner and field_name == "owner":
            continue

        field_value = getattr(value, field_name)
        field_path = f"{path}.{field_name}"
        if isinstance(field_value, CppElement):
            children.append((field_path, field_value))
            continue

        if isinstance(field_value, list):
            element_items = [
                item
                for item in field_value
                if isinstance(item, CppElement)
            ]
            for index, item in enumerate(field_value):
                if isinstance(item, CppElement):
                    item_path = _child_element_path(
                        parent_path=path,
                        parent_value=value,
                        path_owner=path_owner,
                        field_name=field_name,
                        siblings=element_items,
                        index=index,
                        item=item,
                    )
                    children.append((item_path, item))
                    continue
                item_path = f"{field_path}[{index}]"
                if errors is not None:
                    errors.append(
                        f"{item_path} contains {type(item).__name__}, expected a CppElement."
                    )
            continue

        if is_dataclass(field_value) and getattr(field_value, "_is_child_container", False):
            children.extend(
                _collect_direct_child_elements(
                    field_value,
                    path,
                    errors=errors,
                    skip_owner=False,
                    path_owner=path_owner,
                )
            )

    return children


def _child_element_path(
    *,
    parent_path: str,
    parent_value: object,
    path_owner: CppElement | None,
    field_name: str,
    siblings: list[CppElement],
    index: int,
    item: CppElement,
) -> str:
    """Render one stable user-facing path for a child element inside one list field."""

    raw_collection_path = _raw_child_collection_path(
        parent_path=parent_path,
        parent_value=parent_value,
        field_name=field_name,
    )
    name = getattr(item, "name", None)
    if not name:
        return f"{raw_collection_path}[{index}]"

    semantic_collection_path = _semantic_child_collection_path(
        parent_path=parent_path,
        path_owner=path_owner,
        field_name=field_name,
    )
    if semantic_collection_path is None:
        return f"{raw_collection_path}[{index}]"

    if _child_view_returns_many(field_name):
        overload_index = _same_name_sibling_index(siblings, name, item)
        return f'{semantic_collection_path}["{name}"][{overload_index}]'

    duplicate_count = sum(1 for sibling in siblings if sibling.name == name)
    if duplicate_count == 1:
        return f'{semantic_collection_path}["{name}"]'

    return f"{raw_collection_path}[{index}]"


def _semantic_child_collection_path(
    *,
    parent_path: str,
    path_owner: CppElement | None,
    field_name: str,
) -> str | None:
    """Return one semantic-access path for a direct child collection when available."""

    if path_owner is None:
        return None

    accessor_name = _named_child_accessor(field_name)
    if accessor_name is None or not hasattr(path_owner, accessor_name):
        return None

    return f"{parent_path}.{accessor_name}"


def _raw_child_collection_path(
    *,
    parent_path: str,
    parent_value: object,
    field_name: str,
) -> str:
    """Return one structural path to the underlying owned child collection."""

    if getattr(parent_value, "_is_child_container", False):
        return f"{parent_path}.declarations.{field_name}"
    return f"{parent_path}.{field_name}"


def _named_child_accessor(field_name: str) -> str | None:
    """Map one direct child-collection field to its public name-indexed accessor."""

    accessors = {
        "aliases": "alias",
        "class_templates": "class_template",
        "classes": "class_",
        "constructors": "constructor",
        "enumerators": "enumerator",
        "enums": "enum",
        "fields": "field",
        "function_templates": "function_template",
        "functions": "function",
        "methods": "method",
        "namespaces": "namespace",
        "parameters": "parameter",
    }
    return accessors.get(field_name)


def _child_view_returns_many(field_name: str) -> bool:
    """Return whether the named child accessor yields overload groups as lists."""

    return field_name in {
        "constructors",
        "function_templates",
        "functions",
        "methods",
    }


def _same_name_sibling_index(
    siblings: list[CppElement],
    name: str,
    item: CppElement,
) -> int:
    """Return one element's zero-based index within its same-name sibling group."""

    same_name_index = 0
    for sibling in siblings:
        if sibling.name != name:
            continue
        if sibling is item:
            return same_name_index
        same_name_index += 1

    return 0


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
    scope_description = scope._describe_element()

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


def _all_overloadable(elements: list[CppElement]) -> bool:
    """Return whether all given elements belong to one overloadable declaration kind."""

    if not elements:
        return False

    from .function import CppFunction
    from .function_template import CppFunctionTemplate
    from .member import CppConstructor, CppMethod

    if all(isinstance(element, CppConstructor) for element in elements):
        return True

    return all(
        isinstance(element, (CppFunction, CppMethod, CppFunctionTemplate))
        for element in elements
    )
