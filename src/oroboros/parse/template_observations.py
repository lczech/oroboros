from __future__ import annotations

"""Record raw template observation hints from declaration-surface clang types."""

from typing import TYPE_CHECKING, Any

from clang.cindex import CursorKind, TypeKind

from ..model import CppTemplateObservationHint
from .cursor_data import cursor_source_location
from .template_type_recovery import _split_template_spelling
from .types import (
    _ARRAY_KINDS,
    _FUNCTION_KINDS,
    _call_optional_method,
    _same_type_identity,
    _template_argument_types,
    _type_spelling,
)

if TYPE_CHECKING:
    from .build_model import BuildContext


def record_template_observation_hints_in_type(
    clang_type: Any,
    *,
    context: BuildContext | None,
    source_cursor: Any | None,
) -> None:
    """Record raw template observation hints from one declaration-surface type."""

    if context is None or source_cursor is None:
        return
    _record_template_observation_hints_in_clang_type(
        clang_type,
        context,
        source_cursor=source_cursor,
    )


def _record_template_observation_hints_in_clang_type(
    clang_type: Any,
    context: BuildContext,
    *,
    source_cursor: Any,
) -> None:
    """Walk one clang type and record any template spellings reachable from it."""

    if clang_type is None:
        return

    spelling = _type_spelling(clang_type)
    if "<" in spelling and _record_one_template_observation_hint(
        clang_type,
        context,
        source_cursor=source_cursor,
    ):
        for arg_type in _template_argument_types(clang_type):
            _record_template_observation_hints_in_clang_type(
                arg_type,
                context,
                source_cursor=source_cursor,
            )
        return

    kind = getattr(clang_type, "kind", None)

    if kind in {TypeKind.POINTER, TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE}:
        _record_template_observation_hints_in_clang_type(
            _call_optional_method(clang_type, "get_pointee"),
            context,
            source_cursor=source_cursor,
        )
        return

    if kind in _ARRAY_KINDS:
        _record_template_observation_hints_in_clang_type(
            _call_optional_method(clang_type, "get_array_element_type"),
            context,
            source_cursor=source_cursor,
        )
        return

    if kind in _FUNCTION_KINDS:
        _record_template_observation_hints_in_clang_type(
            _call_optional_method(clang_type, "get_result"),
            context,
            source_cursor=source_cursor,
        )
        for arg_type in _call_optional_method(clang_type, "argument_types", []):
            _record_template_observation_hints_in_clang_type(
                arg_type,
                context,
                source_cursor=source_cursor,
            )


def _record_one_template_observation_hint(
    clang_type: Any,
    context: BuildContext,
    *,
    source_cursor: Any,
) -> bool:
    """Append one normalized spelling hint to one confidently resolved template family."""

    spelling = _type_spelling(clang_type)
    template_name, argument_text = _split_template_spelling(spelling)
    if template_name is None or argument_text is None:
        return False

    from .element_registry import resolve_registered_template_family

    template_family = None
    source_template_cursor = _find_template_ref_cursor(template_name, source_cursor)
    if source_template_cursor is not None:
        template_family = resolve_registered_template_family(source_template_cursor, context)

    if template_family is None:
        template_cursor = _specialized_template_cursor(clang_type)
        if template_cursor is None or not _cursor_terminal_name_matches(template_cursor, template_name):
            return False
        template_family = resolve_registered_template_family(template_cursor, context)

    if template_family is None or not hasattr(template_family, "declaration"):
        return False

    declaration = getattr(template_family, "declaration", None)
    if declaration is None or not hasattr(declaration, "cpp"):
        return False

    normalized_spelling = _normalize_template_observation_spelling(spelling)
    if not normalized_spelling:
        return False

    observation_location = cursor_source_location(source_cursor)
    hints = declaration.cpp.template_observation_hints
    for hint in hints:
        if hint.spelling != normalized_spelling:
            continue
        if observation_location is not None and observation_location not in hint.locations:
            hint.locations.append(observation_location)
        return True

    hints.append(
        CppTemplateObservationHint(
            spelling=normalized_spelling,
            locations=[] if observation_location is None else [observation_location],
        )
    )
    return True


def _normalize_template_observation_spelling(spelling: str) -> str:
    """Normalize one recorded template spelling by removing whitespace."""

    return "".join(spelling.split())


def _find_template_ref_cursor(template_name: str, source_cursor: Any) -> Any | None:
    """Return one unique TEMPLATE_REF child matching one terminal template name."""

    terminal_name = template_name.split("::")[-1].strip()
    matching_refs: list[Any] = []
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
            matching_refs.append(referenced_cursor)

    if len(matching_refs) != 1:
        return None
    return matching_refs[0]


def _cursor_terminal_name_matches(cursor: Any, template_name: str) -> bool:
    """Return whether one cursor's spelling matches one template name terminal."""

    cursor_name = getattr(cursor, "spelling", "").strip()
    terminal_name = template_name.split("::")[-1].strip()
    return bool(cursor_name) and cursor_name == terminal_name


def _specialized_template_cursor(clang_type: Any) -> Any | None:
    """Return the primary template cursor behind one concrete clang template type."""

    declaration_cursor = _call_optional_method(clang_type, "get_declaration")
    cursor = _specialized_template_cursor_from_declaration(declaration_cursor)
    if cursor is not None:
        return cursor

    canonical_type = _call_optional_method(clang_type, "get_canonical")
    if canonical_type is None or _same_type_identity(clang_type, canonical_type):
        return None

    canonical_declaration_cursor = _call_optional_method(canonical_type, "get_declaration")
    return _specialized_template_cursor_from_declaration(canonical_declaration_cursor)


def _specialized_template_cursor_from_declaration(declaration_cursor: Any) -> Any | None:
    """Return one specialized-template cursor from one declaration cursor."""

    if declaration_cursor is None:
        return None

    specialized_template = getattr(declaration_cursor, "specialized_template", None)
    if specialized_template is not None:
        return specialized_template

    get_specialized_cursor_template = getattr(declaration_cursor, "get_specialized_cursor_template", None)
    if callable(get_specialized_cursor_template):
        return get_specialized_cursor_template()

    return None
