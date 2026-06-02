from __future__ import annotations

"""Process concrete libclang declaration cursors into semantic model elements."""

from typing import TYPE_CHECKING, AbstractSet, Any, Iterable

from clang.cindex import CursorKind

from ..model import (
    CppAlias,
    CppAliasTemplate,
    CppAliasTemplateDeclaration,
    CppClass,
    CppClassMembers,
    CppClassTemplate,
    CppClassTemplateDeclaration,
    CppConstructor,
    CppDestructor,
    CppElement,
    CppEnum,
    CppEnumerator,
    CppFunction,
    CppFunctionTemplate,
    CppFunctionTemplateDeclaration,
    CppMethod,
    CppMethodTemplate,
    CppMethodTemplateDeclaration,
    CppModule,
    CppNamespace,
    CppObservedTemplateInstance,
    CppParameter,
    CppTemplateArgument,
    CppVariable,
)
from ..model.template_ import _template_argument_key
from ..model.type import TemplateInstanceCppType
from .extract_cpp_facets import (
    extract_alias_cpp_facet,
    extract_alias_template_declaration_cpp_facet,
    extract_class_cpp_facet,
    extract_class_template_declaration_cpp_facet,
    extract_constructor_cpp_facet,
    extract_destructor_cpp_facet,
    extract_enum_cpp_facet,
    extract_enumerator_cpp_facet,
    extract_variable_cpp_facet,
    extract_function_cpp_facet,
    extract_function_template_declaration_cpp_facet,
    extract_method_cpp_facet,
    extract_method_template_declaration_cpp_facet,
    extract_parameter_cpp_facet,
)
from .extract_templates import extract_template_parameters
from .merge_declarations import (
    merge_alias_declaration,
    merge_alias_template_declaration,
    merge_callable_parameter_children,
    merge_class_declaration,
    merge_class_template_declaration,
    merge_constructor_declaration,
    merge_destructor_declaration,
    merge_enum_declaration,
    merge_enumerator_declaration,
    merge_field_declaration,
    merge_function_declaration,
    merge_function_template_declaration,
    merge_method_declaration,
    merge_method_template_declaration,
    merge_parameter_declaration,
    merge_templated_constructor_declaration,
    merge_variable_declaration,
)
from .merge_properties import describe_cursor_entity, record_semantic_warning
from .cursor_data import cursor_source_location, cursor_usr
from .element_registry import (
    lookup_registered_element,
    register_element_for_cursor,
    resolve_class_semantic_owner,
)
from .result import ParserInvariantError
from .types import build_cpp_type

if TYPE_CHECKING:
    from .build_model import BuildContext


_TEMPLATE_PARAMETER_CURSOR_KINDS = frozenset({
    CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
    CursorKind.TEMPLATE_TEMPLATE_PARAMETER,
    CursorKind.TEMPLATE_TYPE_PARAMETER,
})
_PARAMETER_CURSOR_KINDS = frozenset({
    CursorKind.PARM_DECL,
})


# ==================================================================================================
#     Process Cursors
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Class
# ------------------------------------------------------------------------------


def process_class_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one class declaration and recurse into its children."""

    if _handle_explicit_class_template_specialization(cursor, owner, context):
        return

    candidate_cpp = extract_class_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppClass)
    if existing is not None:
        merge_class_declaration(existing, candidate_cpp, cursor, context)
        _visit_children(cursor.get_children(), existing, context)
        return

    cls = CppClass(name=cursor.spelling, cpp=candidate_cpp)
    attached = owner.add_class(cls)
    register_element_for_cursor(cursor, attached, context)
    visit_declaration_children(cursor.get_children(), attached, context)


def process_constructor_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one constructor declaration and recurse into its children."""

    candidate_cpp = extract_constructor_cpp_facet(cursor, context=context)
    constructor_name = _constructor_name_for_owner(owner, cursor)
    candidate_cpp.original_name = constructor_name
    existing = lookup_registered_element(cursor, context, CppConstructor)
    if existing is not None:
        merge_constructor_declaration(existing, candidate_cpp, cursor, context)
        _merge_and_visit_callable_children(
            existing,
            cursor.get_children(),
            context,
            excluded_kinds=_PARAMETER_CURSOR_KINDS,
        )
        return

    constructor = CppConstructor(name=constructor_name, cpp=candidate_cpp)
    attached = owner.add_constructor(constructor)
    _refresh_scope_overload_indices(owner, "constructors")
    register_element_for_cursor(cursor, attached, context)
    visit_callable_children_and_docs(cursor.get_children(), attached, context)


def process_destructor_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one destructor declaration."""

    candidate_cpp = extract_destructor_cpp_facet(cursor, context=context)
    destructor_name = _destructor_name_for_owner(owner, cursor)
    candidate_cpp.original_name = destructor_name
    existing = lookup_registered_element(cursor, context, CppDestructor)
    if existing is not None:
        merge_destructor_declaration(existing, candidate_cpp, cursor, context)
        _visit_children(
            cursor.get_children(),
            existing,
            context,
            excluded_kinds=_PARAMETER_CURSOR_KINDS,
        )
        return

    destructor = CppDestructor(name=destructor_name, cpp=candidate_cpp)
    attached = owner.add_destructor(destructor)
    register_element_for_cursor(cursor, attached, context)
    visit_declaration_children(
        cursor.get_children(),
        attached,
        context,
        excluded_kinds=_PARAMETER_CURSOR_KINDS,
    )


def process_method_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one method declaration and recurse into its children."""

    candidate_cpp = extract_method_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppMethod)
    if existing is not None:
        merge_method_declaration(existing, candidate_cpp, cursor, context)
        _merge_and_visit_callable_children(
            existing,
            cursor.get_children(),
            context,
            excluded_kinds=_PARAMETER_CURSOR_KINDS,
        )
        return

    method = CppMethod(name=cursor.spelling, cpp=candidate_cpp)
    attached = owner.add_method(method)
    _refresh_scope_overload_indices(owner, "methods")
    register_element_for_cursor(cursor, attached, context)
    visit_callable_children_and_docs(cursor.get_children(), attached, context)


def process_field_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one instance-variable declaration."""

    candidate_cpp = extract_variable_cpp_facet(cursor, context=context, kind="member_variable")
    existing = lookup_registered_element(cursor, context, CppVariable)
    if existing is not None:
        merge_field_declaration(context, cursor, existing)
        return

    variable = CppVariable(name=cursor.spelling, cpp=candidate_cpp)
    attached = owner.add_variable(variable)
    register_element_for_cursor(cursor, attached, context)


def process_variable_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one non-local `VAR_DECL` declaration."""

    from ..model import CppModule, CppNamespace

    if isinstance(owner, CppClassMembers):
        variable_kind = "static_member_variable"
    elif isinstance(owner, (CppModule, CppNamespace)):
        variable_kind = "variable"
    elif isinstance(owner, (CppFunction, CppMethod, CppConstructor, CppDestructor)):
        # Function-local variables are intentionally unmodeled.
        return
    else:
        raise ParserInvariantError(
            "Encountered a VAR_DECL under an unexpected semantic owner. "
            f"owner type: {type(owner).__name__}; declaration: {describe_cursor_entity(cursor)}"
        )

    candidate_cpp = extract_variable_cpp_facet(
        cursor,
        context=context,
        kind=variable_kind,
    )
    existing = lookup_registered_element(cursor, context, CppVariable)
    if existing is not None:
        merge_variable_declaration(existing, candidate_cpp, cursor, context)
        return

    variable = CppVariable(name=cursor.spelling, cpp=candidate_cpp)
    if isinstance(owner, CppClassMembers):
        attached = owner.add_static_variable(variable)
    else:
        attached = owner.add_variable(variable)
    register_element_for_cursor(cursor, attached, context)


# ------------------------------------------------------------------------------
#     Class Template
# ------------------------------------------------------------------------------


def process_class_template_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one class-template family and recurse into its declaration."""

    candidate_cpp = extract_class_template_declaration_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppClassTemplate)
    if existing is not None:
        merge_class_template_declaration(existing, candidate_cpp, cursor, context)
        _visit_children(
            cursor.get_children(),
            existing.declaration,
            context,
            excluded_kinds=_TEMPLATE_PARAMETER_CURSOR_KINDS,
        )
        return

    template = CppClassTemplate(
        name=cursor.spelling,
        declaration=CppClassTemplateDeclaration(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = owner.add_class_template(template)
    register_element_for_cursor(cursor, attached, context)
    visit_declaration_children(
        cursor.get_children(),
        attached.declaration,
        context,
        excluded_kinds=_TEMPLATE_PARAMETER_CURSOR_KINDS,
    )


def process_templated_constructor_cursor(
    template_cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one templated constructor under a class-like declaration."""

    candidate_cpp = extract_constructor_cpp_facet(template_cursor, context=context)
    candidate_cpp.original_name = _constructor_name_for_owner(owner, template_cursor)
    candidate_cpp.template_parameters = extract_template_parameters(template_cursor, context=context)

    existing = lookup_registered_element(template_cursor, context, CppConstructor)
    if existing is not None:
        merge_templated_constructor_declaration(
            existing,
            candidate_cpp,
            template_cursor,
            context,
        )
        _merge_and_visit_callable_children(
            existing,
            template_cursor.get_children(),
            context,
            cursor_to_register=template_cursor,
            excluded_kinds=_PARAMETER_CURSOR_KINDS,
        )
        return

    constructor = CppConstructor(
        name=_constructor_name_for_owner(owner, template_cursor),
        cpp=candidate_cpp,
    )
    attached = owner.add_constructor(constructor)
    _refresh_scope_overload_indices(owner, "constructors")
    register_element_for_cursor(template_cursor, attached, context)
    visit_callable_children_and_docs(template_cursor.get_children(), attached, context)


# ------------------------------------------------------------------------------
#     Function
# ------------------------------------------------------------------------------


def process_function_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one free function declaration and recurse into its children."""

    candidate_cpp = extract_function_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppFunction)
    if existing is not None:
        merge_function_declaration(existing, candidate_cpp, cursor, context)
        _merge_and_visit_callable_children(
            existing,
            cursor.get_children(),
            context,
            excluded_kinds=_PARAMETER_CURSOR_KINDS,
        )
        return

    function = CppFunction(name=cursor.spelling, cpp=candidate_cpp)
    attached = owner.add_function(function)
    _refresh_scope_overload_indices(owner, "functions")
    register_element_for_cursor(cursor, attached, context)
    visit_callable_children_and_docs(cursor.get_children(), attached, context)


def process_parameter_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one parameter declaration."""

    candidate_cpp = extract_parameter_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppParameter)
    if existing is not None:
        merge_parameter_declaration(context, cursor, existing)
        return

    parameter = CppParameter(name=cursor.spelling, cpp=candidate_cpp)
    attached = owner.add_parameter(parameter)
    register_element_for_cursor(cursor, attached, context)


# ------------------------------------------------------------------------------
#     Function Template
# ------------------------------------------------------------------------------


def process_function_template_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one function-template family and recurse into its declaration."""

    child_cursors = list(cursor.get_children())
    constructor_owner = _templated_constructor_owner(cursor, owner, context)
    if constructor_owner is not None:
        process_templated_constructor_cursor(
            cursor,
            constructor_owner,
            context,
        )
        return

    method_template_owner = _templated_method_owner(cursor, owner, context)
    if method_template_owner is not None:
        process_method_template_cursor(
            cursor,
            method_template_owner,
            context,
        )
        return

    candidate_cpp = extract_function_template_declaration_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppFunctionTemplate)
    if existing is not None:
        merge_function_template_declaration(existing, candidate_cpp, cursor, context)
        _merge_and_visit_callable_children(
            existing.declaration,
            child_cursors,
            context,
            excluded_kinds=_TEMPLATE_PARAMETER_CURSOR_KINDS,
        )
        return

    template = CppFunctionTemplate(
        name=cursor.spelling,
        declaration=CppFunctionTemplateDeclaration(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = owner.add_function_template(template)
    _refresh_scope_overload_indices(
        owner,
        "function_templates",
        declaration_getter=lambda template: getattr(template, "declaration", None),
    )
    register_element_for_cursor(cursor, attached, context)
    visit_callable_children_and_docs(
        child_cursors,
        attached.declaration,
        context,
        excluded_kinds=_TEMPLATE_PARAMETER_CURSOR_KINDS,
    )


def process_method_template_cursor(
    cursor: Any,
    owner: CppClassMembers,
    context: BuildContext,
) -> None:
    """Create or enrich one method-template family and recurse into its declaration."""

    child_cursors = list(cursor.get_children())
    candidate_cpp = extract_method_template_declaration_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppMethodTemplate)
    if existing is not None:
        merge_method_template_declaration(existing, candidate_cpp, cursor, context)
        _merge_and_visit_callable_children(
            existing.declaration,
            child_cursors,
            context,
            excluded_kinds=_TEMPLATE_PARAMETER_CURSOR_KINDS,
        )
        return

    template = CppMethodTemplate(
        name=cursor.spelling,
        declaration=CppMethodTemplateDeclaration(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = owner.add_method_template(template)
    _refresh_scope_overload_indices(
        owner,
        "method_templates",
        declaration_getter=lambda template: getattr(template, "declaration", None),
    )
    register_element_for_cursor(cursor, attached, context)
    visit_callable_children_and_docs(
        child_cursors,
        attached.declaration,
        context,
        excluded_kinds=_TEMPLATE_PARAMETER_CURSOR_KINDS,
    )


# ------------------------------------------------------------------------------
#     Enum
# ------------------------------------------------------------------------------


def process_enum_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one enum declaration and recurse into its children."""

    candidate_cpp = extract_enum_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppEnum)
    if existing is not None:
        merge_enum_declaration(existing, candidate_cpp, cursor, context)
        _visit_children(cursor.get_children(), existing, context)
        return

    enum_ = CppEnum(name=cursor.spelling, cpp=candidate_cpp)
    attached = owner.add_enum(enum_)
    register_element_for_cursor(cursor, attached, context)
    visit_declaration_children(cursor.get_children(), attached, context)


def process_enumerator_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one enumerator declaration."""

    candidate_cpp = extract_enumerator_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppEnumerator)
    if existing is not None:
        merge_enumerator_declaration(context, cursor, existing)
        return

    enumerator = CppEnumerator(name=cursor.spelling, cpp=candidate_cpp)
    attached = owner.add_enumerator(enumerator)
    register_element_for_cursor(cursor, attached, context)


# ------------------------------------------------------------------------------
#     Alias
# ------------------------------------------------------------------------------


def process_alias_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one alias declaration."""

    candidate_cpp = extract_alias_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppAlias)
    if existing is not None:
        merge_alias_declaration(context, cursor, existing, candidate_cpp)
        return

    alias = CppAlias(name=cursor.spelling, cpp=candidate_cpp)
    attached = owner.add_alias(alias)
    register_element_for_cursor(cursor, attached, context)


def process_alias_template_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one alias-template family."""

    candidate_cpp = extract_alias_template_declaration_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppAliasTemplate)
    if existing is not None:
        merge_alias_template_declaration(existing, candidate_cpp, cursor, context)
        return

    template = CppAliasTemplate(
        name=cursor.spelling,
        declaration=CppAliasTemplateDeclaration(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = owner.add_alias_template(template)
    register_element_for_cursor(cursor, attached, context)


# ==================================================================================================
#     Helper Functions
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Child Visiting
# ------------------------------------------------------------------------------


def apply_parameter_docs(callable_element: Any) -> None:
    """Copy callable-level parameter docs onto the owned parameter nodes."""

    documentation = callable_element.cpp.doc
    if documentation is None or documentation.parsed is None:
        return

    parameter_docs = documentation.parsed.parameters
    for parameter in callable_element.parameters:
        if not parameter.name:
            parameter.cpp.doc = None
            continue
        parameter.cpp.doc = parameter_docs.get(parameter.name)


def visit_callable_children_and_docs(
    child_cursors: Iterable[Any],
    callable_element: Any,
    context: BuildContext,
    *,
    excluded_kinds: AbstractSet[CursorKind] | None = None,
) -> None:
    """Walk one callable's remaining children, then copy parsed parameter docs."""

    _visit_children(
        child_cursors,
        callable_element,
        context,
        excluded_kinds=excluded_kinds,
    )
    apply_parameter_docs(callable_element)


def visit_declaration_children(
    child_cursors: Iterable[Any],
    owner: CppElement,
    context: BuildContext,
    *,
    excluded_kinds: AbstractSet[CursorKind] | None = None,
) -> None:
    """Visit child cursors under one materialized declaration."""

    _visit_children(
        child_cursors,
        owner,
        context,
        excluded_kinds=excluded_kinds,
    )


def _merge_and_visit_callable_children(
    callable_element: Any,
    child_cursors: Iterable[Any],
    context: BuildContext,
    *,
    excluded_kinds: AbstractSet[CursorKind],
    cursor_to_register: Any | None = None,
) -> None:
    """Merge callable parameters from one repeated declaration, then continue child processing."""

    if cursor_to_register is not None:
        register_element_for_cursor(cursor_to_register, callable_element, context)

    merge_callable_parameter_children(
        callable_element,
        child_cursors,
        context,
    )
    visit_callable_children_and_docs(
        child_cursors,
        callable_element,
        context,
        excluded_kinds=excluded_kinds,
    )


def _visit_children(
    child_cursors: Iterable[Any],
    owner: CppElement,
    context: BuildContext,
    *,
    excluded_kinds: AbstractSet[CursorKind] | None = None,
) -> None:
    """Defer child walking to the main clang-walk module."""

    if excluded_kinds is None:
        from .clang_walk import visit_children

        visit_children(child_cursors, owner, context)
        return

    from .clang_walk import visit_cursor

    for child_cursor in child_cursors:
        if getattr(child_cursor, "kind", None) in excluded_kinds:
            continue
        visit_cursor(child_cursor, owner, context)


# ------------------------------------------------------------------------------
#     Naming
# ------------------------------------------------------------------------------


def _constructor_name_for_owner(
    owner: CppElement,
    cursor: Any,
) -> str:
    """Normalize one constructor name against the owning class-like declaration."""

    owner_name = getattr(owner, "name", "")
    if owner_name:
        return owner_name
    return cursor.spelling


def _destructor_name_for_owner(
    owner: CppElement,
    cursor: Any,
) -> str:
    """Normalize one destructor name against the owning class-like declaration."""

    owner_name = getattr(owner, "name", "")
    if owner_name:
        return f"~{owner_name}"
    spelling = cursor.spelling or ""
    return spelling


def _handle_explicit_class_template_specialization(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> bool:
    """Fold one explicit class-template specialization into the template-family path."""

    specialization_type = _explicit_class_template_specialization_type(cursor, context)
    if specialization_type is None:
        return False

    template_family = _find_class_template_family_for_specialization(owner, cursor.spelling)
    if template_family is not None:
        _record_observed_class_template_specialization(
            template_family,
            specialization_type.arguments,
            cursor,
        )

    if _should_warn_about_explicit_class_template_specialization(owner, context):
        _warn_explicit_class_template_specialization(cursor, template_family, context)

    # The current model does not represent explicit class specializations as
    # full declaration trees. Keep their concrete arguments when we can, and
    # otherwise ignore the specialization instead of materializing a duplicate
    # plain class node.
    return True


def _explicit_class_template_specialization_type(
    cursor: Any,
    context: BuildContext,
) -> TemplateInstanceCppType | None:
    """Return the structured specialized type for one explicit specialization cursor."""

    cursor_type = getattr(cursor, "type", None)
    if cursor_type is None:
        return None

    cpp_type = build_cpp_type(
        cursor_type,
        context=context,
        source_cursor=cursor,
    )
    if not isinstance(cpp_type, TemplateInstanceCppType):
        return None

    if cpp_type.template_name.split("::")[-1] != cursor.spelling:
        return None
    return cpp_type


def _find_class_template_family_for_specialization(
    owner: CppElement,
    template_name: str,
) -> CppClassTemplate | None:
    """Return the already materialized class-template family for one specialization."""

    declarations = getattr(owner, "declarations", None)
    class_templates = getattr(declarations, "class_templates", None)
    if class_templates is None:
        return None

    for template in class_templates:
        if template.name == template_name:
            return template
    return None


def _record_observed_class_template_specialization(
    template: CppClassTemplate,
    arguments: list[CppTemplateArgument],
    cursor: Any,
) -> None:
    """Record one explicit specialization as an observed template instance."""

    observed_instances = template.declaration.cpp.observed_instances
    argument_key = _template_argument_key(arguments)
    observation_location = cursor_source_location(cursor)

    for observed_instance in observed_instances:
        if _template_argument_key(observed_instance.arguments) != argument_key:
            continue
        if observation_location is not None and observation_location not in observed_instance.locations:
            observed_instance.locations.append(observation_location)
        return

    observed_instances.append(
        CppObservedTemplateInstance(
            arguments=list(arguments),
            locations=[] if observation_location is None else [observation_location],
        )
    )


def _should_warn_about_explicit_class_template_specialization(
    owner: CppElement,
    context: BuildContext,
) -> bool:
    """Return whether one ignored explicit specialization should produce a warning."""

    if _owner_is_std_namespace(owner):
        return context.config.warn_std_explicit_class_template_specializations
    return True


def _owner_is_std_namespace(owner: CppElement) -> bool:
    """Return whether the current owning scope is the standard namespace."""

    return getattr(owner, "qualified_name", "") == "std"


def _warn_explicit_class_template_specialization(
    cursor: Any,
    template_family: CppClassTemplate | None,
    context: BuildContext,
) -> None:
    """Emit one actionable warning about unsupported explicit specialization bodies."""

    if template_family is None:
        family_hint = (
            "The primary template was not found under the current scope, so this "
            "specialization is ignored entirely."
        )
    else:
        family_hint = (
            f"The primary template family '{template_family.qualified_name}' is active, "
            "so its concrete arguments may still be observed."
        )

    record_semantic_warning(
        context,
        f"Explicit class-template specialization for {describe_cursor_entity(cursor)} "
        "is not modeled as its own specialized declaration tree yet. "
        f"{family_hint} We do currently not yet fully support binding this specialization as its own API surface.",
        code="parse.explicit_class_template_specialization_ignored",
        cursor=cursor,
    )


# ------------------------------------------------------------------------------
#     Overload Index Ordering
# ------------------------------------------------------------------------------


def _refresh_scope_overload_indices(
    owner: CppElement,
    declaration_attr: str,
    *,
    declaration_getter: Any | None = None,
) -> None:
    """Assign stable overload indices across one named sibling declaration collection."""

    declarations = getattr(owner, "declarations", None)
    elements = getattr(declarations, declaration_attr, None)
    if elements is None:
        return

    _assign_overload_indices(
        elements,
        declaration_getter=declaration_getter,
    )


def _assign_overload_indices(
    elements: Iterable[Any],
    *,
    declaration_getter: Any | None = None,
) -> None:
    """Assign same-name overload indices in declaration order for one collection."""

    next_index_by_name: dict[str, int] = {}
    for element in elements:
        target = declaration_getter(element) if declaration_getter is not None else element
        if target is None:
            continue

        cpp = getattr(target, "cpp", None)
        name = getattr(target, "name", "")
        if cpp is None or not hasattr(cpp, "overload_index") or not name:
            continue

        overload_index = next_index_by_name.get(name, 0)
        cpp.overload_index = overload_index
        next_index_by_name[name] = overload_index + 1


# ------------------------------------------------------------------------------
#     Miscellaneous
# ------------------------------------------------------------------------------


def _looks_like_templated_constructor(
    cursor: Any,
    owner: CppElement,
) -> bool:
    """Return whether one function-template cursor is actually a templated constructor."""

    if not isinstance(owner, CppClassMembers):
        return False

    spelling = cursor.spelling or ""
    if spelling == owner.name:
        return True

    return _strip_trailing_template_arguments(spelling) == owner.name


def _templated_constructor_owner(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> CppClassMembers | None:
    """Resolve the owning class-like element when one function-template cursor is a constructor."""

    if _looks_like_templated_constructor(cursor, owner):
        return owner if isinstance(owner, CppClassMembers) else None

    semantic_owner = resolve_class_semantic_owner(cursor, context)
    if semantic_owner is None:
        return None

    if _looks_like_templated_constructor(cursor, semantic_owner):
        return semantic_owner

    return None


def _templated_method_owner(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> CppClassMembers | None:
    """Resolve the owning class-like element when one function-template cursor is a method."""

    if isinstance(owner, CppClassMembers) and not _looks_like_templated_constructor(cursor, owner):
        return owner

    semantic_owner = resolve_class_semantic_owner(cursor, context)
    if semantic_owner is None:
        return None

    if not _looks_like_templated_constructor(cursor, semantic_owner):
        return semantic_owner

    return None

def _strip_trailing_template_arguments(name: str) -> str:
    """Strip one trailing `<...>` suffix from a spelling when it is balanced."""

    if not name.endswith(">"):
        return name

    depth = 0
    for index in range(len(name) - 1, -1, -1):
        character = name[index]
        if character == ">":
            depth += 1
        elif character == "<":
            depth -= 1
            if depth == 0:
                return name[:index]

    return name
