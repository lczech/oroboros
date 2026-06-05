from __future__ import annotations

"""Shared template value objects plus cross-family template helpers."""

from dataclasses import dataclass, field as dataclass_field
from typing import Literal

from .element import CppElement
from .location import SourceLocation
from .type import CppType, cpp_type_key


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppTemplateBindFacet:
    """Store binding policy attached to one template family."""
    pass


# ==================================================================================================
#     Template Values
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Parameters
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppTemplateParameter:
    """Represent one declared parameter slot of a C++ template."""

    # Source-spelled parameter name, which may be empty for unnamed slots.
    name: str
    # Optional default argument placeholder; currently unused by the parser/emitter pipeline.
    default: CppTemplateArgument | None = None
    # Whether this slot accepts a parameter pack.
    is_parameter_pack: bool = False


@dataclass(slots=True)
class CppTypeTemplateParameter(CppTemplateParameter):
    """Represent one type template parameter."""

    # Whether this slot binds a type, such as the `T` in `template<class T>`.
    # Preserve whether the declaration spelled that type slot as `typename` or `class`.
    keyword: Literal["typename", "class"] = "typename"


@dataclass(slots=True)
class CppNonTypeTemplateParameter(CppTemplateParameter):
    """Represent one non-type template parameter."""

    # Whether this slot binds a value, such as the `N` in `template<int N>`.
    # Store the declared type of that value slot, for example `int` or `std::size_t`.
    type: CppType | None = None


@dataclass(slots=True)
class CppTemplateTemplateParameter(CppTemplateParameter):
    """Represent one template-template parameter with recursive inner slots."""

    # Inner parameter signature accepted by the template-template argument.
    parameters: list[CppTemplateParameter] = dataclass_field(default_factory=list)


# ------------------------------------------------------------------------------
#     Arguments
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppTemplateArgument:
    """Represent one concrete argument supplied to a C++ template."""


@dataclass(slots=True)
class CppTypeTemplateArgument(CppTemplateArgument):
    """Represent one type template argument."""

    # Structured type supplied to this argument slot.
    type: CppType | None = None


@dataclass(slots=True)
class CppNonTypeTemplateArgument(CppTemplateArgument):
    """Represent one non-type template argument."""

    # Source-spelled value expression such as `4` or `true`.
    value: str = ""
    # Optional semantic type of the value when clang exposes it.
    type: CppType | None = None


@dataclass(slots=True)
class CppTemplateTemplateArgument(CppTemplateArgument):
    """Represent one template-template argument."""

    # Source-spelled template family name such as `Allocator`.
    name: str = ""
    # Declared inner template-parameter signature when known.
    parameters: list["CppTemplateParameter"] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppOpaqueTemplateArgument(CppTemplateArgument):
    """Represent one template argument whose semantic kind is intentionally unresolved."""

    # Whitespace-normalized source spelling for one argument whose boundaries are trusted.
    spelling: str = ""

    def __post_init__(self) -> None:
        self.spelling = "".join(self.spelling.split())


# ------------------------------------------------------------------------------
#     Observation Hints
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppTemplateObservationHint:
    """Store one raw template-instantiation spelling observed in parsed C++ code."""

    # Whitespace-normalized template spelling observed at one use site, e.g. "demo::Vec<int>".
    spelling: str
    # Source locations where this normalized spelling was observed.
    locations: list[SourceLocation] = dataclass_field(default_factory=list)


# ==================================================================================================
#     Shared Helpers
# ==================================================================================================


def _copy_children(children: list[CppElement]) -> list[CppElement]:
    """Deep-copy one direct child collection for a materialized instance."""

    from copy import deepcopy

    return [deepcopy(child) for child in children]


def _validate_template_arguments(
    parameters: list[CppTemplateParameter],
    arguments: list[CppTemplateArgument],
    *,
    context: str,
) -> None:
    """Validate one structural template argument list against declared parameters."""

    _validate_template_argument_sequence(
        parameters,
        arguments,
        context=context,
    )


def _validate_template_argument_sequence(
    parameters: list[CppTemplateParameter],
    arguments: list[CppTemplateArgument],
    *,
    context: str,
) -> None:
    """Validate one parameter/argument sequence, including packs and defaults."""

    if not parameters:
        if arguments:
            raise ValueError(
                f"{context} received too many template arguments: "
                f"expected 0, got {len(arguments)}."
            )
        return

    parameter = parameters[0]
    remaining_parameters = parameters[1:]

    if parameter.is_parameter_pack:
        last_error: ValueError | None = None
        for consumed_count in range(len(arguments) + 1):
            consumed_arguments = arguments[:consumed_count]
            try:
                for consumed_argument in consumed_arguments:
                    _validate_template_argument_kind(
                        parameter,
                        consumed_argument,
                        context=context,
                    )
                _validate_template_argument_sequence(
                    remaining_parameters,
                    arguments[consumed_count:],
                    context=context,
                )
                return
            except ValueError as error:
                last_error = error

        if last_error is not None:
            raise last_error
        raise ValueError(
            f"{context} could not match the template parameter pack '{parameter.name}'."
        )

    if not arguments:
        if parameter.default is not None:
            _validate_template_argument_sequence(
                remaining_parameters,
                arguments,
                context=context,
            )
            return
        raise ValueError(
            f"{context} is missing a template argument for '{parameter.name}'."
        )

    _validate_template_argument_kind(
        parameter,
        arguments[0],
        context=context,
    )
    _validate_template_argument_sequence(
        remaining_parameters,
        arguments[1:],
        context=context,
    )


def _validate_template_argument_kind(
    parameter: CppTemplateParameter,
    argument: CppTemplateArgument,
    *,
    context: str,
) -> None:
    """Validate one structural template argument kind against one parameter slot."""

    if isinstance(parameter, CppTypeTemplateParameter):
        if isinstance(argument, CppOpaqueTemplateArgument):
            raise ValueError(
                f"{context} received parse-only opaque argument {argument.spelling!r} for '{parameter.name}'; "
                "replace it with a semantic type argument before binding."
            )
        if not isinstance(argument, CppTypeTemplateArgument):
            raise ValueError(
                f"{context} expects a type argument for '{parameter.name}', "
                f"got {type(argument).__name__}."
            )
        return

    if isinstance(parameter, CppNonTypeTemplateParameter):
        if isinstance(argument, CppOpaqueTemplateArgument):
            raise ValueError(
                f"{context} received parse-only opaque argument {argument.spelling!r} for '{parameter.name}'; "
                "replace it with a semantic non-type argument before binding."
            )
        if not isinstance(argument, CppNonTypeTemplateArgument):
            raise ValueError(
                f"{context} expects a non-type argument for '{parameter.name}', "
                f"got {type(argument).__name__}."
            )
        return

    if isinstance(parameter, CppTemplateTemplateParameter):
        if isinstance(argument, CppOpaqueTemplateArgument):
            raise ValueError(
                f"{context} received parse-only opaque argument {argument.spelling!r} for '{parameter.name}'; "
                "replace it with a semantic template-template argument before binding."
            )
        if not isinstance(argument, CppTemplateTemplateArgument):
            raise ValueError(
                f"{context} expects a template-template argument for '{parameter.name}', "
                f"got {type(argument).__name__}."
            )
        _validate_template_template_parameter_shape(
            parameter.parameters,
            argument.parameters,
            context=f"{context} template-template argument '{argument.name or parameter.name}'",
        )
        return

    raise TypeError(f"Unsupported template parameter type: {type(parameter)!r}")


def _validate_template_template_parameter_shape(
    expected_parameters: list[CppTemplateParameter],
    actual_parameters: list[CppTemplateParameter],
    *,
    context: str,
) -> None:
    """Validate one template-template argument signature recursively by structure."""

    if len(expected_parameters) != len(actual_parameters):
        raise ValueError(
            f"{context} has the wrong number of inner template parameters: "
            f"expected {len(expected_parameters)}, got {len(actual_parameters)}."
        )

    for index, (expected_parameter, actual_parameter) in enumerate(
        zip(expected_parameters, actual_parameters, strict=True),
        start=1,
    ):
        if type(expected_parameter) is not type(actual_parameter):
            raise ValueError(
                f"{context} parameter {index} has the wrong kind: "
                f"expected {type(expected_parameter).__name__}, "
                f"got {type(actual_parameter).__name__}."
            )

        if expected_parameter.is_parameter_pack != actual_parameter.is_parameter_pack:
            raise ValueError(
                f"{context} parameter {index} has incompatible pack usage."
            )

        if isinstance(expected_parameter, CppTemplateTemplateParameter):
            _validate_template_template_parameter_shape(
                expected_parameter.parameters,
                actual_parameter.parameters,
                context=f"{context} parameter {index}",
            )


def _synchronize_template_name(
    template: CppElement,
    declaration: CppElement,
) -> None:
    """Keep a template wrapper and its generic declaration on the same name."""

    if declaration.name:
        template.name = declaration.name
    else:
        declaration.name = template.name


def _template_argument_key(arguments: list[CppTemplateArgument]) -> tuple[tuple[object, ...], ...]:
    """Build a stable equality key for one template argument sequence."""

    return tuple(_single_template_argument_key(argument) for argument in arguments)


def _single_template_argument_key(argument: CppTemplateArgument) -> tuple[object, ...]:
    """Build one structural identity key for a concrete template argument."""

    if isinstance(argument, CppTypeTemplateArgument):
        return ("type", cpp_type_key(argument.type))

    if isinstance(argument, CppNonTypeTemplateArgument):
        # Treat non-type arguments with the same value spelling as the same observed
        # specialization even when only one path carried optional semantic type data.
        return ("non_type", argument.value)

    if isinstance(argument, CppTemplateTemplateArgument):
        return (
            "template_template",
            argument.name,
            tuple(_template_parameter_shape_key(parameter) for parameter in argument.parameters),
        )

    if isinstance(argument, CppOpaqueTemplateArgument):
        return ("opaque", argument.spelling)

    raise TypeError(f"Unsupported template argument type: {type(argument)!r}")


def _template_parameter_shape_key(parameter: CppTemplateParameter) -> tuple[object, ...]:
    """Build one structural shape key for a template parameter slot."""

    if isinstance(parameter, CppTypeTemplateParameter):
        return ("type_parameter", parameter.is_parameter_pack)

    if isinstance(parameter, CppNonTypeTemplateParameter):
        return ("non_type_parameter", parameter.is_parameter_pack, cpp_type_key(parameter.type))

    if isinstance(parameter, CppTemplateTemplateParameter):
        return (
            "template_template_parameter",
            parameter.is_parameter_pack,
            tuple(_template_parameter_shape_key(inner) for inner in parameter.parameters),
        )

    raise TypeError(f"Unsupported template parameter type: {type(parameter)!r}")


def _find_existing_semantic_template_instance(
    instances: list[CppElement],
    arguments: list[CppTemplateArgument],
) -> CppElement | None:
    """Return an existing semantic instance with the same structured arguments."""

    argument_key = _template_argument_key(arguments)
    for instance in instances:
        if _template_argument_key(getattr(instance.cpp, "template_arguments", [])) == argument_key:
            return instance
    return None


def _add_manual_template_instance(
    template: CppElement,
    arguments: list[CppTemplateArgument],
    *,
    context: str,
    instance_type: type[CppElement],
    instance_cpp_type: type[object],
) -> CppElement:
    """Create or reuse one semantic template instance under one template family."""

    declaration = getattr(template, "declaration", None)
    if declaration is None:
        raise ValueError("Template family does not contain a generic declaration.")

    _validate_template_arguments(
        declaration.cpp.template_parameters,
        arguments,
        context=context,
    )

    existing_instance = _find_existing_semantic_template_instance(
        getattr(template, "instances"),
        arguments,
    )
    if existing_instance is not None:
        return existing_instance

    instance = instance_type(
        name=template.name,
        cpp=instance_cpp_type(
            template_arguments=list(arguments),
        ),
    )
    return template.add_instance(instance)


# ==================================================================================================
#     Split Type Imports
# ==================================================================================================


from .class_template import (  # noqa: E402
    CppClassTemplate,
    CppClassTemplateDeclaration,
    CppClassTemplateDeclarationCppFacet,
    CppClassTemplateDefaults,
    CppClassTemplateInstance,
    CppClassTemplateInstanceCppFacet,
    add_class_template_instance,
)
from .class_ import CppClassMembers  # noqa: E402
from .module import CppModule  # noqa: E402
from .namespace import CppNamespace  # noqa: E402
from .alias_template import (  # noqa: E402
    CppAliasTemplate,
    CppAliasTemplateDeclaration,
    CppAliasTemplateDeclarationCppFacet,
    CppAliasTemplateInstance,
    CppAliasTemplateInstanceCppFacet,
    add_alias_template_instance,
)
from .function_template import (  # noqa: E402
    CppFunctionTemplate,
    CppFunctionTemplateDeclaration,
    CppFunctionTemplateDeclarationCppFacet,
    CppFunctionTemplateDefaults,
    CppFunctionTemplateInstance,
    CppFunctionTemplateInstanceCppFacet,
    add_function_template_instance,
)
from .method_template import (  # noqa: E402
    CppMethodTemplate,
    CppMethodTemplateDeclaration,
    CppMethodTemplateDeclarationCppFacet,
    CppMethodTemplateDefaults,
    CppMethodTemplateInstance,
    CppMethodTemplateInstanceCppFacet,
    add_method_template_instance,
)


# ==================================================================================================
#     Cross-Family Helpers
# ==================================================================================================


TemplateFamily = CppAliasTemplate | CppClassTemplate | CppFunctionTemplate | CppMethodTemplate


def add_template_instance(
    template: TemplateFamily,
    arguments: list[CppTemplateArgument],
) -> CppAliasTemplateInstance | CppClassTemplateInstance | CppFunctionTemplateInstance | CppMethodTemplateInstance:
    """Create or return one concrete template instance under a template family."""

    if isinstance(template, CppAliasTemplate):
        return add_alias_template_instance(template, arguments)
    if isinstance(template, CppClassTemplate):
        return add_class_template_instance(template, arguments)
    if isinstance(template, CppFunctionTemplate):
        return add_function_template_instance(template, arguments)
    if isinstance(template, CppMethodTemplate):
        return add_method_template_instance(template, arguments)
    raise TypeError(f"Unsupported template family type: {type(template)!r}")
