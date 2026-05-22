from __future__ import annotations

"""Low-level libclang cursor data helpers used by the parse stage."""

from pathlib import Path
from typing import Any

from clang.cindex import CursorKind

from ..model import CppVisibility, SourceLocation


# ==================================================================================================
#     Source Locations And Header Membership
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


# ==================================================================================================
#     Cursor Identity And Display
# ==================================================================================================


def cursor_kind_name(cursor: Any) -> str:
    """Return one normalized libclang cursor-kind name for reporting."""

    kind = getattr(cursor, "kind", None)
    name = getattr(kind, "name", None)
    if name is not None:
        return str(name)
    return str(kind)


def cursor_token_spellings(cursor: Any) -> list[str]:
    """Return the token spellings directly attached to one clang cursor."""

    get_tokens = getattr(cursor, "get_tokens", None)
    if not callable(get_tokens):
        return []
    return [token.spelling for token in get_tokens()]


def cursor_usr(cursor: Any) -> str | None:
    """Return one cursor USR when libclang exposes one for the entity."""

    get_usr = getattr(cursor, "get_usr", None)
    if not callable(get_usr):
        return None

    usr = get_usr()
    if not usr:
        return None
    return str(usr)


# ==================================================================================================
#     Cursor Facts
# ==================================================================================================


def cursor_alias_target_type(cursor: Any) -> Any:
    """Return one alias cursor's underlying target type when libclang exposes it."""

    target = getattr(cursor, "underlying_typedef_type", None)
    if callable(target):
        return target()
    return target


def cursor_alias_kind(cursor: Any) -> str | None:
    """Return whether one alias cursor came from `using` or `typedef` syntax."""

    kind = getattr(cursor, "kind", None)
    if kind == CursorKind.TYPE_ALIAS_DECL:
        return "using"
    if kind == CursorKind.TYPEDEF_DECL:
        return "typedef"
    return None


def cursor_raw_comment(cursor: Any) -> str | None:
    """Return one raw clang comment block when libclang exposes it."""

    raw_comment = getattr(cursor, "raw_comment", None)
    if raw_comment is None:
        return None

    normalized = str(raw_comment).strip()
    if not normalized:
        return None
    return normalized


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


def cursor_storage_class(cursor: Any) -> str | None:
    """Return one normalized storage-class value when libclang exposes it."""

    storage_class = getattr(cursor, "storage_class", None)
    if storage_class is None:
        return None

    name = getattr(storage_class, "name", None)
    if not name or name in {"INVALID", "NONE"}:
        return None
    return str(name).lower()


def cursor_linkage(cursor: Any) -> str | None:
    """Return one normalized linkage value when libclang exposes it."""

    linkage = getattr(cursor, "linkage", None)
    if linkage is None:
        return None

    name = getattr(linkage, "name", None)
    if not name or name in {"INVALID"}:
        return None
    return str(name).lower()


def cursor_tls_kind(cursor: Any) -> str | None:
    """Return one normalized thread-local storage kind when libclang exposes it."""

    tls_kind = getattr(cursor, "tls_kind", None)
    if tls_kind is None:
        return None

    name = getattr(tls_kind, "name", None)
    if not name or name == "NONE":
        return None
    return str(name).lower()


def cursor_type_is_const_qualified(cursor: Any) -> bool:
    """Return whether one cursor's declared type is top-level const-qualified."""

    cpp_type = getattr(cursor, "type", None)
    if cpp_type is None:
        return False

    is_const_qualified = getattr(cpp_type, "is_const_qualified", None)
    if callable(is_const_qualified):
        return bool(is_const_qualified())
    return False


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


# ==================================================================================================
#     Cursor Shape Helpers
# ==================================================================================================


def is_struct_cursor(cursor: Any) -> bool:
    """Return whether one cursor is specifically a struct declaration."""

    return getattr(cursor, "kind", None) == CursorKind.STRUCT_DECL


def cursor_class_kind(cursor: Any) -> str:
    """Return whether one class-like cursor uses `class` or `struct` syntax."""

    if is_struct_cursor(cursor):
        return "struct"
    if getattr(cursor, "kind", None) == CursorKind.CLASS_DECL:
        return "class"

    token_spellings = cursor_token_spellings(cursor)
    if "struct" in token_spellings:
        return "struct"
    return "class"


def is_base_specifier_cursor(cursor: Any) -> bool:
    """Return whether one cursor is a class-base specifier helper cursor."""

    return getattr(cursor, "kind", None) == CursorKind.CXX_BASE_SPECIFIER
