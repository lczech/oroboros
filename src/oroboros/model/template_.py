from __future__ import annotations

"""Shared template value objects plus cross-family template helpers."""

from dataclasses import dataclass, field as dataclass_field
from typing import Literal

from .element import CppElement
from .location import SourceLocation
from .type import CppType


# ==================================================================================================
#     Template Values
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Parameters
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppTemplateParameter:
    """Represent one declared parameter slot of a C++ template."""

    name: str
    default: CppTemplateArgument | None = None
    is_parameter_pack: bool = False

    def render(self) -> str:
        """Render the parameter into a C++-like string form."""

        raise NotImplementedError


@dataclass(slots=True)
class CppTypeTemplateParameter(CppTemplateParameter):
    """Represent one type template parameter."""

    keyword: Literal["typename", "class"] = "typename"

    def render(self) -> str:
        rendered = f"{self.keyword} {self.name}"
        if self.is_parameter_pack:
            rendered = f"{self.keyword}... {self.name}"
        if self.default is not None:
            return f"{rendered} = {self.default.render()}"
        return rendered


@dataclass(slots=True)
class CppNonTypeTemplateParameter(CppTemplateParameter):
    """Represent one non-type template parameter."""

    type: CppType | None = None

    def render(self) -> str:
        rendered_type = self.type.render() if self.type is not None else ""
        rendered = f"{rendered_type} {self.name}".strip()
        if self.is_parameter_pack:
            rendered = f"{rendered_type}... {self.name}".strip()
        if self.default is not None:
            return f"{rendered} = {self.default.render()}"
        return rendered


@dataclass(slots=True)
class CppTemplateTemplateParameter(CppTemplateParameter):
    """Represent one template-template parameter with recursive inner slots."""

    parameters: list[CppTemplateParameter] = dataclass_field(default_factory=list)

    def render(self) -> str:
        inner = ", ".join(parameter.render() for parameter in self.parameters)
        rendered = f"template <{inner}> class {self.name}"
        if self.is_parameter_pack:
            rendered = f"template <{inner}> class... {self.name}"
        if self.default is not None:
            return f"{rendered} = {self.default.render()}"
        return rendered


# ------------------------------------------------------------------------------
#     Arguments
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppTemplateArgument:
    """Represent one concrete argument supplied to a C++ template."""

    def render(self) -> str:
        """Render the argument into a C++-like string form."""

        raise NotImplementedError


@dataclass(slots=True)
class CppTypeTemplateArgument(CppTemplateArgument):
    """Represent one type template argument."""

    type: CppType | None = None

    def render(self) -> str:
        return self.type.render() if self.type is not None else ""


@dataclass(slots=True)
class CppNonTypeTemplateArgument(CppTemplateArgument):
    """Represent one non-type template argument."""

    value: str = ""
    type: CppType | None = None

    def render(self) -> str:
        return self.value


@dataclass(slots=True)
class CppTemplateTemplateArgument(CppTemplateArgument):
    """Represent one template-template argument."""

    name: str = ""
    parameters: list["CppTemplateParameter"] = dataclass_field(default_factory=list)

    def render(self) -> str:
        return self.name


# ------------------------------------------------------------------------------
#     Observed Instances
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppObservedTemplateInstance:
    """Store one concrete template instantiation observed in parsed C++ code."""

    arguments: list[CppTemplateArgument] = dataclass_field(default_factory=list)
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
        if not isinstance(argument, CppTypeTemplateArgument):
            raise ValueError(
                f"{context} expects a type argument for '{parameter.name}', "
                f"got {type(argument).__name__}."
            )
        return

    if isinstance(parameter, CppNonTypeTemplateParameter):
        if not isinstance(argument, CppNonTypeTemplateArgument):
            raise ValueError(
                f"{context} expects a non-type argument for '{parameter.name}', "
                f"got {type(argument).__name__}."
            )
        return

    if isinstance(parameter, CppTemplateTemplateParameter):
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


def _template_argument_key(arguments: list[CppTemplateArgument]) -> tuple[tuple[str, str], ...]:
    """Build a stable equality key for one template argument sequence."""

    return tuple((type(argument).__name__, argument.render()) for argument in arguments)


# ==================================================================================================
#     Split Type Imports
# ==================================================================================================


from .class_template import (  # noqa: E402
    CppClassTemplate,
    CppClassTemplateDecl,
    CppClassTemplateDeclCppFacet,
    CppClassTemplateDefaults,
    CppClassTemplateInstance,
    CppClassTemplateInstanceCppFacet,
    add_class_template_instance,
)
from .function_template import (  # noqa: E402
    CppFunctionTemplate,
    CppFunctionTemplateDecl,
    CppFunctionTemplateDeclCppFacet,
    CppFunctionTemplateDefaults,
    CppFunctionTemplateInstance,
    CppFunctionTemplateInstanceCppFacet,
    add_function_template_instance,
)


# ==================================================================================================
#     Cross-Family Helpers
# ==================================================================================================


TemplateFamily = CppClassTemplate | CppFunctionTemplate
TemplateScope = CppElement


def add_template_instance(
    template: TemplateFamily,
    arguments: list[CppTemplateArgument],
) -> CppClassTemplateInstance | CppFunctionTemplateInstance:
    """Create or return one concrete template instance under a template family."""

    if isinstance(template, CppClassTemplate):
        return add_class_template_instance(template, arguments)
    if isinstance(template, CppFunctionTemplate):
        return add_function_template_instance(template, arguments)
    raise TypeError(f"Unsupported template family type: {type(template)!r}")


def add_observed_template_instances(
    scope: TemplateScope,
    *,
    include_class_templates: bool = True,
    include_function_templates: bool = True,
    recurse: bool = True,
) -> list[CppElement]:
    """Materialize template instances previously observed in the parsed C++ subtree.

    "Observed" here means concrete template instantiations that were encountered
    while parsing the C++ codebase, not instances requested manually through
    binding configuration.
    """

    created_instances: list[CppElement] = []

    for class_template in _iter_class_templates(scope, recurse=recurse):
        if not include_class_templates:
            continue
        for observed_instance in class_template.declaration.cpp.observed_instances:
            created_instances.append(
                add_class_template_instance(
                    class_template,
                    observed_instance.arguments,
                )
            )

    for function_template in _iter_function_templates(scope, recurse=recurse):
        if not include_function_templates:
            continue
        for observed_instance in function_template.declaration.cpp.observed_instances:
            created_instances.append(
                add_function_template_instance(
                    function_template,
                    observed_instance.arguments,
                )
            )

    return created_instances


def _iter_class_templates(
    scope: TemplateScope,
    *,
    recurse: bool,
) -> list[CppClassTemplate]:
    """Collect class template families below one scope."""

    templates: list[CppClassTemplate] = []
    if isinstance(scope, CppClassTemplate):
        templates.append(scope)
    else:
        templates.extend(getattr(scope, "class_templates", []))

    if not recurse:
        return templates

    nested_scopes = _iter_nested_template_scopes(scope)
    for nested_scope in nested_scopes:
        templates.extend(_iter_class_templates(nested_scope, recurse=True))
    return templates


def _iter_function_templates(
    scope: TemplateScope,
    *,
    recurse: bool,
) -> list[CppFunctionTemplate]:
    """Collect function template families below one scope."""

    templates: list[CppFunctionTemplate] = []
    if isinstance(scope, CppFunctionTemplate):
        templates.append(scope)
    else:
        templates.extend(getattr(scope, "function_templates", []))

    if not recurse:
        return templates

    nested_scopes = _iter_nested_template_scopes(scope)
    for nested_scope in nested_scopes:
        templates.extend(_iter_function_templates(nested_scope, recurse=True))
    return templates


def _iter_nested_template_scopes(scope: TemplateScope) -> list[CppElement]:
    """Return nested scopes that may themselves contain template declarations."""

    if isinstance(scope, CppClassTemplate):
        return [scope.declaration]

    nested_scopes = list(getattr(scope, "namespaces", [])) + list(getattr(scope, "classes", []))
    nested_scopes.extend(
        template.declaration for template in getattr(scope, "class_templates", [])
    )
    return nested_scopes
