from __future__ import annotations

"""Attach and reuse semantic elements during clang model building."""

from copy import deepcopy
from typing import TYPE_CHECKING, Any, TypeVar

from ..model import CppElement, CppNamespace
from .extract_cpp_facets import extract_namespace_cpp_facet
from .cursor_data import cursor_usr

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
