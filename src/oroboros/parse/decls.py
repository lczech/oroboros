from __future__ import annotations

"""Minimal cursor walking that materializes semantic declarations from clang."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..model import (
    CppClass,
    CppClassBase,
    CppConstructor,
    CppElement,
    CppEnum,
    CppEnumerator,
    CppVisibility,
    CppFunction,
    CppLocationInfo,
    CppMethod,
    CppModule,
    CppNamespace,
    CppParameter,
    CppField,
    SourceLocation,
)
from .types import build_cpp_type


@dataclass(slots=True)
class ModuleBuildResult:
    """Store one built semantic module plus skipped parser cursor-kind counts."""

    module: CppModule
    skipped_kind_counts: dict[str, int] = field(default_factory=dict)

    @property
    def warnings(self) -> list[str]:
        """Return user-facing parser warnings derived from skipped cursor kinds."""

        if not self.skipped_kind_counts:
            return []

        rendered_counts = ", ".join(
            f"{kind_name} ({count})"
            for kind_name, count in self.skipped_kind_counts.items()
        )
        return [f"Skipped unsupported libclang cursor kinds: {rendered_counts}"]


@dataclass(slots=True)
class ModuleBuildContext:
    """Store shared mutable state while walking one translation unit."""

    active_headers: set[Path]
    skipped_kind_counts: Counter[str] = field(default_factory=Counter)


def build_module_from_translation_unit(
    translation_unit: Any,
    headers: Sequence[Path],
) -> ModuleBuildResult:
    """Build one semantic module from a parsed clang translation unit."""

    module = CppModule(name="module")
    normalized_headers = [header.resolve() for header in headers]
    module.cpp.header_files.extend(normalized_headers)

    context = ModuleBuildContext(
        active_headers={header.resolve() for header in normalized_headers},
    )
    root_cursor = translation_unit.cursor
    for child_cursor in root_cursor.get_children():
        _visit_cursor(child_cursor, module, context)

    return ModuleBuildResult(
        module=module,
        skipped_kind_counts=dict(sorted(context.skipped_kind_counts.items())),
    )


def _visit_cursor(
    cursor: Any,
    owner: CppElement,
    context: ModuleBuildContext,
) -> None:
    """Visit one clang cursor and attach any supported declaration to the model."""

    if not _cursor_is_from_active_header(cursor, context.active_headers):
        return

    clang_kind_name = _cursor_kind_name(cursor)

    if clang_kind_name == "NAMESPACE":
        namespace = _ensure_namespace(owner, cursor)
        _visit_children(cursor.get_children(), namespace, context)
        return

    if clang_kind_name in {"CLASS_DECL", "STRUCT_DECL"}:
        cls = CppClass(
            name=cursor.spelling,
            cpp=_build_class_cpp_facet(cursor, clang_kind_name),
        )
        attached = _attach_class(owner, cls)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, context)
        return

    if clang_kind_name == "ENUM_DECL":
        enum_ = CppEnum(
            name=cursor.spelling,
            cpp=_build_enum_cpp_facet(cursor),
        )
        attached = _attach_enum(owner, enum_)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, context)
        return

    if clang_kind_name == "ENUM_CONSTANT_DECL":
        enumerator = CppEnumerator(
            name=cursor.spelling,
            cpp=_build_enumerator_cpp_facet(cursor),
        )
        _attach_enumerator(owner, enumerator)
        return

    if clang_kind_name == "FUNCTION_DECL":
        function = CppFunction(
            name=cursor.spelling,
            cpp=_build_function_cpp_facet(cursor),
        )
        attached = _attach_function(owner, function)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, context)
        return

    if clang_kind_name == "CXX_METHOD":
        method = CppMethod(
            name=cursor.spelling,
            cpp=_build_method_cpp_facet(cursor),
        )
        attached = _attach_method(owner, method)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, context)
        return

    if clang_kind_name == "CONSTRUCTOR":
        constructor = CppConstructor(
            name=cursor.spelling,
            cpp=_build_constructor_cpp_facet(cursor),
        )
        attached = _attach_constructor(owner, constructor)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, context)
        return

    if clang_kind_name == "FIELD_DECL":
        field = CppField(
            name=cursor.spelling,
            cpp=_build_field_cpp_facet(cursor),
        )
        _attach_field(owner, field)
        return

    if clang_kind_name == "PARM_DECL":
        parameter = CppParameter(
            name=cursor.spelling,
            cpp=_build_parameter_cpp_facet(cursor),
        )
        _attach_parameter(owner, parameter)
        return

    if clang_kind_name in _IGNORED_CURSOR_KINDS:
        return

    context.skipped_kind_counts[clang_kind_name] += 1


def _visit_children(
    children: Iterable[Any],
    owner: CppElement,
    context: ModuleBuildContext,
) -> None:
    """Visit the children of one materialized semantic declaration node."""

    for child in children:
        _visit_cursor(child, owner, context)


_IGNORED_CURSOR_KINDS = frozenset({
    # Base specifiers are already collected structurally into `CppClassBase`.
    "CXX_BASE_SPECIFIER",
    # Access specifier labels do not become standalone semantic nodes.
    "CXX_ACCESS_SPEC_DECL",
    # Reference cursors are supporting links inside declarations, not semantic
    # declaration entities that should become standalone model nodes.
    "NAMESPACE_REF",
    "TYPE_REF",
})


def _ensure_namespace(owner: CppElement, cursor: Any) -> CppNamespace | None:
    """Return one existing or newly created namespace for one parser cursor."""

    namespace_name = cursor.spelling
    existing_namespaces = getattr(owner, "namespaces", None)
    if existing_namespaces is not None:
        for namespace in existing_namespaces:
            if namespace.name == namespace_name:
                return namespace

    namespace = CppNamespace(
        name=namespace_name,
        cpp=_build_namespace_cpp_facet(cursor),
    )
    attach_namespace = getattr(owner, "add_namespace", None)
    if attach_namespace is None:
        return None
    return attach_namespace(namespace)


def _attach_class(owner: CppElement, class_: CppClass) -> CppClass | None:
    attach = getattr(owner, "add_class", None)
    if attach is None:
        return None
    return attach(class_)


def _attach_enum(owner: CppElement, enum_: CppEnum) -> CppEnum | None:
    attach = getattr(owner, "add_enum", None)
    if attach is None:
        return None
    return attach(enum_)


def _attach_enumerator(owner: CppElement, enumerator: CppEnumerator) -> CppEnumerator | None:
    attach = getattr(owner, "add_enumerator", None)
    if attach is None:
        return None
    return attach(enumerator)


def _attach_function(owner: CppElement, function: CppFunction) -> CppFunction | None:
    attach = getattr(owner, "add_function", None)
    if attach is None:
        return None
    return attach(function)


def _attach_method(owner: CppElement, method: CppMethod) -> CppMethod | None:
    attach = getattr(owner, "add_method", None)
    if attach is None:
        return None
    return attach(method)


def _attach_constructor(owner: CppElement, constructor: CppConstructor) -> CppConstructor | None:
    attach = getattr(owner, "add_constructor", None)
    if attach is None:
        return None
    return attach(constructor)


def _attach_field(owner: CppElement, field: CppField) -> CppField | None:
    attach = getattr(owner, "add_field", None)
    if attach is None:
        return None
    return attach(field)


def _attach_parameter(owner: CppElement, parameter: CppParameter) -> CppParameter | None:
    attach = getattr(owner, "add_parameter", None)
    if attach is None:
        return None
    return attach(parameter)


def _build_namespace_cpp_facet(cursor: Any) -> Any:
    from ..model import CppNamespaceCppFacet

    return CppNamespaceCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
    )


def _build_class_cpp_facet(cursor: Any, clang_kind_name: str) -> Any:
    from ..model import CppClassCppFacet

    return CppClassCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
        kind="struct" if clang_kind_name == "STRUCT_DECL" else "class",
        visibility=_cursor_visibility(cursor),
        bases=_build_class_bases(cursor),
    )


def _build_enum_cpp_facet(cursor: Any) -> Any:
    from ..model import CppEnumCppFacet

    return CppEnumCppFacet(
        original_name=cursor.spelling or None,
        underlying_type=build_cpp_type(_cursor_enum_underlying_type(cursor)),
        location=_build_location_info(cursor),
        is_scoped=_cursor_is_scoped_enum(cursor),
        visibility=_cursor_visibility(cursor),
    )


def _build_enumerator_cpp_facet(cursor: Any) -> Any:
    from ..model import CppEnumeratorCppFacet

    return CppEnumeratorCppFacet(
        original_name=cursor.spelling or None,
        value_spelling=_cursor_enum_value_spelling(cursor),
        location=_build_location_info(cursor),
    )


def _build_function_cpp_facet(cursor: Any) -> Any:
    from ..model import CppFunctionCppFacet

    return CppFunctionCppFacet(
        original_name=cursor.spelling or None,
        return_type=build_cpp_type(getattr(cursor, "result_type", None)),
        location=_build_location_info(cursor),
        is_noexcept=_cursor_is_noexcept(cursor),
    )


def _build_method_cpp_facet(cursor: Any) -> Any:
    from ..model import CppMethodCppFacet

    return CppMethodCppFacet(
        original_name=cursor.spelling or None,
        return_type=build_cpp_type(getattr(cursor, "result_type", None)),
        location=_build_location_info(cursor),
        is_noexcept=_cursor_is_noexcept(cursor),
        is_const=_cursor_bool_method(cursor, "is_const_method"),
        is_static=_cursor_bool_method(cursor, "is_static_method"),
        is_virtual=_cursor_bool_method(cursor, "is_virtual_method"),
        is_pure_virtual=_cursor_bool_method(cursor, "is_pure_virtual_method"),
        visibility=_cursor_visibility(cursor),
    )


def _build_constructor_cpp_facet(cursor: Any) -> Any:
    from ..model import CppConstructorCppFacet

    return CppConstructorCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
        is_noexcept=_cursor_is_noexcept(cursor),
        visibility=_cursor_visibility(cursor),
    )


def _build_field_cpp_facet(cursor: Any) -> Any:
    from ..model import CppFieldCppFacet

    return CppFieldCppFacet(
        original_name=cursor.spelling or None,
        type=build_cpp_type(getattr(cursor, "type", None)),
        location=_build_location_info(cursor),
        is_static=_cursor_bool_method(cursor, "is_static_field"),
        visibility=_cursor_visibility(cursor),
    )


def _build_parameter_cpp_facet(cursor: Any) -> Any:
    from ..model import CppParameterCppFacet

    return CppParameterCppFacet(
        original_name=cursor.spelling or None,
        type=build_cpp_type(getattr(cursor, "type", None)),
        location=_build_location_info(cursor),
    )


def _build_location_info(cursor: Any) -> CppLocationInfo:
    """Convert one clang cursor location into the semantic provenance container."""

    location = _cursor_source_location(cursor)
    if location is None:
        return CppLocationInfo()
    return CppLocationInfo(
        primary=location,
        declarations=[location],
    )


def _cursor_source_location(cursor: Any) -> SourceLocation | None:
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


def _cursor_is_from_active_header(cursor: Any, active_headers: set[Path]) -> bool:
    """Return whether one cursor belongs to one of the selected active headers."""

    location = _cursor_source_location(cursor)
    if location is None:
        return False
    return location.file.resolve() in active_headers


def _cursor_kind_name(cursor: Any) -> str:
    """Return one normalized libclang cursor-kind name.

    Libclang exposes cursor kind enums with uppercase names like
    `FUNCTION_DECL`, `CLASS_DECL`, and `CXX_METHOD`, so the parser matches
    against those values directly.
    """

    kind = getattr(cursor, "kind", None)
    name = getattr(kind, "name", None)
    if name is not None:
        return str(name)
    return str(kind)


def _cursor_visibility(cursor: Any) -> CppVisibility | None:
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


def _cursor_bool_method(cursor: Any, method_name: str) -> bool:
    """Call one optional boolean libclang cursor method safely."""

    method = getattr(cursor, method_name, None)
    if callable(method):
        return bool(method())
    return False


def _cursor_is_noexcept(cursor: Any) -> bool:
    """Return whether one clang cursor represents a noexcept callable."""

    exception_spec_kind = getattr(cursor, "exception_specification_kind", None)
    kind_name = getattr(exception_spec_kind, "name", None)
    if kind_name in {"BASIC_NOEXCEPT", "COMPUTED_NOEXCEPT"}:
        return True
    return False


def _cursor_is_scoped_enum(cursor: Any) -> bool:
    """Return whether one clang enum cursor is scoped."""

    is_scoped_enum = getattr(cursor, "is_scoped_enum", None)
    if callable(is_scoped_enum):
        return bool(is_scoped_enum())
    return False


def _cursor_enum_underlying_type(cursor: Any) -> Any:
    """Return one enum cursor's underlying type when libclang exposes it."""

    enum_type = getattr(cursor, "enum_type", None)
    if enum_type is not None:
        return enum_type

    underlying_enum_type = getattr(cursor, "underlying_enum_type", None)
    if callable(underlying_enum_type):
        return underlying_enum_type()

    return None


def _cursor_enum_value_spelling(cursor: Any) -> str | None:
    """Return one enumerator cursor value in textual form when available."""

    enum_value = getattr(cursor, "enum_value", None)
    if enum_value is None:
        return None
    return str(enum_value)


def _build_class_bases(cursor: Any) -> list[CppClassBase]:
    """Collect direct base-class relationships declared on one class cursor."""

    bases: list[CppClassBase] = []
    for child_cursor in cursor.get_children():
        if _cursor_kind_name(child_cursor) != "CXX_BASE_SPECIFIER":
            continue

        base_type = build_cpp_type(getattr(child_cursor, "type", None))
        if base_type is None:
            continue

        bases.append(
            CppClassBase(
                type=base_type,
                visibility=_cursor_visibility(child_cursor),
                is_virtual=_cursor_bool_method(child_cursor, "is_virtual_base"),
            )
        )

    return bases
