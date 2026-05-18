from __future__ import annotations

"""Minimal cursor walking that materializes semantic declarations from clang."""

from pathlib import Path
from typing import Any, Iterable, Sequence

from ..model import (
    CppClass,
    CppConstructor,
    CppElement,
    CppEnum,
    CppEnumerator,
    CppFunction,
    CppLocationInfo,
    CppMethod,
    CppModule,
    CppNamespace,
    CppParameter,
    CppField,
    SourceLocation,
)


def build_module_from_translation_unit(
    translation_unit: Any,
    headers: Sequence[Path],
) -> CppModule:
    """Build one semantic module from a parsed clang translation unit."""

    module = CppModule(name="module")
    normalized_headers = [header.resolve() for header in headers]
    module.cpp.header_files.extend(normalized_headers)

    active_header_set = {header.resolve() for header in normalized_headers}
    root_cursor = translation_unit.cursor
    for child_cursor in root_cursor.get_children():
        _visit_cursor(child_cursor, module, active_header_set)

    return module


def _visit_cursor(
    cursor: Any,
    owner: CppElement,
    active_headers: set[Path],
) -> None:
    """Visit one clang cursor and attach any supported declaration to the model."""

    if not _cursor_is_from_active_header(cursor, active_headers):
        return

    kind_name = _cursor_kind_name(cursor)

    if kind_name == "NAMESPACE":
        namespace = _ensure_namespace(owner, cursor)
        _visit_children(cursor.get_children(), namespace, active_headers)
        return

    if kind_name in {"CLASS_DECL", "STRUCT_DECL"}:
        cls = CppClass(
            name=cursor.spelling,
            cpp=_build_class_cpp_facet(cursor, kind_name),
        )
        attached = _attach_class(owner, cls)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, active_headers)
        return

    if kind_name == "ENUM_DECL":
        enum_ = CppEnum(
            name=cursor.spelling,
            cpp=_build_enum_cpp_facet(cursor),
        )
        attached = _attach_enum(owner, enum_)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, active_headers)
        return

    if kind_name == "ENUM_CONSTANT_DECL":
        enumerator = CppEnumerator(
            name=cursor.spelling,
            cpp=_build_enumerator_cpp_facet(cursor),
        )
        _attach_enumerator(owner, enumerator)
        return

    if kind_name == "FUNCTION_DECL":
        function = CppFunction(
            name=cursor.spelling,
            cpp=_build_function_cpp_facet(cursor),
        )
        attached = _attach_function(owner, function)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, active_headers)
        return

    if kind_name == "CXX_METHOD":
        method = CppMethod(
            name=cursor.spelling,
            cpp=_build_method_cpp_facet(cursor),
        )
        attached = _attach_method(owner, method)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, active_headers)
        return

    if kind_name == "CONSTRUCTOR":
        constructor = CppConstructor(
            name=cursor.spelling,
            cpp=_build_constructor_cpp_facet(cursor),
        )
        attached = _attach_constructor(owner, constructor)
        if attached is not None:
            _visit_children(cursor.get_children(), attached, active_headers)
        return

    if kind_name == "FIELD_DECL":
        field = CppField(
            name=cursor.spelling,
            cpp=_build_field_cpp_facet(cursor),
        )
        _attach_field(owner, field)
        return

    if kind_name == "PARM_DECL":
        parameter = CppParameter(
            name=cursor.spelling,
            cpp=_build_parameter_cpp_facet(cursor),
        )
        _attach_parameter(owner, parameter)


def _visit_children(
    children: Iterable[Any],
    owner: CppElement,
    active_headers: set[Path],
) -> None:
    """Visit the children of one materialized semantic declaration node."""

    for child in children:
        _visit_cursor(child, owner, active_headers)


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


def _build_class_cpp_facet(cursor: Any, kind_name: str) -> Any:
    from ..model import CppClassCppFacet

    return CppClassCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
        kind="struct" if kind_name == "STRUCT_DECL" else "class",
    )


def _build_enum_cpp_facet(cursor: Any) -> Any:
    from ..model import CppEnumCppFacet

    return CppEnumCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
    )


def _build_enumerator_cpp_facet(cursor: Any) -> Any:
    from ..model import CppEnumeratorCppFacet

    return CppEnumeratorCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
    )


def _build_function_cpp_facet(cursor: Any) -> Any:
    from ..model import CppFunctionCppFacet

    return CppFunctionCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
    )


def _build_method_cpp_facet(cursor: Any) -> Any:
    from ..model import CppMethodCppFacet

    return CppMethodCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
    )


def _build_constructor_cpp_facet(cursor: Any) -> Any:
    from ..model import CppConstructorCppFacet

    return CppConstructorCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
    )


def _build_field_cpp_facet(cursor: Any) -> Any:
    from ..model import CppFieldCppFacet

    return CppFieldCppFacet(
        original_name=cursor.spelling or None,
        location=_build_location_info(cursor),
    )


def _build_parameter_cpp_facet(cursor: Any) -> Any:
    from ..model import CppParameterCppFacet

    return CppParameterCppFacet(
        original_name=cursor.spelling or None,
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
    """Return one normalized libclang cursor-kind name."""

    kind = getattr(cursor, "kind", None)
    name = getattr(kind, "name", None)
    if name is not None:
        return str(name)
    return str(kind)
