from __future__ import annotations

"""Build parsed `.cpp` facet data from libclang cursors."""

from pathlib import Path
from typing import Any

from clang.cindex import CursorKind

from ..model import CppClassBase, CppLocationInfo, CppVisibility, SourceLocation
from .types import build_cpp_type


# ==================================================================================================
#     Facet Builders
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Declaration Facets
# ------------------------------------------------------------------------------


def build_namespace_cpp_facet(cursor: Any) -> Any:
    from ..model import CppNamespaceCppFacet

    return CppNamespaceCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
    )


def build_class_cpp_facet(cursor: Any) -> Any:
    from ..model import CppClassCppFacet

    return CppClassCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        kind="struct" if is_struct_cursor(cursor) else "class",
        visibility=cursor_visibility(cursor),
        bases=build_class_bases(cursor),
    )


def build_enum_cpp_facet(cursor: Any) -> Any:
    from ..model import CppEnumCppFacet

    return CppEnumCppFacet(
        original_name=cursor.spelling or None,
        underlying_type=build_cpp_type(cursor_enum_underlying_type(cursor)),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_scoped=cursor_is_scoped_enum(cursor),
        visibility=cursor_visibility(cursor),
    )


def build_enumerator_cpp_facet(cursor: Any) -> Any:
    from ..model import CppEnumeratorCppFacet

    return CppEnumeratorCppFacet(
        original_name=cursor.spelling or None,
        value_spelling=cursor_enum_value_spelling(cursor),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
    )


def build_function_cpp_facet(cursor: Any) -> Any:
    from ..model import CppFunctionCppFacet

    return CppFunctionCppFacet(
        original_name=cursor.spelling or None,
        return_type=build_cpp_type(getattr(cursor, "result_type", None)),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
    )


def build_method_cpp_facet(cursor: Any) -> Any:
    from ..model import CppMethodCppFacet

    return CppMethodCppFacet(
        original_name=cursor.spelling or None,
        return_type=build_cpp_type(getattr(cursor, "result_type", None)),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        is_const=cursor_bool_method(cursor, "is_const_method"),
        is_static=cursor_bool_method(cursor, "is_static_method"),
        is_virtual=cursor_bool_method(cursor, "is_virtual_method"),
        is_pure_virtual=cursor_bool_method(cursor, "is_pure_virtual_method"),
        visibility=cursor_visibility(cursor),
    )


def build_constructor_cpp_facet(cursor: Any) -> Any:
    from ..model import CppConstructorCppFacet

    return CppConstructorCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        visibility=cursor_visibility(cursor),
    )


def build_field_cpp_facet(cursor: Any) -> Any:
    from ..model import CppFieldCppFacet

    return CppFieldCppFacet(
        original_name=cursor.spelling or None,
        type=build_cpp_type(getattr(cursor, "type", None)),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_static=cursor_bool_method(cursor, "is_static_field"),
        visibility=cursor_visibility(cursor),
    )


def build_parameter_cpp_facet(cursor: Any) -> Any:
    from ..model import CppParameterCppFacet

    return CppParameterCppFacet(
        original_name=cursor.spelling or None,
        type=build_cpp_type(getattr(cursor, "type", None)),
        location=build_location_info(cursor),
    )


# ------------------------------------------------------------------------------
#     Source Locations and Provenance
# ------------------------------------------------------------------------------


def build_location_info(cursor: Any) -> CppLocationInfo:
    """Convert one clang cursor location into the semantic provenance container."""

    location = cursor_source_location(cursor)
    if location is None:
        return CppLocationInfo()
    is_definition = cursor_is_definition(cursor)
    return CppLocationInfo(
        primary=location,
        declarations=[location],
        definition=location if is_definition else None,
    )


# ==================================================================================================
#     Cursor Data Extraction
# ==================================================================================================


def cursor_source_location(cursor: Any) -> SourceLocation | None:
    """Convert one clang cursor location into a semantic source location."""

    location = getattr(cursor, "location", None)
    if location is None:
        return None

    file_object = getattr(location, "file", None)
    if file_object is None:
        return None

    file_name = getattr(file_object, "name", None)
    if file_name is None:
        return None

    return SourceLocation(
        file=Path(file_name).resolve(),
        line=int(getattr(location, "line", 0)),
        column=int(getattr(location, "column", 0)),
    )


def cursor_is_from_active_header(cursor: Any, active_headers: set[Path]) -> bool:
    """Return whether one cursor belongs to one of the selected active headers."""

    location = cursor_source_location(cursor)
    if location is None:
        return False
    return location.file.resolve() in active_headers


def cursor_kind_name(cursor: Any) -> str:
    """Return one normalized libclang cursor-kind name for reporting."""

    kind = getattr(cursor, "kind", None)
    name = getattr(kind, "name", None)
    if name is not None:
        return str(name)
    return str(kind)


def cursor_raw_comment(cursor: Any) -> str | None:
    """Return one raw clang comment block when libclang exposes it."""

    raw_comment = getattr(cursor, "raw_comment", None)
    if raw_comment is None:
        return None

    normalized = str(raw_comment).strip()
    if not normalized:
        return None
    return normalized


def cursor_usr(cursor: Any) -> str | None:
    """Return one cursor USR when libclang exposes one for the entity."""

    get_usr = getattr(cursor, "get_usr", None)
    if not callable(get_usr):
        return None

    usr = get_usr()
    if not usr:
        return None
    return str(usr)


def cursor_visibility(cursor: Any) -> CppVisibility | None:
    """Return one semantic C++ visibility value for one clang cursor."""

    access_specifier = getattr(cursor, "access_specifier", None)
    access_name = getattr(access_specifier, "name", None)
    if access_name == "PUBLIC":
        return CppVisibility.PUBLIC
    if access_name == "PROTECTED":
        return CppVisibility.PROTECTED
    if access_name == "PRIVATE":
        return CppVisibility.PRIVATE
    return None


def cursor_bool_method(cursor: Any, method_name: str) -> bool:
    """Call one optional boolean libclang cursor method safely."""

    method = getattr(cursor, method_name, None)
    if callable(method):
        return bool(method())
    return False


def cursor_is_definition(cursor: Any) -> bool:
    """Return whether one clang cursor is a full definition."""

    return cursor_bool_method(cursor, "is_definition")


def cursor_is_noexcept(cursor: Any) -> bool:
    """Return whether one clang cursor represents a noexcept callable."""

    exception_spec_kind = getattr(cursor, "exception_specification_kind", None)
    kind_name = getattr(exception_spec_kind, "name", None)
    return kind_name in {"BASIC_NOEXCEPT", "COMPUTED_NOEXCEPT"}


def cursor_is_scoped_enum(cursor: Any) -> bool:
    """Return whether one clang enum cursor is scoped."""

    is_scoped_enum = getattr(cursor, "is_scoped_enum", None)
    if callable(is_scoped_enum):
        return bool(is_scoped_enum())
    return False


def cursor_enum_underlying_type(cursor: Any) -> Any:
    """Return one enum cursor's underlying type when libclang exposes it."""

    enum_type = getattr(cursor, "enum_type", None)
    if enum_type is not None:
        return enum_type

    underlying_enum_type = getattr(cursor, "underlying_enum_type", None)
    if callable(underlying_enum_type):
        return underlying_enum_type()

    return None


def cursor_enum_value_spelling(cursor: Any) -> str | None:
    """Return one enumerator cursor value in textual form when available."""

    enum_value = getattr(cursor, "enum_value", None)
    if enum_value is None:
        return None
    return str(enum_value)


def is_struct_cursor(cursor: Any) -> bool:
    """Return whether one cursor is specifically a struct declaration."""

    return getattr(cursor, "kind", None) == CursorKind.STRUCT_DECL


def is_base_specifier_cursor(cursor: Any) -> bool:
    """Return whether one cursor is a class-base specifier helper cursor."""

    return getattr(cursor, "kind", None) == CursorKind.CXX_BASE_SPECIFIER


def build_class_bases(cursor: Any) -> list[CppClassBase]:
    """Collect direct base-class relationships declared on one class cursor."""

    bases: list[CppClassBase] = []
    for child_cursor in cursor.get_children():
        if not is_base_specifier_cursor(child_cursor):
            continue

        base_type = build_cpp_type(getattr(child_cursor, "type", None))
        if base_type is None:
            continue

        bases.append(
            CppClassBase(
                type=base_type,
                visibility=cursor_visibility(child_cursor),
                is_virtual=cursor_bool_method(child_cursor, "is_virtual_base"),
            )
        )

    return bases
