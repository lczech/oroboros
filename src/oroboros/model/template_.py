from __future__ import annotations

"""Template declaration, instance, and helper model objects."""

from copy import deepcopy
from dataclasses import dataclass, field as dataclass_field
from typing import TYPE_CHECKING, Literal

from .class_ import (
    CppClass,
    CppClassBindFacet,
    CppClassCppFacet,
    CppClassMembers,
    CppField,
    CppFieldBindFacet,
)
from .element import CppElement
from .function import (
    CppFunction,
    CppFunctionBindFacet,
    CppFunctionCppFacet,
    CppParameter,
)
from .location import SourceLocation
from .member import CppConstructor, CppMethod
from .type import CppType

if TYPE_CHECKING:
    from .enum import CppEnumBindFacet


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
    """Store one concrete template instantiation observed during parsing."""

    arguments: list[CppTemplateArgument] = dataclass_field(default_factory=list)
    locations: list[SourceLocation] = dataclass_field(default_factory=list)


# ==================================================================================================
#     Facets
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Class
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppClassTemplateDeclCppFacet(CppClassCppFacet):
    """Store parsed C++ details for one generic class template declaration."""

    template_parameters: list[CppTemplateParameter] = dataclass_field(default_factory=list)
    observed_instances: list[CppObservedTemplateInstance] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppClassTemplateInstanceCppFacet(CppClassCppFacet):
    """Store parsed C++ details for one concrete class template instance."""

    template_arguments: list[CppTemplateArgument] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppClassTemplateDefaults:
    """Store defaults applied to selected class template instances and their descendants."""

    # Defaults applied to each selected class template instance itself.
    instance: CppClassBindFacet = dataclass_field(default_factory=CppClassBindFacet)
    # Defaults applied to nested classes inside selected instances.
    class_: CppClassBindFacet = dataclass_field(default_factory=CppClassBindFacet)
    # Defaults applied to methods inside selected instances.
    method: CppFunctionBindFacet = dataclass_field(default_factory=CppFunctionBindFacet)
    # Defaults applied to constructors inside selected instances.
    constructor: CppFunctionBindFacet = dataclass_field(default_factory=CppFunctionBindFacet)
    # Defaults applied to fields inside selected instances.
    field: CppFieldBindFacet = dataclass_field(default_factory=CppFieldBindFacet)
    # Defaults applied to enums inside selected instances.
    enum: "CppEnumBindFacet" = dataclass_field(default_factory=lambda: _make_enum_bind_facet())


def _make_enum_bind_facet() -> "CppEnumBindFacet":
    """Create one enum-bind facet without import cycles at module import time."""

    from .enum import CppEnumBindFacet

    return CppEnumBindFacet()


# ------------------------------------------------------------------------------
#     Function
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppFunctionTemplateDeclCppFacet(CppFunctionCppFacet):
    """Store parsed C++ details for one generic function template declaration."""

    template_parameters: list[CppTemplateParameter] = dataclass_field(default_factory=list)
    observed_instances: list[CppObservedTemplateInstance] = dataclass_field(default_factory=list)
    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_pure_virtual: bool = False


@dataclass(slots=True)
class CppFunctionTemplateInstanceCppFacet(CppFunctionCppFacet):
    """Store parsed C++ details for one concrete function template instance."""

    template_arguments: list[CppTemplateArgument] = dataclass_field(default_factory=list)
    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_pure_virtual: bool = False


@dataclass(slots=True)
class CppFunctionTemplateDefaults:
    """Store defaults applied to selected function template instances."""

    # Defaults applied to each selected function template instance itself.
    instance: CppFunctionBindFacet = dataclass_field(default_factory=CppFunctionBindFacet)


# ==================================================================================================
#     Elements
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Declarations
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppClassTemplateDecl(CppClassMembers):
    """Represent one generic class template declaration without binding state."""

    # Parsed C++ details for the generic class template declaration.
    cpp: CppClassTemplateDeclCppFacet = dataclass_field(default_factory=CppClassTemplateDeclCppFacet)


@dataclass(slots=True)
class CppFunctionTemplateDecl(CppElement):
    """Represent one generic function template declaration without binding state."""

    # Parsed C++ details for the generic function template declaration.
    cpp: CppFunctionTemplateDeclCppFacet = dataclass_field(default_factory=CppFunctionTemplateDeclCppFacet)
    # Parameters declared directly on this generic function template declaration.
    parameters: list[CppParameter] = dataclass_field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self.adopt_children(self.parameters)


# ------------------------------------------------------------------------------
#     Instances
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppClassTemplateInstance(CppClass):
    """Represent one selected class template instantiation to be bound."""

    # Parsed C++ details for this concrete class template instance.
    cpp: CppClassTemplateInstanceCppFacet = dataclass_field(default_factory=CppClassTemplateInstanceCppFacet)


@dataclass(slots=True)
class CppFunctionTemplateInstance(CppFunction):
    """Represent one selected function template instantiation to be bound."""

    # Parsed C++ details for this concrete function template instance.
    cpp: CppFunctionTemplateInstanceCppFacet = dataclass_field(default_factory=CppFunctionTemplateInstanceCppFacet)


# ------------------------------------------------------------------------------
#     Template Families
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppClassTemplate(CppElement):
    """Group one generic class template declaration with its selected instances."""

    # Parsed generic class template declaration, including observed instances.
    declaration: CppClassTemplateDecl | None = None
    # Selected concrete instantiations to bind for this template family.
    instances: list[CppClassTemplateInstance] = dataclass_field(default_factory=list)
    # Defaults applied to selected instances and their descendants.
    defaults: CppClassTemplateDefaults = dataclass_field(default_factory=CppClassTemplateDefaults)

    @property
    def scope_name(self) -> str | None:
        """Keep the template-family wrapper out of C++ qualified names."""

        return None

    def __post_init__(self) -> None:
        """Create and adopt the generic declaration plus any selected instances."""

        declaration = self.declaration
        if declaration is None:
            declaration = CppClassTemplateDecl(name=self.name)
        _synchronize_template_name(self, declaration)
        self.declaration = declaration

        self.adopt_children([self.declaration])
        self.adopt_children(self.instances)


@dataclass(slots=True)
class CppFunctionTemplate(CppElement):
    """Group one generic function template declaration with its selected instances."""

    # Parsed generic function template declaration, including observed instances.
    declaration: CppFunctionTemplateDecl | None = None
    # Selected concrete instantiations to bind for this template family.
    instances: list[CppFunctionTemplateInstance] = dataclass_field(default_factory=list)
    # Defaults applied to selected instances of this template family.
    defaults: CppFunctionTemplateDefaults = dataclass_field(default_factory=CppFunctionTemplateDefaults)

    @property
    def scope_name(self) -> str | None:
        """Keep the template-family wrapper out of C++ qualified names."""

        return None

    def __post_init__(self) -> None:
        """Create and adopt the generic declaration plus any selected instances."""

        declaration = self.declaration
        if declaration is None:
            declaration = CppFunctionTemplateDecl(name=self.name)
        _synchronize_template_name(self, declaration)
        self.declaration = declaration

        self.adopt_children([self.declaration])
        self.adopt_children(self.instances)


# ==================================================================================================
#     Helpers
# ==================================================================================================


TemplateFamily = CppClassTemplate | CppFunctionTemplate
TemplateScope = CppElement


# ------------------------------------------------------------------------------
#     Adding Instance Functions
# ------------------------------------------------------------------------------


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


def add_class_template_instance(
    template: CppClassTemplate,
    arguments: list[CppTemplateArgument],
) -> CppClassTemplateInstance:
    """Create or return one concrete class template instance under a template family."""

    existing_instance = _find_existing_class_template_instance(template, arguments)
    if existing_instance is not None:
        return existing_instance

    declaration = template.declaration
    if declaration is None:
        raise ValueError("Class template family does not contain a generic declaration.")

    _validate_template_arguments(
        declaration.cpp.template_parameters,
        arguments,
        context=f"class template '{template.name}'",
    )

    instance = CppClassTemplateInstance(
        name=template.name,
        cpp=CppClassTemplateInstanceCppFacet(
            original_name=declaration.cpp.original_name,
            qualified_name=declaration.cpp.qualified_name,
            location=declaration.cpp.location,
            comment=declaration.cpp.comment,
            doc=declaration.cpp.doc,
            kind=declaration.cpp.kind,
            bases=deepcopy(declaration.cpp.bases),
            template_arguments=deepcopy(arguments),
        ),
        classes=_copy_children(declaration.classes),
        constructors=_copy_children(declaration.constructors),
        methods=_copy_children(declaration.methods),
        fields=_copy_children(declaration.fields),
        enums=_copy_children(declaration.enums),
        class_templates=_copy_children(declaration.class_templates),
        function_templates=_copy_children(declaration.function_templates),
    )
    template.instances.append(instance)
    template.adopt_children([instance])
    return instance


def add_function_template_instance(
    template: CppFunctionTemplate,
    arguments: list[CppTemplateArgument],
) -> CppFunctionTemplateInstance:
    """Create or return one concrete function template instance under a template family."""

    existing_instance = _find_existing_function_template_instance(template, arguments)
    if existing_instance is not None:
        return existing_instance

    declaration = template.declaration
    if declaration is None:
        raise ValueError("Function template family does not contain a generic declaration.")

    _validate_template_arguments(
        declaration.cpp.template_parameters,
        arguments,
        context=f"function template '{template.name}'",
    )

    instance = CppFunctionTemplateInstance(
        name=template.name,
        cpp=CppFunctionTemplateInstanceCppFacet(
            original_name=declaration.cpp.original_name,
            qualified_name=declaration.cpp.qualified_name,
            operator=deepcopy(declaration.cpp.operator),
            return_type=deepcopy(declaration.cpp.return_type),
            location=declaration.cpp.location,
            comment=declaration.cpp.comment,
            doc=declaration.cpp.doc,
            overload_index=declaration.cpp.overload_index,
            is_noexcept=declaration.cpp.is_noexcept,
            template_arguments=deepcopy(arguments),
            is_const=declaration.cpp.is_const,
            is_static=declaration.cpp.is_static,
            is_virtual=declaration.cpp.is_virtual,
            is_pure_virtual=declaration.cpp.is_pure_virtual,
        ),
        parameters=_copy_children(declaration.parameters),
    )
    template.instances.append(instance)
    template.adopt_children([instance])
    return instance


def add_observed_template_instances(
    scope: TemplateScope,
    *,
    include_class_templates: bool = True,
    include_function_templates: bool = True,
    recurse: bool = True,
) -> list[CppElement]:
    """Materialize observed template instances within one subtree."""

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


# ------------------------------------------------------------------------------
#     Internal Helpers
# ------------------------------------------------------------------------------


def _copy_children(children: list[CppElement]) -> list[CppElement]:
    """Deep-copy one direct child collection for a materialized instance."""

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


def _find_existing_class_template_instance(
    template: CppClassTemplate,
    arguments: list[CppTemplateArgument],
) -> CppClassTemplateInstance | None:
    """Return an existing class instance with the same template arguments, if any."""

    argument_key = _template_argument_key(arguments)
    for instance in template.instances:
        if _template_argument_key(instance.cpp.template_arguments) == argument_key:
            return instance
    return None


def _find_existing_function_template_instance(
    template: CppFunctionTemplate,
    arguments: list[CppTemplateArgument],
) -> CppFunctionTemplateInstance | None:
    """Return an existing function instance with the same template arguments, if any."""

    argument_key = _template_argument_key(arguments)
    for instance in template.instances:
        if _template_argument_key(instance.cpp.template_arguments) == argument_key:
            return instance
    return None


def _template_argument_key(arguments: list[CppTemplateArgument]) -> tuple[tuple[str, str], ...]:
    """Build a stable equality key for one template argument sequence."""

    return tuple((type(argument).__name__, argument.render()) for argument in arguments)
