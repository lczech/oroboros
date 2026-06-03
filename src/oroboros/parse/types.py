from __future__ import annotations

"""Translate clang type objects into the semantic C++ type model."""

import re
from typing import TYPE_CHECKING, Any

from clang.cindex import CursorKind, TypeKind

from ..diagnostics import Diagnostic
from ..model import (
    ArrayCppType,
    BuiltinCppType,
    CppNonTypeTemplateArgument,
    CppObservedTemplateInstance,
    CppTemplateArgument,
    CppTypeTemplateArgument,
    CppType,
    FunctionCppType,
    LValueReferenceCppType,
    NamedCppType,
    PointerCppType,
    RValueReferenceCppType,
    TemplateInstanceCppType,
)
from ..model.type import cpp_builtin_kind_from_spelling
from .cursor_data import cursor_source_location

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Public Type Builder
# ==================================================================================================


def build_cpp_type(
    clang_type: Any,
    *,
    context: BuildContext | None = None,
    source_cursor: Any | None = None,
    record_observations: bool = True,
) -> CppType | None:
    """Convert one clang type object into the structured semantic type model."""

    if clang_type is None:
        return None

    return _build_cpp_type(
        clang_type,
        allow_canonical=True,
        context=context,
        source_cursor=source_cursor,
        record_observations=record_observations,
    )


def _build_cpp_type(
    clang_type: Any,
    *,
    allow_canonical: bool,
    context: BuildContext | None,
    source_cursor: Any | None,
    record_observations: bool = True,
) -> CppType | None:
    """Recursively convert one clang type while avoiding canonical recursion loops."""

    is_const = _call_optional_bool_method(clang_type, "is_const_qualified")

    builtin_kind = _clang_builtin_kind(clang_type)
    if builtin_kind is not None:
        return BuiltinCppType(kind=builtin_kind, is_const=is_const)

    if _type_kind_matches(clang_type, TypeKind.POINTER):
        return PointerCppType(
            pointee=_build_cpp_type(
                _call_optional_method(clang_type, "get_pointee"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
                record_observations=record_observations,
            ),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, TypeKind.LVALUEREFERENCE):
        return LValueReferenceCppType(
            referred=_build_cpp_type(
                _call_optional_method(clang_type, "get_pointee"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
                record_observations=record_observations,
            ),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, TypeKind.RVALUEREFERENCE):
        return RValueReferenceCppType(
            referred=_build_cpp_type(
                _call_optional_method(clang_type, "get_pointee"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
                record_observations=record_observations,
            ),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, *_ARRAY_KINDS):
        return ArrayCppType(
            element_type=_build_cpp_type(
                _call_optional_method(clang_type, "get_array_element_type"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
                record_observations=record_observations,
            ),
            extent=_get_array_extent(clang_type),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, *_FUNCTION_KINDS):
        return FunctionCppType(
            return_type=_build_cpp_type(
                _call_optional_method(clang_type, "get_result"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
                record_observations=record_observations,
            ),
            parameters=[
                _build_cpp_type(
                    parameter_type,
                    allow_canonical=allow_canonical,
                    context=context,
                    source_cursor=source_cursor,
                    record_observations=record_observations,
                )
                for parameter_type in _call_optional_method(clang_type, "argument_types", [])
            ],
            is_variadic=_call_optional_bool_method(clang_type, "is_function_variadic"),
            is_const=is_const,
        )

    spelling = _normalize_name_type_spelling(
        _type_spelling(clang_type),
        is_const=is_const,
    )
    if "<" in spelling:
        # Record the observation from the clang type spelling directly — independent of
        # how we build the type object below.  This is the authoritative path: spellings
        # are always correct through alias chains, dependent contexts, and zero-arg forms.
        if record_observations:
            _record_observed_template_instance(clang_type, context, source_cursor=source_cursor)
        # Build the structured TemplateInstanceCppType from spelling.  Falls through to
        # NamedCppType for zero-argument spellings such as Box<> (no arguments to split).
        template_instance = _parse_template_instance_spelling(spelling, is_const=is_const)
        if template_instance is not None:
            # Enrich arguments with clang's direct arg types to restore declaration links
            # and non-type type annotations.  Only applies to class template instantiations
            # (where libclang exposes direct arg types); alias template instantiations
            # return 0 direct args and are intentionally left as spelling-built types.
            direct_argument_types = _template_argument_types(clang_type)
            for index, direct_type in enumerate(direct_argument_types):
                if index >= len(template_instance.arguments):
                    break
                if direct_type is None or _type_kind_matches(direct_type, TypeKind.INVALID):
                    continue
                arg = template_instance.arguments[index]
                if isinstance(arg, CppTypeTemplateArgument):
                    enriched = _build_cpp_type(
                        direct_type,
                        allow_canonical=allow_canonical,
                        context=context,
                        source_cursor=source_cursor,
                        record_observations=record_observations,
                    )
                    if enriched is not None:
                        template_instance.arguments[index] = CppTypeTemplateArgument(type=enriched)
                elif isinstance(arg, CppNonTypeTemplateArgument) and arg.type is None:
                    annotation = _build_cpp_type(
                        direct_type,
                        allow_canonical=True,
                        context=context,
                        source_cursor=None,
                        record_observations=record_observations,
                    )
                    if annotation is not None:
                        template_instance.arguments[index] = CppNonTypeTemplateArgument(
                            value=arg.value, type=annotation
                        )
            return template_instance

    canonical = None
    if allow_canonical:
        canonical_type = _call_optional_method(clang_type, "get_canonical")
        if canonical_type is not None and not _same_type_identity(clang_type, canonical_type):
            canonical = _build_cpp_type(
                canonical_type,
                allow_canonical=False,
                context=context,
                source_cursor=None,
                record_observations=record_observations,
            )

    named_type = NamedCppType(
        name=spelling,
        canonical=canonical,
        is_const=is_const,
    )
    _record_named_type_declaration_link(
        named_type,
        clang_type,
        context,
        source_cursor=source_cursor,
    )
    return named_type


# ==================================================================================================
#     Spelling-Based Syntax Recovery
# ==================================================================================================


def _build_type_from_spelling(spelling: str) -> CppType:
    """Build one fallback semantic type from a plain C++ spelling fragment."""

    normalized = spelling.strip()

    # Peel top-level wrapper constness before normalizing inner named-type spellings.
    if normalized.endswith(" const"):
        without_const = normalized[:-len(" const")].rstrip()

        if without_const.endswith("&&"):
            return RValueReferenceCppType(
                referred = _build_type_from_spelling(without_const[:-2]),
                is_const = True,
            )

        if without_const.endswith("&"):
            return LValueReferenceCppType(
                referred = _build_type_from_spelling(without_const[:-1]),
                is_const = True,
            )

        if without_const.endswith("*"):
            return PointerCppType(
                pointee = _build_type_from_spelling(without_const[:-1]),
                is_const = True,
            )

    if normalized.endswith("&&"):
        return RValueReferenceCppType(
            referred = _build_type_from_spelling(normalized[:-2]),
            is_const = False,
        )

    if normalized.endswith("&"):
        return LValueReferenceCppType(
            referred = _build_type_from_spelling(normalized[:-1]),
            is_const = False,
        )

    if normalized.endswith("*"):
        return PointerCppType(
            pointee = _build_type_from_spelling(normalized[:-1]),
            is_const = False,
        )

    is_const = normalized.startswith("const ") or normalized.endswith(" const")
    normalized = _normalize_name_type_spelling(normalized, is_const=is_const)

    template_instance = _parse_template_instance_spelling(normalized, is_const=is_const)
    if template_instance is not None:
        return template_instance

    builtin_kind = cpp_builtin_kind_from_spelling(normalized)
    if builtin_kind is not None:
        return BuiltinCppType(kind=builtin_kind, is_const=is_const)

    return NamedCppType(name=normalized, is_const=is_const)


def build_template_argument_from_spelling(spelling: str) -> CppTemplateArgument:
    """Build one structured template argument from one source spelling fragment."""

    normalized = spelling.strip()
    if _looks_like_non_type_template_argument(normalized):
        return CppNonTypeTemplateArgument(value=normalized)

    return CppTypeTemplateArgument(
        type=_build_type_from_spelling(normalized),
    )


def _normalize_name_type_spelling(
    spelling: str,
    *,
    is_const: bool,
) -> str:
    """Normalize one named-type spelling so top-level const lives only in `is_const`."""

    normalized = spelling.strip()
    if not is_const:
        return normalized

    if normalized.startswith("const "):
        return normalized[len("const "):].strip()

    if normalized.endswith(" const"):
        return normalized[:-len(" const")].strip()

    return normalized


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
        arguments=[build_template_argument_from_spelling(s) for s in argument_spellings],
        is_const=is_const,
    )


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


def _template_argument_types(clang_type: Any) -> list[Any]:
    """Return clang template argument types when libclang exposes them."""

    get_argument_count = getattr(clang_type, "get_num_template_arguments", None)
    get_argument_type = getattr(clang_type, "get_template_argument_type", None)
    if not callable(get_argument_count) or not callable(get_argument_type):
        return []

    argument_count = get_argument_count()
    if not isinstance(argument_count, int) or argument_count < 0:
        return []

    argument_types: list[Any] = []
    for index in range(argument_count):
        argument_types.append(get_argument_type(index))

    return argument_types


def _looks_like_non_type_template_argument(spelling: str) -> bool:
    """Return whether one template-argument spelling looks like a value expression."""

    normalized = spelling.strip()
    if not normalized:
        return False

    if normalized in {"true", "false", "nullptr"}:
        return True

    if _INTEGER_LITERAL_RE.fullmatch(normalized):
        return True

    if _FLOAT_LITERAL_RE.fullmatch(normalized):
        return True

    if _CHAR_LITERAL_RE.fullmatch(normalized):
        return True

    if _STRING_LITERAL_RE.fullmatch(normalized):
        return True

    return False


_INTEGER_LITERAL_RE = re.compile(
    r"""
    [+-]?
    (?:
        0[xX][0-9A-Fa-f]+ |
        0[bB][01]+ |
        0[0-7]* |
        [1-9][0-9]*
    )
    (?:[uU](?:ll|LL|l|L)?|(?:ll|LL|l|L)[uU]?)?
    """,
    re.VERBOSE,
)

_FLOAT_LITERAL_RE = re.compile(
    r"""
    [+-]?
    (?:
        (?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)? |
        [0-9]+[eE][+-]?[0-9]+
    )
    [fFlL]?
    """,
    re.VERBOSE,
)

_CHAR_LITERAL_RE = re.compile(r"(?:u8|u|U|L)?'(?:\\.|[^'\\])+'")
_STRING_LITERAL_RE = re.compile(r'(?:u8|u|U|L)?\"(?:\\.|[^\"\\])*\"')




# ==================================================================================================
#     Clang Type Introspection
# ==================================================================================================


def _clang_builtin_kind(clang_type: Any) -> str | None:
    """Return one semantic builtin kind for one clang builtin type."""

    actual_kind = getattr(clang_type, "kind", None)
    if actual_kind is None:
        return None

    return _CLANG_BUILTIN_KIND_MAP.get(actual_kind)


def _type_kind_matches(clang_type: Any, *expected_kinds: Any) -> bool:
    """Return whether one clang type matches any expected libclang type kinds."""

    actual_kind = getattr(clang_type, "kind", None)
    if actual_kind is None:
        return False
    return actual_kind in expected_kinds


_CLANG_BUILTIN_KIND_MAP: dict[Any, str] = {
    TypeKind.VOID: "void",
    TypeKind.NULLPTR: "nullptr_t",
    TypeKind.BOOL: "bool",
    TypeKind.CHAR_U: "char",
    TypeKind.UCHAR: "unsigned_char",
    TypeKind.CHAR16: "char16_t",
    TypeKind.CHAR32: "char32_t",
    TypeKind.USHORT: "unsigned_short",
    TypeKind.UINT: "unsigned_int",
    TypeKind.ULONG: "unsigned_long",
    TypeKind.ULONGLONG: "unsigned_long_long",
    TypeKind.CHAR_S: "char",
    TypeKind.SCHAR: "signed_char",
    TypeKind.WCHAR: "wchar_t",
    TypeKind.SHORT: "short",
    TypeKind.INT: "int",
    TypeKind.LONG: "long",
    TypeKind.LONGLONG: "long_long",
    TypeKind.FLOAT: "float",
    TypeKind.DOUBLE: "double",
    TypeKind.LONGDOUBLE: "long_double",
}

_ARRAY_KINDS = frozenset({TypeKind.CONSTANTARRAY, TypeKind.INCOMPLETEARRAY})
_FUNCTION_KINDS = frozenset({TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO})


def _type_kind_name(clang_type: Any) -> str:
    """Return one normalized libclang type-kind name.

    Libclang exposes these enum names in uppercase forms such as `POINTER`,
    `FUNCTIONPROTO`, and `LVALUEREFERENCE`. The parser mainly matches against
    the enum members themselves, while this helper keeps reporting and test
    fallbacks readable.
    """

    kind = getattr(clang_type, "kind", None)
    name = getattr(kind, "name", None)
    if name is not None:
        return str(name)
    return str(kind)


def _type_spelling(clang_type: Any) -> str:
    """Return one normalized type spelling string."""

    return str(getattr(clang_type, "spelling", "")).strip()


# ==================================================================================================
#     Declaration Recording
# ==================================================================================================


def _call_optional_method(clang_type: Any, method_name: str, default: Any = None) -> Any:
    """Call one optional libclang type method, returning a default when absent."""

    method = getattr(clang_type, method_name, None)
    if callable(method):
        return method()
    return default


def _call_optional_bool_method(clang_type: Any, method_name: str) -> bool:
    """Call one optional libclang type predicate and normalize it to `bool`."""

    return bool(_call_optional_method(clang_type, method_name, False))


def _record_named_type_declaration_link(
    cpp_type: NamedCppType,
    clang_type: Any,
    context: BuildContext | None,
    *,
    source_cursor: Any | None = None,
) -> None:
    """Capture one referenced declaration USR for a named type when available."""

    if context is None:
        return

    declaration_cursor = _call_optional_method(clang_type, "get_declaration")
    if declaration_cursor is None:
        return

    declaration_location = cursor_source_location(declaration_cursor)
    must_resolve_in_active_headers = False
    if declaration_location is not None:
        declaration_file = declaration_location.file.resolve()
        if (
            declaration_file not in context.active_headers
            and declaration_file in context.known_project_headers
        ):
            _record_inactive_project_type_reference_warning(
                cpp_type,
                declaration_location=declaration_location,
                source_cursor=source_cursor,
                context=context,
            )
            return
        must_resolve_in_active_headers = declaration_file in context.active_headers

    declaration_usr = _cursor_usr(declaration_cursor)
    if declaration_usr is None:
        return

    from .build_model import PendingTypeDeclarationLink

    context.pending_type_declaration_links.append(
        PendingTypeDeclarationLink(
            cpp_type=cpp_type,
            declaration_usr=declaration_usr,
            declaration_cursor=declaration_cursor,
            source_location=cursor_source_location(source_cursor) if source_cursor is not None else None,
            declaration_location=declaration_location,
            must_resolve_in_active_headers=must_resolve_in_active_headers,
        )
    )


def _record_inactive_project_type_reference_warning(
    cpp_type: NamedCppType,
    *,
    declaration_location: Any,
    source_cursor: Any | None,
    context: BuildContext,
) -> None:
    """Warn when an active declaration references a known inactive project type."""

    use_location = cursor_source_location(source_cursor) if source_cursor is not None else None
    warning = (
        f"Active declaration references known project type {cpp_type.name!r} "
        "from an inactive project header; "
        "preserving the type spelling without materializing that declaration."
    )
    locations = []
    if use_location is not None:
        locations.append(use_location)
    if declaration_location is not None:
        locations.append(declaration_location)
    context.report.add(
        Diagnostic(
            severity="warning",
            stage="parse",
            code="parse.inactive_project_type_reference",
            message=warning,
            locations=locations,
        )
    )


def _record_observed_template_instance(
    clang_type: Any,
    context: BuildContext | None,
    *,
    source_cursor: Any | None,
) -> None:
    """Record one template instantiation observation and recurse into argument types."""

    if context is None:
        return

    _record_one_observed_template_instance(clang_type, context, source_cursor=source_cursor)

    # Recurse into direct argument types so that nested template instantiations
    # (e.g. Vec<Leaf> inside Container<Vec<Leaf>>) are also observed.
    for arg_type in _template_argument_types(clang_type):
        _record_observed_template_instances_in_clang_type(arg_type, context, source_cursor=source_cursor)


def _record_one_observed_template_instance(
    clang_type: Any,
    context: BuildContext,
    *,
    source_cursor: Any | None,
) -> None:
    """Append one spelling-keyed observation to the matching template family."""

    spelling = _type_spelling(clang_type)
    template_name, argument_text = _split_template_spelling(spelling)
    if template_name is None:
        return

    # Resolve the template cursor: prefer clang's specialized_template, fall back to a
    # TEMPLATE_REF child of the source cursor (needed for alias template instantiations
    # where specialized_template is absent or points to the wrong family).
    template_cursor = _specialized_template_cursor(clang_type)
    if source_cursor is not None and (
        template_cursor is None
        or not _cursor_terminal_name_matches(template_cursor, template_name)
    ):
        source_template_cursor = _find_template_ref_cursor(template_name, source_cursor)
        if source_template_cursor is not None:
            template_cursor = source_template_cursor
    if template_cursor is None:
        return

    from .element_registry import resolve_registered_template_family

    template_family = resolve_registered_template_family(template_cursor, context)
    if template_family is None or not hasattr(template_family, "declaration"):
        return

    declaration = getattr(template_family, "declaration", None)
    if declaration is None or not hasattr(declaration, "cpp"):
        return

    argument_spellings = _split_template_arguments(argument_text) if argument_text is not None else []
    observation_location = cursor_source_location(source_cursor) if source_cursor is not None else None

    # Build dedup key from the canonical type so that Box<int> and Box<int, double>
    # (where double is the default) collapse to one observation.  Only use canonical
    # args when the canonical type refers to the same template family; otherwise (alias
    # expansion would change the family name) fall back to source argument spellings.
    dedup_key = _canonical_dedup_key(clang_type, template_name, argument_spellings)

    observed_instances = declaration.cpp.observed_instances
    for inst in observed_instances:
        if tuple(inst.argument_spellings) == dedup_key:
            if inst.instantiation_spelling is None:
                inst.instantiation_spelling = spelling
            if observation_location is not None and observation_location not in inst.locations:
                inst.locations.append(observation_location)
            return

    observed_instances.append(
        CppObservedTemplateInstance(
            instantiation_spelling=spelling,
            argument_spellings=list(dedup_key),
            locations=[] if observation_location is None else [observation_location],
        )
    )


def _record_observed_template_instances_in_clang_type(
    clang_type: Any,
    context: BuildContext,
    *,
    source_cursor: Any | None,
) -> None:
    """Walk one clang type to record any nested template instantiation observations."""

    if clang_type is None:
        return

    spelling = _type_spelling(clang_type)
    if "<" in spelling:
        _record_observed_template_instance(clang_type, context, source_cursor=source_cursor)
        return

    kind = getattr(clang_type, "kind", None)

    if kind in {TypeKind.POINTER, TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE}:
        _record_observed_template_instances_in_clang_type(
            _call_optional_method(clang_type, "get_pointee"),
            context,
            source_cursor=source_cursor,
        )
        return

    if kind in _ARRAY_KINDS:
        _record_observed_template_instances_in_clang_type(
            _call_optional_method(clang_type, "get_array_element_type"),
            context,
            source_cursor=source_cursor,
        )
        return

    if kind in _FUNCTION_KINDS:
        _record_observed_template_instances_in_clang_type(
            _call_optional_method(clang_type, "get_result"),
            context,
            source_cursor=source_cursor,
        )
        for arg_type in _call_optional_method(clang_type, "argument_types", []):
            _record_observed_template_instances_in_clang_type(
                arg_type, context, source_cursor=source_cursor
            )


# ==================================================================================================
#     Template Introspection
# ==================================================================================================


def _find_template_ref_cursor(template_name: str, source_cursor: Any) -> Any | None:
    """Return a TEMPLATE_REF child of source_cursor matching the terminal template name."""

    terminal_name = template_name.split("::")[-1].strip()
    for child_cursor in _call_optional_method(source_cursor, "get_children", []):
        if getattr(child_cursor, "kind", None) != CursorKind.TEMPLATE_REF:
            continue
        if child_cursor.spelling != terminal_name:
            continue
        referenced_cursor = getattr(child_cursor, "referenced", None)
        if getattr(referenced_cursor, "kind", None) in {
            CursorKind.TYPE_ALIAS_TEMPLATE_DECL,
            CursorKind.CLASS_TEMPLATE,
            CursorKind.FUNCTION_TEMPLATE,
        }:
            return referenced_cursor
    return None


def _cursor_terminal_name_matches(cursor: Any, template_name: str) -> bool:
    """Return whether one cursor's spelling matches the terminal component of a template name."""

    cursor_name = getattr(cursor, "spelling", "").strip()
    terminal_name = template_name.split("::")[-1].strip()
    return bool(cursor_name) and cursor_name == terminal_name


def _canonical_dedup_key(
    clang_type: Any,
    template_name: str,
    source_spellings: list[str],
) -> tuple[str, ...]:
    """Return the canonical argument spellings for dedup across defaulted-arg variants.

    Box<int> and Box<int, double> (default U=double) canonicalize to the same spelling
    'Box<int, double>', so they share one observation entry.  For alias template
    instantiations the canonical type has a different family name (alias expansion), so
    we fall back to the source spellings to avoid cross-family collisions.
    """
    canonical = _call_optional_method(clang_type, "get_canonical")
    if canonical is None or _same_type_identity(clang_type, canonical):
        return tuple(source_spellings)
    canonical_spelling = _type_spelling(canonical)
    canonical_name, canonical_arg_text = _split_template_spelling(canonical_spelling)
    if canonical_name is None:
        return tuple(source_spellings)
    # Use canonical args only when the canonical type still belongs to the same family.
    if canonical_name.split("::")[-1] != template_name.split("::")[-1]:
        return tuple(source_spellings)
    canonical_args = _split_template_arguments(canonical_arg_text) if canonical_arg_text is not None else []
    # Do not use canonical args when they contain libclang's internal parameter-name
    # substitutions (e.g. "value-parameter-0-0") — these would erase the user's own
    # parameter names (e.g. "N", "is_const") that tests and users expect to see.
    if any("parameter-" in s for s in canonical_args):
        return tuple(source_spellings)
    return tuple(canonical_args)


def _specialized_template_cursor(clang_type: Any) -> Any | None:
    """Return the generic template cursor behind one concrete template-instantiated type."""

    declaration_cursor = _call_optional_method(clang_type, "get_declaration")
    if declaration_cursor is None:
        return None

    specialized_template = getattr(declaration_cursor, "specialized_template", None)
    if specialized_template is not None:
        return specialized_template

    get_specialized_cursor_template = getattr(declaration_cursor, "get_specialized_cursor_template", None)
    if callable(get_specialized_cursor_template):
        return get_specialized_cursor_template()

    return None


def _cursor_usr(cursor: Any) -> str | None:
    """Return one cursor USR when libclang exposes one for the entity."""

    get_usr = getattr(cursor, "get_usr", None)
    if not callable(get_usr):
        return None

    usr = get_usr()
    if not usr:
        return None
    return str(usr)


def _get_array_extent(clang_type: Any) -> str | None:
    """Return the rendered extent of one clang array type, if any."""

    get_array_size = getattr(clang_type, "get_array_size", None)
    if callable(get_array_size):
        extent = get_array_size()
        if isinstance(extent, int) and extent >= 0:
            return str(extent)
    return None


# ==================================================================================================
#     Type Identity Helpers
# ==================================================================================================


def _same_type_identity(left: Any, right: Any) -> bool:
    """Return whether two clang type objects look like the same semantic type."""

    if left is right:
        return True
    return (
        _type_kind_name(left) == _type_kind_name(right)
        and _type_spelling(left) == _type_spelling(right)
    )
