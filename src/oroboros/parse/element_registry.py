from __future__ import annotations

"""Attach and reuse semantic elements during clang model building."""

from copy import deepcopy
from typing import TYPE_CHECKING, Any, TypeVar

from clang.cindex import CursorKind

from ..model import CppClassMembers, CppClassTemplate, CppElement, CppModule, CppNamespace
from .extract_cpp_facets import extract_namespace_cpp_facet
from .cursor_data import cursor_source_location, cursor_usr

if TYPE_CHECKING:
    from .build_model import BuildContext

_ElementT = TypeVar("_ElementT")


# ==================================================================================================
#     Element Registry
# ==================================================================================================


def ensure_namespace(
    owner: CppElement,
    cursor: Any,
    context: BuildContext,
    *,
    merge_common_cpp_fields: Any,
    merge_cpp_scalar: Any,
) -> CppNamespace | None:
    """Return one existing or newly created namespace for one parser cursor."""

    candidate_cpp = extract_namespace_cpp_facet(cursor, context=context)
    _inherit_compact_namespace_comment(owner, candidate_cpp)
    existing = lookup_registered_element(cursor, context, CppNamespace)
    if existing is not None:
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_scalar(existing, "is_inline", candidate_cpp.is_inline, context, cursor)
        return existing

    namespace_name = cursor.spelling
    existing_declarations = getattr(owner, "declarations", None)
    existing_namespaces = getattr(existing_declarations, "namespaces", None)
    if namespace_name and existing_namespaces is not None:
        for namespace in existing_namespaces:
            if namespace.name == namespace_name:
                merge_common_cpp_fields(namespace, candidate_cpp, context, cursor)
                merge_cpp_scalar(namespace, "is_inline", candidate_cpp.is_inline, context, cursor)
                register_element_for_cursor(cursor, namespace, context)
                return namespace

    namespace = CppNamespace(
        name=namespace_name,
        cpp=candidate_cpp,
    )
    attached = owner.add_namespace(namespace)
    register_element_for_cursor(cursor, attached, context)
    return attached


def _inherit_compact_namespace_comment(owner: CppElement, candidate_cpp: Any) -> None:
    """Propagate one compact `namespace a::b` comment from the outer to inner namespace."""

    if not isinstance(owner, CppNamespace):
        return

    candidate_doc = getattr(candidate_cpp, "doc", None)
    owner_doc = getattr(owner.cpp, "doc", None)
    if candidate_doc is not None and candidate_doc.attached_comment is not None:
        return
    if owner_doc is None or owner_doc.attached_comment is None:
        return

    owner_location = owner.cpp.location.primary
    candidate_location = candidate_cpp.location.primary
    if owner_location is None or candidate_location is None:
        return
    if owner_location.file != candidate_location.file or owner_location.line != candidate_location.line:
        return

    candidate_cpp.doc = deepcopy(owner_doc)


def lookup_registered_element(
    cursor: Any,
    context: BuildContext,
    expected_type: type[_ElementT],
) -> _ElementT | None:
    """Return the previously materialized element for one cursor USR, if any."""

    usr = cursor_usr(cursor)
    if usr is None:
        return None

    element = context.usr_to_element.get(usr)
    if isinstance(element, expected_type):
        return element
    return None


def register_element_for_cursor(
    cursor: Any,
    element: CppElement,
    context: BuildContext,
) -> None:
    """Record one cursor USR to semantic element mapping for later reuse."""

    usr = cursor_usr(cursor)
    if usr is None:
        return

    context.usr_to_element.setdefault(usr, element)


# ==================================================================================================
#     Semantic Owner Resolution
# ==================================================================================================


def resolve_semantic_owner(
    cursor: Any,
    fallback_owner: CppElement,
    context: BuildContext,
) -> CppElement:
    """Resolve the semantic owner that should receive one visited child cursor."""

    semantic_parent = getattr(cursor, "semantic_parent", None)
    semantic_owner = _semantic_owner_from_usr(semantic_parent, context)
    if semantic_owner is not None:
        return semantic_owner

    matched_registered_owner = find_registered_semantic_owner(semantic_parent, context)
    if matched_registered_owner is not None:
        return matched_registered_owner

    matched_ancestor = matching_owner_ancestor(semantic_parent, fallback_owner)
    if matched_ancestor is not None:
        return matched_ancestor

    return fallback_owner


def resolve_class_semantic_owner(
    cursor: Any,
    context: BuildContext,
) -> CppClassMembers | None:
    """Return the class-like semantic owner of one cursor when already materialized."""

    semantic_parent = getattr(cursor, "semantic_parent", None)
    semantic_owner = _semantic_owner_from_usr(semantic_parent, context)
    if isinstance(semantic_owner, CppClassMembers):
        return semantic_owner

    matched_registered_owner = find_registered_semantic_owner(semantic_parent, context)
    if isinstance(matched_registered_owner, CppClassMembers):
        return matched_registered_owner
    return None


def _semantic_owner_from_usr(
    semantic_parent: Any,
    context: BuildContext,
) -> CppElement | None:
    """Return the registered semantic owner for one semantic-parent cursor USR."""

    semantic_parent_usr = cursor_usr(semantic_parent)
    if semantic_parent_usr is None:
        return None

    semantic_owner = context.usr_to_element.get(semantic_parent_usr)
    if isinstance(semantic_owner, CppClassTemplate):
        return semantic_owner.declaration
    return semantic_owner


def find_registered_semantic_owner(
    semantic_parent: Any,
    context: BuildContext,
) -> CppClassMembers | None:
    """Find one already-registered class-like owner by scope/name when USRs do not align."""

    seen_ids: set[int] = set()
    for element in context.usr_to_element.values():
        if id(element) in seen_ids:
            continue
        seen_ids.add(id(element))
        candidate = element.declaration if isinstance(element, CppClassTemplate) else element
        if not isinstance(candidate, CppClassMembers):
            continue
        if not element_matches_semantic_parent(candidate, semantic_parent):
            continue
        if _semantic_parent_chain_matches(candidate.owner, getattr(semantic_parent, "semantic_parent", None)):
            return candidate
    return None


def element_matches_semantic_parent(
    element: CppElement,
    semantic_parent: Any,
) -> bool:
    """Return whether one model element corresponds to one clang semantic-parent cursor."""

    parent_kind = getattr(semantic_parent, "kind", None)
    if parent_kind == CursorKind.TRANSLATION_UNIT:
        return isinstance(element, CppModule)

    parent_name = getattr(semantic_parent, "spelling", None)
    if parent_kind == CursorKind.NAMESPACE:
        return isinstance(element, CppNamespace) and element.name == parent_name

    return getattr(element, "name", None) == parent_name


def _semantic_parent_chain_matches(
    owner: CppElement | None,
    semantic_parent: Any,
) -> bool:
    """Return whether one clang semantic-parent chain matches one model-owner chain."""

    owner = _normalize_owner_for_semantic_match(owner)
    if semantic_parent is None:
        return owner is None
    if owner is None:
        return False
    if not element_matches_semantic_parent(owner, semantic_parent):
        return False

    next_semantic_parent = getattr(semantic_parent, "semantic_parent", None)
    if getattr(semantic_parent, "kind", None) == CursorKind.TRANSLATION_UNIT:
        return True
    return _semantic_parent_chain_matches(owner.owner, next_semantic_parent)


def _normalize_owner_for_semantic_match(owner: CppElement | None) -> CppElement | None:
    """Skip wrapper elements that do not correspond to clang semantic-parent scopes."""

    if isinstance(owner, CppClassTemplate):
        return owner.owner
    return owner


def matching_owner_ancestor(
    semantic_parent: Any,
    owner: CppElement,
) -> CppElement | None:
    """Find one already-materialized ancestor matching a child cursor semantic parent."""

    current: CppElement | None = owner
    while current is not None:
        if element_matches_semantic_parent(current, semantic_parent):
            return current
        current = current.owner
    return None


# ==================================================================================================
#     Unsupported Cursor Reporting
# ==================================================================================================


def record_skipped_cursor_example(cursor: Any, context: BuildContext) -> None:
    """Capture a short example for one unsupported cursor kind when requested."""

    if context.config.unsupported_cursor_reporting != "examples":
        return

    kind_name = str(getattr(getattr(cursor, "kind", None), "name", "<unknown>"))
    examples = context.skipped_kind_examples.setdefault(kind_name, [])
    if len(examples) >= 3:
        return

    location = cursor_source_location(cursor)
    location_text = "<unknown location>" if location is None else str(location)
    spelling = getattr(cursor, "spelling", "") or "<anonymous>"
    examples.append(f"{spelling} @ {location_text}")
