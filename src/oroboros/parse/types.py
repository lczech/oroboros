from __future__ import annotations

"""Translate clang type objects into the semantic C++ type model."""

from typing import Any

from ..model import (
    ArrayCppType,
    BuiltinCppType,
    CppType,
    FunctionCppType,
    LValueReferenceCppType,
    NamedCppType,
    PointerCppType,
    RValueReferenceCppType,
    TemplateInstanceCppType,
)
from ..model.type import cpp_builtin_kind_from_spelling


_CLANG_BUILTIN_KIND_MAP: dict[str, str] = {
    "VOID": "void",
    "NULLPTR": "nullptr_t",
    "BOOL": "bool",
    "CHAR_U": "char",
    "UCHAR": "unsigned_char",
    "CHAR16": "char16_t",
    "CHAR32": "char32_t",
    "USHORT": "unsigned_short",
    "UINT": "unsigned_int",
    "ULONG": "unsigned_long",
    "ULONGLONG": "unsigned_long_long",
    "CHAR_S": "char",
    "SCHAR": "signed_char",
    "WCHAR": "wchar_t",
    "SHORT": "short",
    "INT": "int",
    "LONG": "long",
    "LONGLONG": "long_long",
    "FLOAT": "float",
    "DOUBLE": "double",
    "LONGDOUBLE": "long_double",
}


def build_cpp_type(clang_type: Any) -> CppType | None:
    """Convert one clang type object into the structured semantic type model."""

    if clang_type is None:
        return None

    return _build_cpp_type(clang_type, allow_canonical=True)


def _build_cpp_type(
    clang_type: Any,
    *,
    allow_canonical: bool,
) -> CppType | None:
    """Recursively convert one clang type while avoiding canonical recursion loops."""

    clang_kind_name = _type_kind_name(clang_type)
    is_const = _is_const_qualified(clang_type)

    builtin_kind = _CLANG_BUILTIN_KIND_MAP.get(clang_kind_name)
    if builtin_kind is not None:
        return BuiltinCppType(kind=builtin_kind, is_const=is_const)

    if clang_kind_name == "POINTER":
        return PointerCppType(
            pointee=_build_cpp_type(_get_pointee_type(clang_type), allow_canonical=allow_canonical),
            is_const=is_const,
        )

    if clang_kind_name == "LVALUEREFERENCE":
        return LValueReferenceCppType(
            referred=_build_cpp_type(_get_pointee_type(clang_type), allow_canonical=allow_canonical),
            is_const=is_const,
        )

    if clang_kind_name == "RVALUEREFERENCE":
        return RValueReferenceCppType(
            referred=_build_cpp_type(_get_pointee_type(clang_type), allow_canonical=allow_canonical),
            is_const=is_const,
        )

    if clang_kind_name in {"CONSTANTARRAY", "INCOMPLETEARRAY"}:
        return ArrayCppType(
            element_type=_build_cpp_type(_get_array_element_type(clang_type), allow_canonical=allow_canonical),
            extent=_get_array_extent(clang_type),
            is_const=is_const,
        )

    if clang_kind_name in {"FUNCTIONPROTO", "FUNCTIONNOPROTO"}:
        return FunctionCppType(
            return_type=_build_cpp_type(_get_result_type(clang_type), allow_canonical=allow_canonical),
            parameters=[
                _build_cpp_type(parameter_type, allow_canonical=allow_canonical)
                for parameter_type in _get_argument_types(clang_type)
            ],
            is_variadic=_is_function_variadic(clang_type),
            is_const=is_const,
        )

    spelling = _type_spelling(clang_type)
    template_instance = _parse_template_instance_spelling(spelling, is_const=is_const)
    if template_instance is not None:
        return template_instance

    canonical = None
    if allow_canonical:
        canonical_type = _get_canonical_type(clang_type)
        if canonical_type is not None and not _same_type_identity(clang_type, canonical_type):
            canonical = _build_cpp_type(canonical_type, allow_canonical=False)

    return NamedCppType(
        name=spelling,
        canonical=canonical,
        is_const=is_const,
    )


def _parse_template_instance_spelling(
    spelling: str,
    *,
    is_const: bool,
) -> TemplateInstanceCppType | None:
    """Parse one simple template-instantiation spelling into a structured type."""

    normalized = spelling.strip()
    if not normalized.endswith(">") or "<" not in normalized:
        return None

    base_name, argument_text = _split_template_spelling(normalized)
    if base_name is None or argument_text is None:
        return None

    argument_spellings = _split_template_arguments(argument_text)
    if not argument_spellings:
        return None

    return TemplateInstanceCppType(
        template_name=base_name,
        arguments=[
            _build_type_from_spelling(argument_spelling)
            for argument_spelling in argument_spellings
        ],
        is_const=is_const,
    )


def _build_type_from_spelling(spelling: str) -> CppType:
    """Build one fallback semantic type from a plain C++ spelling fragment."""

    normalized = spelling.strip()
    is_const = False

    if normalized.startswith("const "):
        is_const = True
        normalized = normalized[len("const "):].strip()

    if normalized.endswith("&&"):
        return RValueReferenceCppType(
            referred=_build_type_from_spelling(normalized[:-2]),
            is_const=is_const,
        )

    if normalized.endswith("&"):
        return LValueReferenceCppType(
            referred=_build_type_from_spelling(normalized[:-1]),
            is_const=is_const,
        )

    if normalized.endswith("*"):
        return PointerCppType(
            pointee=_build_type_from_spelling(normalized[:-1]),
            is_const=is_const,
        )

    template_instance = _parse_template_instance_spelling(normalized, is_const=is_const)
    if template_instance is not None:
        return template_instance

    builtin_kind = cpp_builtin_kind_from_spelling(normalized)
    if builtin_kind is not None:
        return BuiltinCppType(kind=builtin_kind, is_const=is_const)

    return NamedCppType(name=normalized, is_const=is_const)


def _split_template_spelling(spelling: str) -> tuple[str | None, str | None]:
    """Split one `Name<Args...>` spelling into base name and inner argument text."""

    depth = 0
    start_index = None
    for index, character in enumerate(spelling):
        if character == "<":
            if depth == 0:
                start_index = index
            depth += 1
        elif character == ">":
            depth -= 1
            if depth == 0 and start_index is not None:
                base_name = spelling[:start_index].strip()
                argument_text = spelling[start_index + 1:index].strip()
                if index != len(spelling) - 1:
                    return None, None
                return base_name, argument_text

    return None, None


def _split_template_arguments(argument_text: str) -> list[str]:
    """Split one template argument list text into top-level argument spellings."""

    arguments: list[str] = []
    current: list[str] = []
    depth = 0

    for character in argument_text:
        if character == "<":
            depth += 1
        elif character == ">":
            depth -= 1
        elif character == "," and depth == 0:
            argument = "".join(current).strip()
            if argument:
                arguments.append(argument)
            current = []
            continue

        current.append(character)

    tail = "".join(current).strip()
    if tail:
        arguments.append(tail)

    return arguments


def _type_kind_name(clang_type: Any) -> str:
    """Return one normalized libclang type-kind name.

    Libclang exposes these enum names in uppercase forms such as `POINTER`,
    `FUNCTIONPROTO`, and `LVALUEREFERENCE`, so the parser comparisons use those
    values directly.
    """

    kind = getattr(clang_type, "kind", None)
    name = getattr(kind, "name", None)
    if name is not None:
        return str(name)
    return str(kind)


def _type_spelling(clang_type: Any) -> str:
    """Return one normalized type spelling string."""

    return str(getattr(clang_type, "spelling", "")).strip()


def _is_const_qualified(clang_type: Any) -> bool:
    """Return whether one clang type is top-level const-qualified."""

    is_const_qualified = getattr(clang_type, "is_const_qualified", None)
    if callable(is_const_qualified):
        return bool(is_const_qualified())
    return False


def _get_pointee_type(clang_type: Any) -> Any:
    """Return the pointee or referred type of one pointer/reference clang type."""

    get_pointee = getattr(clang_type, "get_pointee", None)
    if callable(get_pointee):
        return get_pointee()
    return None


def _get_array_element_type(clang_type: Any) -> Any:
    """Return the element type of one clang array type."""

    get_array_element_type = getattr(clang_type, "get_array_element_type", None)
    if callable(get_array_element_type):
        return get_array_element_type()
    return None


def _get_array_extent(clang_type: Any) -> str | None:
    """Return the rendered extent of one clang array type, if any."""

    get_array_size = getattr(clang_type, "get_array_size", None)
    if callable(get_array_size):
        extent = get_array_size()
        if isinstance(extent, int) and extent >= 0:
            return str(extent)
    return None


def _get_result_type(clang_type: Any) -> Any:
    """Return the result type of one clang function type."""

    get_result = getattr(clang_type, "get_result", None)
    if callable(get_result):
        return get_result()
    return None


def _get_argument_types(clang_type: Any) -> list[Any]:
    """Return the argument types of one clang function type."""

    argument_types = getattr(clang_type, "argument_types", None)
    if callable(argument_types):
        return list(argument_types())
    return []


def _is_function_variadic(clang_type: Any) -> bool:
    """Return whether one clang function type is variadic."""

    is_function_variadic = getattr(clang_type, "is_function_variadic", None)
    if callable(is_function_variadic):
        return bool(is_function_variadic())
    return False


def _get_canonical_type(clang_type: Any) -> Any:
    """Return the canonical form of one clang type, if available."""

    get_canonical = getattr(clang_type, "get_canonical", None)
    if callable(get_canonical):
        return get_canonical()
    return None


def _same_type_identity(left: Any, right: Any) -> bool:
    """Return whether two clang type objects look like the same semantic type."""

    if left is right:
        return True
    return (
        _type_kind_name(left) == _type_kind_name(right)
        and _type_spelling(left) == _type_spelling(right)
    )
