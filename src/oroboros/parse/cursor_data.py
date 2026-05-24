from __future__ import annotations

"""Low-level libclang cursor data helpers used by the parse stage."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clang.cindex import (
    AccessSpecifier,
    CursorKind,
    ExceptionSpecificationKind,
    LinkageKind,
    StorageClass,
    TLSKind,
    TokenKind,
    TypeKind,
)

from ..model import CppOperator, CppVisibility, SourceLocation


# ==================================================================================================
#     Token Data
# ==================================================================================================


@dataclass(slots=True)
class CursorTokenInfo:
    """Store one token plus the source positions needed for local syntax recovery."""

    kind: TokenKind
    spelling: str
    start_line: int
    start_column: int
    start_offset: int
    end_line: int
    end_column: int
    end_offset: int


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


def cursor_alias_template_target_cursor(cursor: Any) -> Any | None:
    """Return the nested `TYPE_ALIAS_DECL` child that carries one alias-template target."""

    for child_cursor in cursor.get_children():
        if getattr(child_cursor, "kind", None) == CursorKind.TYPE_ALIAS_DECL:
            return child_cursor
    return None


def cursor_alias_template_target_type(cursor: Any) -> Any:
    """Return one alias-template cursor's underlying target type when clang exposes it."""

    target_cursor = cursor_alias_template_target_cursor(cursor)
    if target_cursor is None:
        return None
    return cursor_alias_target_type(target_cursor)


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
    if access_specifier == AccessSpecifier.PUBLIC:
        return CppVisibility.PUBLIC
    if access_specifier == AccessSpecifier.PROTECTED:
        return CppVisibility.PROTECTED
    if access_specifier == AccessSpecifier.PRIVATE:
        return CppVisibility.PRIVATE

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

    if storage_class == StorageClass.INVALID:
        return None
    if storage_class == StorageClass.NONE:
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

    if linkage == LinkageKind.INVALID:
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

    if tls_kind == TLSKind.NONE:
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
    if exception_spec_kind is None:
        return False

    if exception_spec_kind == ExceptionSpecificationKind.BASIC_NOEXCEPT:
        return True
    if exception_spec_kind == ExceptionSpecificationKind.COMPUTED_NOEXCEPT:
        return True

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


def cursor_parameter_default_value(cursor: Any) -> str | None:
    """Return one normalized parameter default expression from cursor tokens."""

    token_spellings = cursor_token_spellings(cursor)
    if "=" not in token_spellings:
        return None

    default_tokens = token_spellings[token_spellings.index("=") + 1 :]
    if not default_tokens:
        return None

    rendered = normalize_token_spellings(default_tokens)
    return rendered or None


def cursor_has_explicit_specifier(cursor: Any) -> bool:
    """Return whether one constructor cursor is preceded by an `explicit` specifier."""

    token_spellings = cursor_token_spellings(cursor)
    if "explicit" not in token_spellings:
        return False

    explicit_index = token_spellings.index("explicit")
    spelling = getattr(cursor, "spelling", None)
    if spelling and spelling in token_spellings:
        spelling_index = token_spellings.index(spelling)
        if explicit_index >= spelling_index:
            return False

        # Regular explicit specifier: `explicit` appears before the constructor name.
        if explicit_index + 1 >= spelling_index or token_spellings[explicit_index + 1] != "(":
            return True

        # C++20 abbreviated function template syntax with specifier `explicit(...)`
        parenthesis_depth = 0
        inner_tokens: list[str] = []
        for token in token_spellings[explicit_index + 1 : spelling_index]:
            if token == "(":
                if parenthesis_depth > 0:
                    inner_tokens.append(token)
                parenthesis_depth += 1
                continue
            if token == ")":
                parenthesis_depth -= 1
                if parenthesis_depth > 0:
                    inner_tokens.append(token)
                continue
            if parenthesis_depth > 0:
                inner_tokens.append(token)

        normalized_inner = normalize_token_spellings(inner_tokens)
        if normalized_inner == "false":
            return False
        if normalized_inner == "true":
            return True

        return True
    return True


def cursor_callable_is_deleted(cursor: Any, *, context: Any | None = None) -> bool:
    """Return whether one callable declaration is marked `= delete`."""

    if cursor_bool_method(cursor, "is_deleted_method"):
        return True

    if _has_token_suffix_sequence(cursor_token_spellings(cursor), ["=", "delete"]):
        return True

    following_tokens = cursor_following_token_spellings(cursor, context=context, max_tokens=2)
    return following_tokens[:2] == ["=", "delete"]


def cursor_callable_is_defaulted(cursor: Any, *, context: Any | None = None) -> bool:
    """Return whether one callable declaration is marked `= default`."""

    if cursor_bool_method(cursor, "is_default_method"):
        return True

    if _has_token_suffix_sequence(cursor_token_spellings(cursor), ["=", "default"]):
        return True

    following_tokens = cursor_following_token_spellings(cursor, context=context, max_tokens=2)
    return following_tokens[:2] == ["=", "default"]


def cursor_ref_qualifier(cursor: Any) -> str | None:
    """Return one member-callable ref-qualifier token, when the declaration uses one."""

    token_spellings = cursor_token_spellings(cursor)
    if not token_spellings:
        return None

    for close_index in _top_level_parenthesis_close_indices(token_spellings):
        qualifier = _cursor_ref_qualifier_after_parenthesis_close(token_spellings, close_index)
        if qualifier is _INVALID_REF_QUALIFIER_CANDIDATE:
            continue
        return qualifier

    return None


def cursor_operator(cursor: Any) -> CppOperator | None:
    """Return structured operator metadata for one callable cursor when applicable."""

    kind = getattr(cursor, "kind", None)
    if kind == CursorKind.CONVERSION_FUNCTION:
        return CppOperator(
            kind="conversion",
            is_explicit=cursor_conversion_operator_is_explicit(cursor),
        )

    spelling = getattr(cursor, "spelling", None)
    if spelling is None:
        return None

    normalized_spelling = str(spelling).strip()
    if not normalized_spelling.startswith("operator"):
        return None

    operator_spelling = normalized_spelling[len("operator") :].strip()
    if not operator_spelling:
        return None

    if operator_spelling == "co_await":
        return CppOperator(kind="co_await", symbol=operator_spelling)

    if operator_spelling in {"new", "new[]"}:
        return CppOperator(kind="allocation", symbol=operator_spelling)

    if operator_spelling in {"delete", "delete[]"}:
        return CppOperator(kind="deallocation", symbol=operator_spelling)

    if operator_spelling not in _SYMBOLIC_OPERATOR_SPELLINGS:
        return None

    return CppOperator(
        kind="symbolic",
        symbol=operator_spelling,
        is_postfix=_cursor_operator_is_postfix(cursor, operator_spelling),
    )


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

    # Real libclang cursors should normally be enough here, but keep the token
    # fallback for odd synthetic/test cursors where only the spelled keyword is available.
    token_spellings = cursor_token_spellings(cursor)
    if "struct" in token_spellings:
        return "struct"
    return "class"


def is_base_specifier_cursor(cursor: Any) -> bool:
    """Return whether one cursor is a class-base specifier helper cursor."""

    return getattr(cursor, "kind", None) == CursorKind.CXX_BASE_SPECIFIER


# ==================================================================================================
#     Token Helpers
# ==================================================================================================


def file_cursor_tokens(file_path: Path, context: Any | None) -> list[CursorTokenInfo]:
    """Return cached clang tokens for one source file when a translation unit is available."""

    if context is None:
        return []

    cached = getattr(context, "file_tokens_by_path", {}).get(file_path)
    if cached is not None:
        return cached

    translation_unit = getattr(context, "translation_unit", None)
    get_extent = getattr(translation_unit, "get_extent", None)
    get_tokens = getattr(translation_unit, "get_tokens", None)
    if not callable(get_extent) or not callable(get_tokens):
        return []

    line_count = _count_source_lines(file_path)
    extent = get_extent(str(file_path), ((1, 1), (line_count + 1, 1)))
    tokens: list[CursorTokenInfo] = []
    for token in get_tokens(extent=extent):
        token_location = getattr(token, "location", None)
        file_object = getattr(token_location, "file", None)
        file_name = getattr(file_object, "name", None)
        if file_name is None or Path(file_name).resolve() != file_path:
            continue

        token_extent = getattr(token, "extent", None)
        if token_extent is None:
            continue

        token_kind = getattr(token, "kind", None)
        if token_kind is None:
            continue

        start = token_extent.start
        end = token_extent.end
        tokens.append(
            CursorTokenInfo(
                kind=token_kind,
                spelling=str(getattr(token, "spelling", "")),
                start_line=int(getattr(start, "line", 0)),
                start_column=int(getattr(start, "column", 0)),
                start_offset=int(getattr(start, "offset", 0)),
                end_line=int(getattr(end, "line", 0)),
                end_column=int(getattr(end, "column", 0)),
                end_offset=int(getattr(end, "offset", 0)),
            )
        )

    getattr(context, "file_tokens_by_path", {})[file_path] = tokens
    return tokens


def cursor_following_token_spellings(
    cursor: Any,
    *,
    context: Any | None = None,
    max_tokens: int | None = None,
) -> list[str]:
    """Return normalized token spellings immediately following one cursor extent."""

    file_path = _cursor_file_path(cursor)
    cursor_extent = getattr(cursor, "extent", None)
    if file_path is None or cursor_extent is None:
        return []

    tokens = file_cursor_tokens(file_path, context)
    if not tokens:
        return []

    end = cursor_extent.end
    end_offset = int(getattr(end, "offset", 0))
    following_spellings: list[str] = []
    for token in tokens:
        if token.start_offset < end_offset:
            continue
        if token.kind == TokenKind.COMMENT:
            continue
        if token.spelling == ";":
            break
        following_spellings.append(token.spelling)
        if max_tokens is not None and len(following_spellings) >= max_tokens:
            break
    return following_spellings


def normalize_token_spellings(token_spellings: list[str]) -> str:
    """Render one token sequence into a compact normalized spelling."""

    if not token_spellings:
        return ""

    glued_punctuation: set[str] = {
        "::", ".", "->", "->*",
        "(", ")", "[", "]", "{", "}", "<", ">",
        ",", ";", ":", "?", "!", "~",
        "+", "-", "*", "/", "%", "^", "&", "&&", "|", "||",
        "=", "==", "!=", "<=", ">=", "<<", ">>",
        "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
    }

    rendered = token_spellings[0]
    previous = token_spellings[0]
    for current in token_spellings[1:]:
        if previous not in glued_punctuation and current not in glued_punctuation:
            rendered += " "
        rendered += current
        previous = current
    return rendered


def _has_token_suffix_sequence(token_spellings: list[str], suffix: list[str]) -> bool:
    """Return whether one token spelling sequence ends with a given suffix."""

    if len(token_spellings) < len(suffix):
        return False
    return token_spellings[-len(suffix) :] == suffix


def _top_level_parenthesis_close_indices(token_spellings: list[str]) -> list[int]:
    """Return indices of `)` tokens that close one top-level parenthesized sequence."""

    depth = 0
    close_indices: list[int] = []
    for index, token in enumerate(token_spellings):
        if token == "(":
            depth += 1
            continue
        if token != ")" or depth <= 0:
            continue
        depth -= 1
        if depth == 0:
            close_indices.append(index)
    return close_indices


def _cursor_ref_qualifier_after_parenthesis_close(
    token_spellings: list[str],
    close_index: int,
) -> str | None | object:
    """Return one trailing ref-qualifier after a candidate declarator `)` token."""

    index = close_index + 1
    while index < len(token_spellings):
        token = token_spellings[index]

        if token in {"const", "volatile", "override", "final"}:
            index += 1
            continue

        if token in {"&", "&&"}:
            return token

        if token in {"noexcept", "requires", "->", ";", "{", "=", ":"}:
            return None

        if token == "(":
            return _INVALID_REF_QUALIFIER_CANDIDATE

        return _INVALID_REF_QUALIFIER_CANDIDATE

    return None


_SYMBOLIC_OPERATOR_SPELLINGS = frozenset({
    "+", "-", "*", "/", "%",
    "^", "&", "|", "~",
    "!", "=",
    "<", ">", "+=", "-=", "*=", "/=", "%=",
    "^=", "&=", "|=",
    "<<", ">>", ">>=", "<<=",
    "==", "!=", "<=", ">=", "<=>",
    "&&", "||",
    "++", "--",
    ",", "->*", "->",
    "()", "[]",
})


def _cursor_operator_is_postfix(
    cursor: Any,
    operator_spelling: str,
) -> bool:
    """Return whether one increment/decrement operator uses postfix callable shape."""

    if operator_spelling not in {"++", "--"}:
        return False

    parameter_cursors = [
        child_cursor
        for child_cursor in cursor.get_children()
        if getattr(child_cursor, "kind", None) == CursorKind.PARM_DECL
    ]
    if len(parameter_cursors) != 1:
        return False

    return _cursor_parameter_is_int(parameter_cursors[0])


def _cursor_parameter_is_int(cursor: Any) -> bool:
    """Return whether one parameter cursor has plain `int` type."""

    clang_type = getattr(cursor, "type", None)
    if clang_type is None:
        return False

    kind = getattr(clang_type, "kind", None)
    if kind == TypeKind.INT:
        return True

    kind_name = getattr(kind, "name", None)
    if kind_name == "INT":
        return True

    return str(getattr(clang_type, "spelling", "")).strip() == "int"


def cursor_conversion_operator_is_explicit(cursor: Any) -> bool:
    """Return whether one conversion operator uses an `explicit` specifier."""

    if getattr(cursor, "kind", None) != CursorKind.CONVERSION_FUNCTION:
        return False

    token_spellings = cursor_token_spellings(cursor)
    if "explicit" not in token_spellings:
        return False

    explicit_index = token_spellings.index("explicit")
    try:
        operator_index = token_spellings.index("operator")
    except ValueError:
        return True

    if explicit_index >= operator_index:
        return False

    if explicit_index + 1 >= operator_index or token_spellings[explicit_index + 1] != "(":
        return True

    parenthesis_depth = 0
    inner_tokens: list[str] = []
    for token in token_spellings[explicit_index + 1 : operator_index]:
        if token == "(":
            if parenthesis_depth > 0:
                inner_tokens.append(token)
            parenthesis_depth += 1
            continue
        if token == ")":
            parenthesis_depth -= 1
            if parenthesis_depth > 0:
                inner_tokens.append(token)
            continue
        if parenthesis_depth > 0:
            inner_tokens.append(token)

    normalized_inner = normalize_token_spellings(inner_tokens)
    if normalized_inner == "false":
        return False
    if normalized_inner == "true":
        return True

    return True


def _cursor_file_path(cursor: Any) -> Path | None:
    """Return the resolved source file path for one cursor when available."""

    location = getattr(cursor, "location", None)
    file_object = getattr(location, "file", None)
    file_name = getattr(file_object, "name", None)
    if file_name is None:
        return None
    return Path(file_name).resolve()


def _count_source_lines(file_path: Path) -> int:
    """Return the source-file line count used to build a file token extent."""

    return file_path.read_text(encoding="utf-8", errors="ignore").count("\n") + 1


_INVALID_REF_QUALIFIER_CANDIDATE = object()
