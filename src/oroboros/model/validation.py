from __future__ import annotations

"""Semantic validation helpers for the C++ declaration model."""

from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Any

from ..diagnostics import Diagnostic, DiagnosticRenderOptions, format_diagnostics
from .class_ import CppClass
from .function import CppParameter
from .element import CppElement, ModelValidationError
from .enum import CppEnum
from .lookup import _iter_direct_child_elements
from .location import CppLocationInfo, SourceLocation
from .type import NamedCppType


# ==================================================================================================
#     Validate Tree
# ==================================================================================================


def validate_tree(root: CppElement) -> None:
    """Validate owner links and direct-child containment across one subtree."""

    diagnostics = collect_tree_diagnostics(root)
    if diagnostics:
        raise ModelValidationError(
            format_diagnostics(
                diagnostics,
                title="Invalid semantic model tree:",
                options=DiagnosticRenderOptions(
                    include_stage=False,
                    include_code=False,
                ),
            ),
            diagnostics=diagnostics,
        )


def collect_tree_diagnostics(root: CppElement) -> list[Diagnostic]:
    """Collect structural validation diagnostics across one subtree."""

    root_path = _root_access_path(root)
    diagnostics: list[Diagnostic] = []
    visited: dict[int, str] = {id(root): root_path}

    _validate_tree_subtree(root, root_path, visited, diagnostics)
    return diagnostics


def _validate_tree_subtree(
    element: CppElement,
    path: str,
    visited: dict[int, str],
    errors: list[str],
) -> None:
    """Collect structural validation errors for one subtree into one shared list."""

    _validate_owner_chain(element, path, errors)

    for child_path, child in _iter_direct_child_elements(element, path, errors):
        if child.owner is not element:
            _append_validation_error(
                errors,
                child_path,
                f"has owner {child._describe_owner()}, expected {element._describe_element()}",
                subject=child,
            )

        child_id = id(child)
        if child_id in visited:
            _append_validation_error(
                errors,
                child_path,
                f"references the same element already seen at {visited[child_id]}",
                subject=child,
            )
            continue

        visited[child_id] = child_path
        _validate_tree_subtree(child, child_path, visited, errors)


def _validate_owner_chain(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Detect cyclic owner links starting from one element."""

    seen_owner_ids = {id(element)}
    current = element.owner

    while current is not None:
        current_id = id(current)
        if current_id in seen_owner_ids:
            _append_validation_error(
                errors,
                path,
                f"participates in an owner cycle involving {current._describe_element()}",
                subject=element,
            )
            return
        seen_owner_ids.add(current_id)
        current = current.owner


# ==================================================================================================
#     Validate Semantics
# ==================================================================================================


class ModelSemanticValidationError(ValueError):
    """Report one or more semantic consistency problems in the model."""

    def __init__(self, message: str, *, diagnostics: list[Diagnostic] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = [] if diagnostics is None else diagnostics


def validate_semantics(root: CppElement) -> None:
    """Validate semantic cross-links and type usage across one subtree."""

    diagnostics = collect_semantic_diagnostics(root)
    if diagnostics:
        raise ModelSemanticValidationError(
            format_diagnostics(
                diagnostics,
                title="Invalid semantic model:",
                options=DiagnosticRenderOptions(
                    include_stage=False,
                    include_code=False,
                ),
            ),
            diagnostics=diagnostics,
        )


def collect_semantic_diagnostics(root: CppElement) -> list[Diagnostic]:
    """Collect semantic validation diagnostics across one subtree."""

    root_path = _root_access_path(root)
    diagnostics: list[Diagnostic] = []

    _validate_semantic_subtree(root, root_path, diagnostics)
    return diagnostics


def _validate_semantic_subtree(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate one element plus all descendants in one semantic subtree."""

    _validate_element_semantics(element, path, errors)

    for dataclass_field in dataclass_fields(element):
        field_name = dataclass_field.name
        if field_name == "owner":
            continue
        value = getattr(element, field_name)
        _validate_embedded_value(
            value,
            f"{path}.{field_name}",
            errors,
            reference_scope=_reference_lookup_scope(element),
        )

    for child_path, child in _iter_direct_child_elements(element, path):
        _validate_semantic_subtree(child, child_path, errors)


# ------------------------------------------------------------------------------
#     Validators
# ------------------------------------------------------------------------------


def _validate_element_semantics(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate semantic constraints specific to one declaration element."""

    _validate_cpp_name_sanity(element, path, errors)
    _validate_cpp_original_name(element, path, errors)
    _validate_cpp_availability(element, path, errors)
    _validate_duplicate_child_names(element, path, errors)
    _validate_owner_kind(element, path, errors)
    _validate_constructor_name(element, path, errors)
    _validate_special_member_classification(element, path, errors)
    _validate_method_like_flags(element, path, errors)
    _validate_variable_field_traits(element, path, errors)
    _validate_alias_target(element, path, errors)
    _validate_enumerator_value_sanity(element, path, errors)
    _validate_template_family(element, path, errors)
    _validate_overload_indices(element, path, errors)

    if isinstance(element, CppClass):
        _validate_class_like_kind_rules(element, path, errors)
        for index, base in enumerate(element.cpp.bases):
            _validate_class_base(
                base.type,
                f"{path}.cpp.bases[{index}].type",
                errors,
            )

    from .class_template import CppClassTemplateDeclaration

    if isinstance(element, CppClassTemplateDeclaration):
        _validate_class_like_kind_rules(element, path, errors)
        for index, base in enumerate(element.cpp.bases):
            _validate_class_base(
                base.type,
                f"{path}.cpp.bases[{index}].type",
                errors,
            )


def _validate_embedded_value(
    value: Any,
    path: str,
    errors: list[str],
    *,
    reference_scope: CppElement | None,
) -> None:
    """Walk one embedded non-element value and validate nested semantics."""

    if isinstance(value, CppElement):
        return

    if isinstance(value, NamedCppType):
        _validate_named_cpp_type(value, path, errors, reference_scope=reference_scope)

    if isinstance(value, CppLocationInfo):
        _validate_location_info(value, path, errors)

    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_embedded_value(
                item,
                f"{path}[{index}]",
                errors,
                reference_scope=reference_scope,
            )
        return

    if isinstance(value, tuple):
        for index, item in enumerate(value):
            _validate_embedded_value(
                item,
                f"{path}[{index}]",
                errors,
                reference_scope=reference_scope,
            )
        return

    if is_dataclass(value):
        for dataclass_field in dataclass_fields(value):
            nested_value = getattr(value, dataclass_field.name)
            _validate_embedded_value(
                nested_value,
                f"{path}.{dataclass_field.name}",
                errors,
                reference_scope=reference_scope,
            )


def _validate_named_cpp_type(
    cpp_type: NamedCppType,
    path: str,
    errors: list[str],
    *,
    reference_scope: CppElement | None,
) -> None:
    """Validate one declaration-linked named C++ type."""

    declaration = cpp_type.declaration
    if declaration is None:
        return

    if not _is_valid_named_type_declaration(declaration):
        _append_validation_error(
            errors,
            path,
            f"links to {declaration._describe_element()}, which is not a valid type declaration",
            subject=declaration,
        )
        return

    if cpp_type.name and not _named_type_matches_declaration(
        cpp_type,
        declaration,
        reference_scope=reference_scope,
    ):
        _append_validation_error(
            errors,
            path,
            f"spells the type as {cpp_type.name!r} but links to {declaration.qualified_name!r}",
            subject=declaration,
        )


def _validate_class_base(
    cpp_type: Any,
    path: str,
    errors: list[str],
) -> None:
    """Validate one class base-type relationship."""

    if not isinstance(cpp_type, NamedCppType):
        return

    declaration = cpp_type.declaration
    if declaration is None:
        return

    if not isinstance(declaration, CppClass):
        _append_validation_error(
            errors,
            path,
            f"uses {declaration._describe_element()} as a base, but class bases must refer to class-like declarations",
            subject=declaration,
        )


def _validate_class_like_kind_rules(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate semantic rules that differ between classes, structs, and unions."""

    from .class_ import CppClassMembers

    cpp_facet = getattr(element, "cpp", None)
    if cpp_facet is None or getattr(cpp_facet, "kind", None) != "union":
        return

    if getattr(cpp_facet, "bases", []):
        _append_validation_error(
            errors,
            path,
            f"{path}.cpp.kind is 'union', so {path}.cpp.bases must be empty",
            subject=element,
        )

    if not isinstance(element, CppClassMembers):
        return

    for index, method in enumerate(element.declarations.methods):
        if method.cpp.is_virtual:
            _append_validation_error(
                errors,
                f"{path}.methods[{index}]",
                "cpp marks a union method as virtual",
                subject=method,
            )
        if method.cpp.is_pure_virtual:
            _append_validation_error(
                errors,
                f"{path}.methods[{index}]",
                "cpp marks a union method as pure virtual",
                subject=method,
            )

    for index, method_template in enumerate(element.declarations.method_templates):
        declaration = method_template.declaration
        if declaration is None:
            continue
        if declaration.cpp.is_virtual:
            _append_validation_error(
                errors,
                f"{path}.method_templates[{index}].declaration",
                "cpp marks a union method template as virtual",
                subject=declaration,
            )
        if declaration.cpp.is_pure_virtual:
            _append_validation_error(
                errors,
                f"{path}.method_templates[{index}].declaration",
                "cpp marks a union method template as pure virtual",
                subject=declaration,
            )


def _validate_cpp_name_sanity(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that one semantic element name looks like plausible C++."""

    from .module import CppModule

    if isinstance(element, CppModule):
        return

    _validate_cpp_name(
        element.name,
        path,
        errors,
        allow_operator_names=_allows_operator_name(element),
        allow_destructor_names=_allows_destructor_name(element),
    )


def _validate_cpp_original_name(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that parsed original names stay aligned with element names."""

    cpp_facet = getattr(element, "cpp", None)
    original_name = getattr(cpp_facet, "original_name", None)
    if original_name is None:
        return

    if element.name != original_name:
        _append_validation_error(
            errors,
            path,
            f"is named {element.name!r}, but cpp.original_name is {original_name!r}",
            subject=element,
        )


def _validate_cpp_availability(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate coarse clang availability annotations on parsed declaration facets."""

    cpp_facet = getattr(element, "cpp", None)
    availability = getattr(cpp_facet, "availability", None)
    if availability is None:
        return

    if availability not in {
        "available",
        "deprecated",
        "not_accessible",
        "not_available",
    }:
        _append_validation_error(
            errors,
            f"{path}.cpp.availability",
            "must be one of 'available', 'deprecated', 'not_accessible', or 'not_available'",
            subject=element,
        )


def _validate_duplicate_child_names(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that non-overload child collections do not repeat names."""

    duplicate_checked_fields = [
        "namespaces",
        "classes",
        "alias_templates",
        "class_templates",
        "enums",
        "variables",
        "static_variables",
        "aliases",
        "enumerators",
    ]

    for field_name in duplicate_checked_fields:
        children = _direct_declaration_collection(element, field_name)
        if children is None:
            continue
        _validate_unique_names(children, f"{path}.{field_name}", errors)


def _validate_unique_names(
    children: list[Any],
    path: str,
    errors: list[str],
) -> None:
    """Validate that one child-element collection does not repeat names."""

    first_seen_at: dict[str, tuple[int, CppElement]] = {}

    for index, child in enumerate(children):
        if not isinstance(child, CppElement):
            continue

        previous_entry = first_seen_at.get(child.name)
        if previous_entry is not None:
            previous_index, previous_child = previous_entry
            _append_validation_error(
                errors,
                f"{path}[{index}]",
                f"duplicates the name {child.name!r} already used at {path}[{previous_index}]",
                subject=child,
                locations=_validation_subject_locations(child) + _validation_subject_locations(previous_child),
            )
            continue

        first_seen_at[child.name] = (index, child)


def _validate_owner_kind(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that selected element kinds appear only under valid owners."""

    from .alias import CppAlias
    from .alias_template import (
        CppAliasTemplate,
        CppAliasTemplateDeclaration,
        CppAliasTemplateInstance,
    )
    from .class_ import CppClassMembers
    from .enum import CppEnumerator
    from .function import CppFunction, CppParameter
    from .function_template import (
        CppFunctionTemplate,
        CppFunctionTemplateDeclaration,
        CppFunctionTemplateInstance,
    )
    from .method_template import (
        CppMethodTemplate,
        CppMethodTemplateDeclaration,
        CppMethodTemplateInstance,
    )
    from .module import CppModule
    from .member import CppConstructor, CppDestructor, CppMethod
    from .namespace import CppNamespace
    from .class_template import (
        CppClassTemplate,
        CppClassTemplateDeclaration,
        CppClassTemplateInstance,
    )
    from .variable import CppVariable

    owner = element.owner
    if owner is None:
        return

    if isinstance(element, CppNamespace) and not isinstance(owner, (CppModule, CppNamespace)):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but namespaces must be owned by the module root or another namespace",
            subject=element,
        )

    if isinstance(element, CppFunction) and not isinstance(owner, (CppModule, CppNamespace)):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but free functions must be owned by the module root or a namespace",
            subject=element,
        )

    if isinstance(element, CppAlias) and not isinstance(owner, (CppModule, CppNamespace, CppClassMembers)):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but aliases must be owned by the module root, a namespace, or a class-like declaration",
            subject=element,
        )

    if isinstance(element, CppParameter) and not isinstance(
        owner,
        (
            CppFunction,
            CppMethod,
            CppConstructor,
            CppFunctionTemplateDeclaration,
            CppMethodTemplateDeclaration,
        ),
    ):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but parameters must be owned by function-like declarations",
            subject=element,
        )

    if isinstance(element, (CppMethod, CppConstructor, CppDestructor)) and not isinstance(
        owner,
        CppClassMembers,
    ):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but this member kind must be owned by a class-like declaration",
            subject=element,
        )

    if isinstance(element, CppVariable) and not isinstance(
        owner,
        (CppModule, CppNamespace, CppClassMembers),
    ):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but variables must be owned by the module root, a namespace, or a class-like declaration",
            subject=element,
        )

    if isinstance(element, CppEnumerator) and not isinstance(owner, CppEnum):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but enumerators must be owned by enums",
            subject=element,
        )

    if isinstance(element, CppEnum) and not isinstance(owner, (CppModule, CppNamespace, CppClassMembers)):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but enums must be owned by the module root, a namespace, or a class-like declaration",
            subject=element,
        )

    if isinstance(element, CppClass) and not isinstance(owner, (CppModule, CppNamespace, CppClassMembers)):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but classes must be owned by the module root, a namespace, or a class-like declaration",
            subject=element,
        )

    if isinstance(element, (CppAliasTemplate, CppClassTemplate, CppFunctionTemplate, CppMethodTemplate)) and not isinstance(
        owner,
        (CppModule, CppNamespace, CppClassMembers),
    ):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but template families must be owned by the module root, a namespace, or a class-like declaration",
            subject=element,
        )

    if isinstance(element, CppAliasTemplateDeclaration) and not isinstance(owner, CppAliasTemplate):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but alias-template declarations must be owned by alias-template families",
            subject=element,
        )

    if isinstance(element, CppClassTemplateDeclaration) and not isinstance(owner, CppClassTemplate):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but class-template declarations must be owned by class-template families",
            subject=element,
        )

    if isinstance(element, CppAliasTemplateInstance) and not isinstance(owner, CppAliasTemplate):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but alias-template instances must be owned by alias-template families",
            subject=element,
        )

    if isinstance(element, CppClassTemplateInstance) and not isinstance(owner, CppClassTemplate):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but class-template instances must be owned by class-template families",
            subject=element,
        )

    if isinstance(element, CppFunctionTemplateDeclaration) and not isinstance(owner, CppFunctionTemplate):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but function-template declarations must be owned by function-template families",
            subject=element,
        )

    if isinstance(element, CppFunctionTemplateInstance) and not isinstance(owner, CppFunctionTemplate):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but function-template instances must be owned by function-template families",
            subject=element,
        )

    if isinstance(element, CppMethodTemplateDeclaration) and not isinstance(owner, CppMethodTemplate):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but method-template declarations must be owned by method-template families",
            subject=element,
        )

    if isinstance(element, CppMethodTemplateInstance) and not isinstance(owner, CppMethodTemplate):
        _append_validation_error(
            errors,
            path,
            f"is owned by {owner._describe_element()}, but method-template instances must be owned by method-template families",
            subject=element,
        )


def _validate_constructor_name(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that special-member names match their owning class-like declaration."""

    from .member import CppConstructor, CppDestructor

    if not isinstance(element, (CppConstructor, CppDestructor)):
        return

    owner = element.owner
    if owner is None:
        return

    expected_name = owner.name if isinstance(element, CppConstructor) else f"~{owner.name}"
    if element.name != expected_name:
        _append_validation_error(
            errors,
            path,
            f"is named {element.name!r}, but its owning class-like declaration is named {owner.name!r}, "
            f"so the expected member name is {expected_name!r}",
            subject=element,
        )


def _validate_method_like_flags(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate method-like flag invariants for class member callables."""

    from .class_ import CppClassMembers
    from .function_template import CppFunctionTemplateDeclaration
    from .method_template import CppMethodTemplateDeclaration, CppMethodTemplateInstance
    from .member import CppDestructor, CppMethod

    cpp_facet = getattr(element, "cpp", None)
    if cpp_facet is None:
        return

    if not hasattr(cpp_facet, "is_virtual"):
        return

    if not isinstance(
        element,
        (CppMethod, CppDestructor, CppMethodTemplateDeclaration, CppMethodTemplateInstance),
    ):
        return

    owner = element.owner
    if owner is None or not isinstance(owner, CppClassMembers):
        return

    if cpp_facet.is_pure_virtual and not cpp_facet.is_virtual:
        _append_validation_error(
            errors,
            path,
            "cpp marks the callable as pure virtual, but not virtual",
            subject=element,
        )

    ref_qualifier = getattr(cpp_facet, "ref_qualifier", None)
    if ref_qualifier not in {None, "&", "&&"}:
        _append_validation_error(
            errors,
            f"{path}.cpp.ref_qualifier",
            "must be one of None, '&', or '&&'",
            subject=element,
        )

    if getattr(cpp_facet, "is_static", False) and cpp_facet.is_virtual:
        _append_validation_error(
            errors,
            path,
            "cpp marks the callable as both static and virtual",
            subject=element,
        )

    if getattr(cpp_facet, "is_static", False) and ref_qualifier is not None:
        _append_validation_error(
            errors,
            path,
            "cpp marks the callable as both static and ref-qualified",
            subject=element,
        )


def _validate_special_member_classification(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate special-member and converting-constructor classifier fields."""

    from .member import CppConstructor, CppMethod

    cpp_facet = getattr(element, "cpp", None)
    if cpp_facet is None:
        return

    if isinstance(element, CppConstructor):
        special_member_kind = getattr(cpp_facet, "special_member_kind", None)
        if special_member_kind not in {
            None,
            "default_constructor",
            "copy_constructor",
            "move_constructor",
        }:
            _append_validation_error(
                errors,
                f"{path}.cpp.special_member_kind",
                "must be one of None, 'default_constructor', 'copy_constructor', or 'move_constructor'",
                subject=element,
            )
        return

    if hasattr(cpp_facet, "is_converting_constructor") and getattr(cpp_facet, "is_converting_constructor", False):
        _append_validation_error(
            errors,
            f"{path}.cpp.is_converting_constructor",
            "is only valid on constructors",
            subject=element,
        )

    if not hasattr(cpp_facet, "special_member_kind"):
        return

    special_member_kind = getattr(cpp_facet, "special_member_kind", None)
    if isinstance(element, CppMethod):
        if special_member_kind not in {None, "copy_assignment", "move_assignment"}:
            _append_validation_error(
                errors,
                f"{path}.cpp.special_member_kind",
                "must be one of None, 'copy_assignment', or 'move_assignment'",
                subject=element,
            )
        if special_member_kind is not None and element.name != "operator=":
            _append_validation_error(
                errors,
                path,
                f"cpp marks the method as {special_member_kind!r}, but the method name is not 'operator='",
                subject=element,
            )
        return

    if special_member_kind is not None:
        _append_validation_error(
            errors,
            f"{path}.cpp.special_member_kind",
            "is only valid on constructors and ordinary methods",
            subject=element,
        )


def _validate_alias_target(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that alias declarations carry a usable target type."""

    from .alias import CppAlias
    from .alias_template import CppAliasTemplateDeclaration

    if not isinstance(element, (CppAlias, CppAliasTemplateDeclaration)):
        return

    if element.cpp.target is None:
        _append_validation_error(
            errors,
            f"{path}.cpp.target",
            "is missing for this alias declaration",
            subject=element,
        )


def _validate_variable_field_traits(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate bitfield and `mutable` traits on parsed variable declarations."""

    from .variable import CppVariable

    if not isinstance(element, CppVariable):
        return

    cpp_facet = element.cpp
    is_member_like = cpp_facet.kind in {"member_variable", "static_member_variable"}
    if cpp_facet.bitfield_width is not None and not cpp_facet.is_bitfield:
        _append_validation_error(
            errors,
            f"{path}.cpp.bitfield_width",
            f"is set, but {path}.cpp.is_bitfield is false",
            subject=element,
        )

    if cpp_facet.is_bitfield and cpp_facet.kind == "static_member_variable":
        _append_validation_error(
            errors,
            path,
            "cpp marks a static member variable as a bitfield",
            subject=element,
        )

    if cpp_facet.is_mutable and cpp_facet.kind != "member_variable":
        _append_validation_error(
            errors,
            path,
            "cpp marks a non-member field as mutable",
            subject=element,
        )

    if (cpp_facet.is_bitfield or cpp_facet.bitfield_width is not None or cpp_facet.is_mutable) and not is_member_like:
        _append_validation_error(
            errors,
            path,
            "cpp field-only traits are only valid on class member variables",
            subject=element,
        )


def _validate_template_family(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate wrapper/declaration/instance consistency of template families."""

    from .alias_template import CppAliasTemplate
    from .class_template import CppClassTemplate
    from .function_template import CppFunctionTemplate
    from .method_template import CppMethodTemplate
    from .template_ import _validate_template_arguments

    if not isinstance(element, (CppAliasTemplate, CppClassTemplate, CppFunctionTemplate, CppMethodTemplate)):
        return

    declaration = element.declaration
    if declaration is None:
        _append_validation_error(
            errors,
            path,
            "does not contain a generic declaration",
            subject=element,
        )
        return

    if declaration.name != element.name:
        _append_validation_error(
            errors,
            f"{path}.declaration",
            f"is named {declaration.name!r}, but the template family is named {element.name!r}",
            subject=declaration,
        )

    for index, instance in enumerate(element.instances):
        if instance.name != element.name:
            _append_validation_error(
                errors,
                f"{path}.instances[{index}]",
                f"is named {instance.name!r}, but the template family is named {element.name!r}",
                subject=instance,
            )

        try:
            _validate_template_arguments(
                declaration.cpp.template_parameters,
                instance.cpp.template_arguments,
                context=f"{type(element).__name__} '{element.name}' instance {index}",
            )
        except ValueError as error:
            _append_validation_error(
                errors,
                f"{path}.instances[{index}]",
                f"has invalid template arguments: {error}",
                subject=instance,
            )

    for index, observed_instance in enumerate(declaration.cpp.observed_instances):
        try:
            _validate_template_arguments(
                declaration.cpp.template_parameters,
                observed_instance.arguments,
                context=f"{type(element).__name__} '{element.name}' observed instance {index}",
            )
        except ValueError as error:
            _append_validation_error(
                errors,
                f"{path}.declaration.cpp.observed_instances[{index}]",
                f"has invalid template arguments: {error}",
                subject=observed_instance,
            )


def _validate_enumerator_value_sanity(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate simple lexical sanity of enumerator value spellings."""

    from .enum import CppEnumerator

    if not isinstance(element, CppEnumerator):
        return

    value_spelling = element.cpp.value_spelling
    if value_spelling is None:
        return

    if not value_spelling.strip():
        _append_validation_error(
            errors,
            f"{path}.cpp.value_spelling",
            "must not be empty or whitespace-only",
            subject=element,
        )


def _validate_overload_indices(
    element: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate overload-index uniqueness and contiguity inside sibling groups."""

    _validate_overload_index_collection(
        _direct_declaration_collection(element, "functions"),
        f"{path}.functions",
        errors,
    )
    _validate_overload_index_collection(
        _direct_declaration_collection(element, "methods"),
        f"{path}.methods",
        errors,
    )
    _validate_overload_index_collection(
        _direct_declaration_collection(element, "constructors"),
        f"{path}.constructors",
        errors,
    )

    function_templates = _direct_declaration_collection(element, "function_templates")
    if function_templates is not None:
        _validate_overload_index_collection(
            [template.declaration for template in function_templates if getattr(template, "declaration", None) is not None],
            f"{path}.function_templates",
            errors,
        )

    method_templates = _direct_declaration_collection(element, "method_templates")
    if method_templates is not None:
        _validate_overload_index_collection(
            [template.declaration for template in method_templates if getattr(template, "declaration", None) is not None],
            f"{path}.method_templates",
            errors,
        )


def _validate_overload_index_collection(
    elements: list[Any] | None,
    path: str,
    errors: list[str],
) -> None:
    """Validate overload-index groupings for one same-scope callable collection."""

    if not elements:
        return

    groups: dict[str, list[tuple[int, Any]]] = {}
    for index, element in enumerate(elements):
        if not isinstance(element, CppElement):
            continue
        groups.setdefault(element.name, []).append((index, element))

    for group_name, group in groups.items():
        if len(group) <= 1:
            continue

        indexed_entries: list[tuple[int, int]] = []
        missing_indices: list[int] = []

        for entry_index, element in group:
            overload_index = getattr(getattr(element, "cpp", None), "overload_index", None)
            if overload_index is None:
                missing_indices.append(entry_index)
                continue
            indexed_entries.append((entry_index, overload_index))

        if missing_indices and indexed_entries:
            missing_list = ", ".join(f"{path}[{index}]" for index in missing_indices)
            _append_validation_error(
                errors,
                path,
                f"overload group {group_name!r} mixes set and unset overload_index values; missing at {missing_list}",
                locations=[
                    location
                    for _, element in group
                    for location in _validation_subject_locations(element)
                ],
            )
            continue

        if missing_indices:
            continue

        sorted_indices = sorted(overload_index for _, overload_index in indexed_entries)
        expected_indices = list(range(len(group)))
        if sorted_indices != expected_indices:
            _append_validation_error(
                errors,
                path,
                f"overload group {group_name!r} has overload_index values {sorted_indices}, expected {expected_indices}",
                locations=[
                    location
                    for _, element in group
                    for location in _validation_subject_locations(element)
                ],
            )


def _validate_location_info(
    location: CppLocationInfo,
    path: str,
    errors: list[str],
) -> None:
    """Validate internal consistency of one source-provenance bundle."""

    declaration_keys: set[tuple[str, int, int]] = set()

    for index, declaration in enumerate(location.declarations):
        key = _source_location_key(declaration)
        if key in declaration_keys:
            _append_validation_error(
                errors,
                f"{path}.declarations[{index}]",
                "duplicates an earlier declaration location",
                subject=declaration,
            )
            continue
        declaration_keys.add(key)

    primary = location.primary
    definition = location.definition
    if primary is None:
        return

    if definition is not None:
        primary_key = _source_location_key(primary)
        if primary_key != _source_location_key(definition) and primary_key not in declaration_keys:
            _append_validation_error(
                errors,
                f"{path}.primary",
                "must match either .definition or one of .declarations",
                subject=primary,
            )


def _validate_cpp_name(
    name: str,
    path: str,
    errors: list[str],
    *,
    allow_operator_names: bool = False,
    allow_destructor_names: bool = False,
) -> None:
    """Validate lexical sanity of one local C++ declaration-style name."""

    if name == "":
        return

    if name != name.strip():
        _append_validation_error(
            errors,
            path,
            f"has leading or trailing whitespace in name {name!r}",
        )
        return

    if any(character in name for character in "\n\r\t"):
        _append_validation_error(
            errors,
            path,
            f"contains control whitespace in name {name!r}",
        )
        return

    if allow_operator_names and name.startswith("operator"):
        return

    if allow_destructor_names and name.startswith("~") and _is_cpp_identifier(name[1:]):
        return

    if not _is_cpp_identifier(name):
        _append_validation_error(
            errors,
            path,
            f"has implausible C++ name spelling {name!r}",
        )


def _validate_cpp_qualified_name(
    qualified_name: str,
    path: str,
    errors: list[str],
) -> None:
    """Validate lexical sanity of one stored C++ qualified name string."""

    if qualified_name != qualified_name.strip():
        _append_validation_error(
            errors,
            path,
            f"has leading or trailing whitespace in {qualified_name!r}",
        )
        return

    if any(character in qualified_name for character in " \n\r\t"):
        _append_validation_error(
            errors,
            path,
            f"contains whitespace in {qualified_name!r}",
        )
        return

    parts = qualified_name.split("::")
    if any(part == "" for part in parts):
        _append_validation_error(
            errors,
            path,
            f"has malformed scope separators in {qualified_name!r}",
        )
        return

    for index, part in enumerate(parts):
        _validate_cpp_name(part, f"{path}[part {index}]", errors)


# ------------------------------------------------------------------------------
#     Helper Functions
# ------------------------------------------------------------------------------


def _direct_declaration_collection(
    element: CppElement,
    field_name: str,
) -> list[Any] | None:
    """Return one direct declaration collection from an element when it exists."""

    declarations = getattr(element, "declarations", None)
    if declarations is not None:
        return getattr(declarations, field_name, None)

    return getattr(element, field_name, None)


def _source_location_key(location: SourceLocation) -> tuple[str, int, int]:
    """Build one comparable key for a source location."""

    return (str(location.file), location.line, location.column)


def _allows_operator_name(element: CppElement) -> bool:
    """Return whether one element kind may legitimately use an operator name."""

    cpp_facet = getattr(element, "cpp", None)
    return getattr(cpp_facet, "operator", None) is not None or element.name.startswith("operator")


def _allows_destructor_name(element: CppElement) -> bool:
    """Return whether one element kind may legitimately use a destructor spelling."""

    return type(element).__name__ == "CppDestructor" or element.name.startswith("~")


def _is_cpp_identifier(name: str) -> bool:
    """Return whether one name looks like a plausible C++ identifier."""

    if not name:
        return False

    first = name[0]
    if first != "_" and not first.isalpha():
        return False

    for character in name[1:]:
        if character != "_" and not character.isalnum():
            return False

    return True


def _is_valid_named_type_declaration(declaration: CppElement) -> bool:
    """Check whether one declaration element may be referenced by a named type."""

    from .alias import CppAlias
    from .alias_template import CppAliasTemplateDeclaration, CppAliasTemplateInstance
    from .class_template import CppClassTemplateDeclaration, CppClassTemplateInstance

    return isinstance(
        declaration,
        (
            CppAlias,
            CppAliasTemplateDeclaration,
            CppAliasTemplateInstance,
            CppClass,
            CppEnum,
            CppClassTemplateDeclaration,
            CppClassTemplateInstance,
        ),
    )


def _named_type_matches_declaration(
    cpp_type: NamedCppType,
    declaration: CppElement,
    *,
    reference_scope: CppElement | None,
) -> bool:
    """Check whether one named-type spelling is compatible with its declaration."""

    del reference_scope

    normalized_name = _normalize_named_type_spelling_for_match(cpp_type.name)
    original_name = getattr(getattr(declaration, "cpp", None), "original_name", None)
    valid_names = {_normalize_named_type_spelling_for_match(declaration.name)}
    if original_name is not None:
        valid_names.add(_normalize_named_type_spelling_for_match(original_name))
    return _terminal_type_name_segment(normalized_name) in valid_names


def _normalize_named_type_spelling_for_match(name: str) -> str:
    """Normalize one named-type spelling for semantic declaration matching."""

    normalized = name.strip().removeprefix("::")
    for prefix in ("typename ", "struct ", "class ", "union ", "enum "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break
    return normalized


def _terminal_type_name_segment(name: str) -> str:
    """Return the terminal scope segment used for light linked-type sanity checks."""

    segments = name.split("::")
    return segments[-1].strip() if segments else name.strip()


def _reference_lookup_scope(element: CppElement) -> CppElement | None:
    """Return the semantic scope used for validating embedded type-name spellings."""

    if isinstance(element, CppParameter):
        owner = element.owner
        if owner is None:
            return None
        return owner.scope_parent

    return element.scope_parent


# ------------------------------------------------------------------------------
#     Error Processing
# ------------------------------------------------------------------------------


def _append_validation_error(
    errors: list[Diagnostic],
    path: str,
    detail: str,
    *,
    subject: Any | None = None,
    locations: list[SourceLocation] | None = None,
) -> None:
    """Append one structured validation diagnostic."""

    rendered_locations = (
        _unique_source_locations(locations)
        if locations is not None
        else _validation_subject_locations(subject)
    )
    errors.append(
        Diagnostic(
            severity="error",
            stage="validation",
            code="validation.error",
            message=detail,
            locations=rendered_locations,
            element_path=path,
        )
    )


def _validation_subject_locations(subject: Any) -> list[SourceLocation]:
    """Return the most relevant source locations known for one validation subject."""

    from .template_ import CppObservedTemplateInstance

    if isinstance(subject, SourceLocation):
        return [subject]

    if isinstance(subject, CppLocationInfo):
        return _location_info_locations(subject)

    if isinstance(subject, CppObservedTemplateInstance):
        return _unique_source_locations(subject.locations)

    cpp_facet = getattr(subject, "cpp", None)
    location = getattr(cpp_facet, "location", None)
    if isinstance(location, CppLocationInfo):
        return _location_info_locations(location)

    return []


def _location_info_locations(location: CppLocationInfo) -> list[SourceLocation]:
    """Return all unique known source locations from one provenance bundle."""

    ordered_locations: list[SourceLocation] = []
    if location.primary is not None:
        ordered_locations.append(location.primary)
    if location.definition is not None:
        ordered_locations.append(location.definition)
    ordered_locations.extend(location.declarations)
    return _unique_source_locations(ordered_locations)


def _unique_source_locations(locations: list[SourceLocation]) -> list[SourceLocation]:
    """Preserve one ordered list of unique source locations."""

    unique_locations: list[SourceLocation] = []
    seen_keys: set[tuple[str, int, int]] = set()
    for location in locations:
        key = _source_location_key(location)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_locations.append(location)
    return unique_locations


def _root_access_path(root: CppElement) -> str:
    """Return one copy-pasteable root expression for validator error paths."""

    root_names = {
        "CppAlias": "alias",
        "CppAliasTemplate": "alias_template",
        "CppAliasTemplateDeclaration": "alias_template_declaration",
        "CppAliasTemplateInstance": "alias_template_instance",
        "CppClass": "class_",
        "CppClassTemplate": "class_template",
        "CppClassTemplateDeclaration": "class_template_declaration",
        "CppClassTemplateInstance": "class_template_instance",
        "CppConstructor": "constructor",
        "CppDestructor": "destructor",
        "CppEnum": "enum_",
        "CppEnumerator": "enumerator",
        "CppFunction": "function",
        "CppFunctionTemplate": "function_template",
        "CppFunctionTemplateDeclaration": "function_template_declaration",
        "CppFunctionTemplateInstance": "function_template_instance",
        "CppMethod": "method",
        "CppMethodTemplate": "method_template",
        "CppMethodTemplateDeclaration": "method_template_declaration",
        "CppMethodTemplateInstance": "method_template_instance",
        "CppModule": "module",
        "CppNamespace": "namespace",
        "CppParameter": "parameter",
        "CppVariable": "variable",
    }
    return root_names.get(type(root).__name__, "root")
