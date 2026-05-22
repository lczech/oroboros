from __future__ import annotations

"""Attach and reuse semantic elements during clang model building."""

from typing import TYPE_CHECKING, Any, TypeVar

from ..model import CppElement, CppNamespace
from .build_facets import build_namespace_cpp_facet
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

    candidate_cpp = build_namespace_cpp_facet(cursor)
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
    attached = attach_element(owner, "add_namespace", namespace)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
    return attached


def attach_element(
    owner: CppElement,
    attach_method_name: str,
    element: _ElementT,
) -> _ElementT | None:
    """Attach one element through the named owner `add_*` helper when available."""

    attach = getattr(owner, attach_method_name, None)
    if attach is None:
        return None
    return attach(element)


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
