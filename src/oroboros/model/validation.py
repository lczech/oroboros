from __future__ import annotations

"""Semantic validation helpers for the C++ declaration model."""

from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Any

from .class_ import CppClass
from .element import CppElement, ModelValidationError
from .enum import CppEnum
from .lookup import _iter_direct_child_nodes
from .location import CppLocationInfo, SourceLocation
from .type import NamedCppType


# ==================================================================================================
#     Validate Tree
# ==================================================================================================


def validate_tree(root: CppElement) -> None:
    """Validate owner links and direct-child containment across one subtree."""

    root_path = root._describe_node()
    errors: list[str] = []
    visited: dict[int, str] = {id(root): root_path}

    _validate_tree_subtree(root, root_path, visited, errors)

    if errors:
        raise ModelValidationError(
            "Invalid semantic model tree:\n- " + "\n- ".join(errors)
        )


def _validate_tree_subtree(
    node: CppElement,
    path: str,
    visited: dict[int, str],
    errors: list[str],
) -> None:
    """Collect structural validation errors for one subtree into one shared list."""

    _validate_owner_chain(node, path, errors)

    for child_path, child in _iter_direct_child_nodes(node, path, errors):
        if child.owner is not node:
            errors.append(
                f"{child_path} has owner {child._describe_owner()}, "
                f"expected {node._describe_node()}."
            )

        child_id = id(child)
        if child_id in visited:
            errors.append(
                f"{child_path} references the same node already seen at "
                f"{visited[child_id]}."
            )
            continue

        visited[child_id] = child_path
        _validate_tree_subtree(child, child_path, visited, errors)


def _validate_owner_chain(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Detect cyclic owner links starting from one node."""

    seen_owner_ids = {id(node)}
    current = node.owner

    while current is not None:
        current_id = id(current)
        if current_id in seen_owner_ids:
            errors.append(
                f"{path} participates in an owner cycle involving "
                f"{current._describe_node()}."
            )
            return
        seen_owner_ids.add(current_id)
        current = current.owner


# ==================================================================================================
#     Validate Semantics
# ==================================================================================================


class ModelSemanticValidationError(ValueError):
    """Report one or more semantic consistency problems in the model."""


def validate_semantics(root: CppElement) -> None:
    """Validate semantic cross-links and type usage across one subtree."""

    root_path = root._describe_node()
    errors: list[str] = []

    _validate_semantic_subtree(root, root_path, errors)

    if errors:
        raise ModelSemanticValidationError(
            "Invalid semantic model:\n- " + "\n- ".join(errors)
        )


def _validate_semantic_subtree(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate one node plus all descendants in one semantic subtree."""

    _validate_element_semantics(node, path, errors)

    for dataclass_field in dataclass_fields(node):
        field_name = dataclass_field.name
        if field_name == "owner":
            continue
        value = getattr(node, field_name)
        _validate_embedded_value(value, f"{path}.{field_name}", errors)

    for child_path, child in _iter_direct_child_nodes(node, path):
        _validate_semantic_subtree(child, child_path, errors)


def _validate_element_semantics(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate semantic constraints specific to one declaration node."""

    _validate_cpp_name_sanity(node, path, errors)
    _validate_cpp_original_name(node, path, errors)
    _validate_duplicate_child_names(node, path, errors)
    _validate_owner_kind(node, path, errors)
    _validate_constructor_name(node, path, errors)
    _validate_method_like_flags(node, path, errors)
    _validate_alias_metadata(node, path, errors)
    _validate_enumerator_value_sanity(node, path, errors)
    _validate_template_family(node, path, errors)
    _validate_overload_indices(node, path, errors)

    if isinstance(node, CppClass):
        for index, base in enumerate(node.cpp.bases):
            _validate_class_base(
                base.type,
                f"{path}.cpp.bases[{index}].type",
                errors,
            )


def _validate_embedded_value(
    value: Any,
    path: str,
    errors: list[str],
) -> None:
    """Walk one embedded non-element value and validate nested semantics."""

    if isinstance(value, CppElement):
        return

    if isinstance(value, NamedCppType):
        _validate_named_cpp_type(value, path, errors)

    if isinstance(value, CppLocationInfo):
        _validate_location_info(value, path, errors)

    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_embedded_value(item, f"{path}[{index}]", errors)
        return

    if isinstance(value, tuple):
        for index, item in enumerate(value):
            _validate_embedded_value(item, f"{path}[{index}]", errors)
        return

    if is_dataclass(value):
        for dataclass_field in dataclass_fields(value):
            nested_value = getattr(value, dataclass_field.name)
            _validate_embedded_value(
                nested_value,
                f"{path}.{dataclass_field.name}",
                errors,
            )


def _validate_named_cpp_type(
    cpp_type: NamedCppType,
    path: str,
    errors: list[str],
) -> None:
    """Validate one declaration-linked named C++ type."""

    declaration = cpp_type.declaration
    if declaration is None:
        return

    if not _is_valid_named_type_declaration(declaration):
        errors.append(
            f"{path} links to {declaration._describe_node()}, which is not a valid type declaration."
        )
        return

    if cpp_type.name and not _named_type_matches_declaration(cpp_type, declaration):
        errors.append(
            f"{path} spells the type as {cpp_type.name!r} but links to "
            f"{declaration.qualified_name!r}."
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
        errors.append(
            f"{path} uses {declaration._describe_node()} as a base, but class bases "
            f"must refer to class-like declarations."
        )


def _validate_cpp_name_sanity(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that one semantic node name looks like plausible C++."""

    from .module import CppModule

    if isinstance(node, CppModule):
        return

    _validate_cpp_name(
        node.name,
        path,
        errors,
        allow_operator_names=_allows_operator_name(node),
    )


def _validate_cpp_original_name(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that parsed original names stay aligned with element names."""

    cpp_facet = getattr(node, "cpp", None)
    original_name = getattr(cpp_facet, "original_name", None)
    if original_name is None:
        return

    if node.name != original_name:
        errors.append(
            f"{path} is named {node.name!r}, but cpp.original_name is {original_name!r}."
        )


def _validate_duplicate_child_names(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that non-overload child collections do not repeat names."""

    duplicate_checked_fields = [
        "namespaces",
        "classes",
        "class_templates",
        "enums",
        "fields",
        "enumerators",
    ]

    for field_name in duplicate_checked_fields:
        children = getattr(node, field_name, None)
        if children is None:
            continue
        _validate_unique_names(children, f"{path}.{field_name}", errors)


def _validate_unique_names(
    children: list[Any],
    path: str,
    errors: list[str],
) -> None:
    """Validate that one child-element collection does not repeat names."""

    first_seen_at: dict[str, int] = {}

    for index, child in enumerate(children):
        if not isinstance(child, CppElement):
            continue

        previous_index = first_seen_at.get(child.name)
        if previous_index is not None:
            errors.append(
                f"{path}[{index}] duplicates the name {child.name!r} already used at "
                f"{path}[{previous_index}]."
            )
            continue

        first_seen_at[child.name] = index


def _validate_owner_kind(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that selected element kinds appear only under valid owners."""

    from .class_ import CppClassMembers, CppField
    from .enum import CppEnumerator
    from .function import CppFunction, CppParameter
    from .function_template import (
        CppFunctionTemplate,
        CppFunctionTemplateDecl,
        CppFunctionTemplateInstance,
    )
    from .module import CppModule
    from .member import CppConstructor, CppMethod
    from .namespace import CppNamespace
    from .class_template import CppClassTemplate, CppClassTemplateDecl, CppClassTemplateInstance

    owner = node.owner
    if owner is None:
        return

    if isinstance(node, CppNamespace) and not isinstance(owner, (CppModule, CppNamespace)):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but namespaces must be owned "
            f"by the module root or another namespace."
        )

    if isinstance(node, CppFunction) and not isinstance(owner, (CppModule, CppNamespace)):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but free functions must be "
            f"owned by the module root or a namespace."
        )

    if isinstance(node, CppParameter) and not isinstance(
        owner,
        (CppFunction, CppMethod, CppConstructor, CppFunctionTemplateDecl),
    ):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but parameters must be owned "
            f"by function-like declarations."
        )

    if isinstance(node, (CppMethod, CppConstructor, CppField)) and not isinstance(
        owner,
        CppClassMembers,
    ):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but this member kind must be "
            f"owned by a class-like declaration."
        )

    if isinstance(node, CppEnumerator) and not isinstance(owner, CppEnum):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but enumerators must be owned "
            f"by enums."
        )

    if isinstance(node, CppEnum) and not isinstance(owner, (CppModule, CppNamespace, CppClassMembers)):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but enums must be owned by "
            f"the module root, a namespace, or a class-like declaration."
        )

    if isinstance(node, CppClass) and not isinstance(owner, (CppModule, CppNamespace, CppClassMembers)):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but classes must be owned by "
            f"the module root, a namespace, or a class-like declaration."
        )

    if isinstance(node, (CppClassTemplate, CppFunctionTemplate)) and not isinstance(
        owner,
        (CppModule, CppNamespace, CppClassMembers),
    ):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but template families must be "
            f"owned by the module root, a namespace, or a class-like declaration."
        )

    if isinstance(node, CppClassTemplateDecl) and not isinstance(owner, CppClassTemplate):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but class-template declarations "
            f"must be owned by class-template families."
        )

    if isinstance(node, CppClassTemplateInstance) and not isinstance(owner, CppClassTemplate):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but class-template instances "
            f"must be owned by class-template families."
        )

    if isinstance(node, CppFunctionTemplateDecl) and not isinstance(owner, CppFunctionTemplate):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but function-template declarations "
            f"must be owned by function-template families."
        )

    if isinstance(node, CppFunctionTemplateInstance) and not isinstance(owner, CppFunctionTemplate):
        errors.append(
            f"{path} is owned by {owner._describe_node()}, but function-template instances "
            f"must be owned by function-template families."
        )


def _validate_constructor_name(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate that constructor names match their owning class-like declaration."""

    from .member import CppConstructor

    if not isinstance(node, CppConstructor):
        return

    owner = node.owner
    if owner is None:
        return

    if node.name != owner.name:
        errors.append(
            f"{path} is named {node.name!r}, but its owning class-like declaration is "
            f"named {owner.name!r}."
        )


def _validate_method_like_flags(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate method-like flag invariants for class member callables."""

    from .class_ import CppClassMembers
    from .function_template import CppFunctionTemplateDecl, CppFunctionTemplateInstance
    from .member import CppMethod

    cpp_facet = getattr(node, "cpp", None)
    if cpp_facet is None:
        return

    if not hasattr(cpp_facet, "is_virtual"):
        return

    if not isinstance(node, (CppMethod, CppFunctionTemplateDecl, CppFunctionTemplateInstance)):
        return

    owner = node.owner
    if owner is None or not isinstance(owner, CppClassMembers):
        return

    if cpp_facet.is_pure_virtual and not cpp_facet.is_virtual:
        errors.append(
            f"{path}.cpp marks the callable as pure virtual, but not virtual."
        )

    if cpp_facet.is_static and cpp_facet.is_virtual:
        errors.append(
            f"{path}.cpp marks the callable as both static and virtual."
        )


def _validate_alias_metadata(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate qualified alias metadata stored on one scope node."""

    cpp_facet = getattr(node, "cpp", None)
    aliases = getattr(cpp_facet, "aliases", None)
    if aliases is None:
        return

    for index, alias in enumerate(aliases):
        _validate_cpp_name(
            alias.name,
            f"{path}.cpp.aliases[{index}].name",
            errors,
        )

        if alias.qualified_name is None:
            continue

        _validate_cpp_qualified_name(
            alias.qualified_name,
            f"{path}.cpp.aliases[{index}].qualified_name",
            errors,
        )

        expected_qualified_name = _expected_nested_qualified_name(node.qualified_name, alias.name)
        if alias.qualified_name != expected_qualified_name:
            errors.append(
                f"{path}.cpp.aliases[{index}] has qualified_name {alias.qualified_name!r}, "
                f"expected {expected_qualified_name!r}."
            )


def _expected_nested_qualified_name(
    scope_qualified_name: str,
    name: str,
) -> str:
    """Build the expected qualified name of one scope-local declaration."""

    if scope_qualified_name:
        return f"{scope_qualified_name}::{name}"
    return name


def _validate_template_family(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate wrapper/declaration/instance consistency of template families."""

    from .class_template import CppClassTemplate
    from .function_template import CppFunctionTemplate
    from .template_ import _validate_template_arguments

    if not isinstance(node, (CppClassTemplate, CppFunctionTemplate)):
        return

    declaration = node.declaration
    if declaration is None:
        errors.append(f"{path} does not contain a generic declaration.")
        return

    if declaration.name != node.name:
        errors.append(
            f"{path}.declaration is named {declaration.name!r}, but the template family "
            f"is named {node.name!r}."
        )

    for index, instance in enumerate(node.instances):
        if instance.name != node.name:
            errors.append(
                f"{path}.instances[{index}] is named {instance.name!r}, but the template "
                f"family is named {node.name!r}."
            )

        try:
            _validate_template_arguments(
                declaration.cpp.template_parameters,
                instance.cpp.template_arguments,
                context=f"{type(node).__name__} '{node.name}' instance {index}",
            )
        except ValueError as error:
            errors.append(f"{path}.instances[{index}] has invalid template arguments: {error}")

    for index, observed_instance in enumerate(declaration.cpp.observed_instances):
        try:
            _validate_template_arguments(
                declaration.cpp.template_parameters,
                observed_instance.arguments,
                context=f"{type(node).__name__} '{node.name}' observed instance {index}",
            )
        except ValueError as error:
            errors.append(
                f"{path}.declaration.cpp.observed_instances[{index}] has invalid template arguments: "
                f"{error}"
            )


def _validate_enumerator_value_sanity(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate simple lexical sanity of enumerator value spellings."""

    from .enum import CppEnumerator

    if not isinstance(node, CppEnumerator):
        return

    value_spelling = node.cpp.value_spelling
    if value_spelling is None:
        return

    if not value_spelling.strip():
        errors.append(
            f"{path}.cpp.value_spelling must not be empty or whitespace-only."
        )


def _validate_overload_indices(
    node: CppElement,
    path: str,
    errors: list[str],
) -> None:
    """Validate overload-index uniqueness and contiguity inside sibling groups."""

    _validate_overload_index_collection(
        getattr(node, "functions", None),
        f"{path}.functions",
        errors,
    )
    _validate_overload_index_collection(
        getattr(node, "methods", None),
        f"{path}.methods",
        errors,
    )
    _validate_overload_index_collection(
        getattr(node, "constructors", None),
        f"{path}.constructors",
        errors,
    )

    function_templates = getattr(node, "function_templates", None)
    if function_templates is not None:
        _validate_overload_index_collection(
            [template.declaration for template in function_templates if getattr(template, "declaration", None) is not None],
            f"{path}.function_templates",
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
            errors.append(
                f"{path} overload group {group_name!r} mixes set and unset overload_index "
                f"values; missing at {missing_list}."
            )
            continue

        if missing_indices:
            continue

        sorted_indices = sorted(overload_index for _, overload_index in indexed_entries)
        expected_indices = list(range(len(group)))
        if sorted_indices != expected_indices:
            errors.append(
                f"{path} overload group {group_name!r} has overload_index values "
                f"{sorted_indices}, expected {expected_indices}."
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
            errors.append(
                f"{path}.declarations[{index}] duplicates an earlier declaration location."
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
            errors.append(
                f"{path}.primary must match either .definition or one of .declarations."
            )


def _source_location_key(location: SourceLocation) -> tuple[str, int, int]:
    """Build one comparable key for a source location."""

    return (str(location.file), location.line, location.column)


def _validate_cpp_name(
    name: str,
    path: str,
    errors: list[str],
    *,
    allow_operator_names: bool = False,
) -> None:
    """Validate lexical sanity of one local C++ declaration-style name."""

    if name == "":
        return

    if name != name.strip():
        errors.append(f"{path} has leading or trailing whitespace in name {name!r}.")
        return

    if any(character in name for character in "\n\r\t"):
        errors.append(f"{path} contains control whitespace in name {name!r}.")
        return

    if allow_operator_names and name.startswith("operator"):
        return

    if not _is_cpp_identifier(name):
        errors.append(f"{path} has implausible C++ name spelling {name!r}.")


def _validate_cpp_qualified_name(
    qualified_name: str,
    path: str,
    errors: list[str],
) -> None:
    """Validate lexical sanity of one stored C++ qualified name string."""

    if qualified_name != qualified_name.strip():
        errors.append(f"{path} has leading or trailing whitespace in {qualified_name!r}.")
        return

    if any(character in qualified_name for character in " \n\r\t"):
        errors.append(f"{path} contains whitespace in {qualified_name!r}.")
        return

    parts = qualified_name.split("::")
    if any(part == "" for part in parts):
        errors.append(f"{path} has malformed scope separators in {qualified_name!r}.")
        return

    for index, part in enumerate(parts):
        _validate_cpp_name(part, f"{path}[part {index}]", errors)


def _allows_operator_name(node: CppElement) -> bool:
    """Return whether one node kind may legitimately use an operator name."""

    cpp_facet = getattr(node, "cpp", None)
    return getattr(cpp_facet, "operator", None) is not None or node.name.startswith("operator")


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
    """Check whether one declaration node may be referenced by a named type."""

    from .class_template import CppClassTemplateDecl, CppClassTemplateInstance

    return isinstance(
        declaration,
        (
            CppClass,
            CppEnum,
            CppClassTemplateDecl,
            CppClassTemplateInstance,
        ),
    )


def _named_type_matches_declaration(
    cpp_type: NamedCppType,
    declaration: CppElement,
) -> bool:
    """Check whether one named-type spelling is compatible with its declaration."""

    normalized_name = cpp_type.name.removeprefix("::")
    original_name = getattr(getattr(declaration, "cpp", None), "original_name", None)

    if "::" in normalized_name:
        return normalized_name == declaration.qualified_name

    valid_names = {declaration.name}
    if original_name is not None:
        valid_names.add(original_name)
    return normalized_name in valid_names
