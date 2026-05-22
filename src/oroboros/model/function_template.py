from __future__ import annotations

"""Function-template model objects and helpers."""

from dataclasses import dataclass, field as dataclass_field

from .element import CppElement
from .function import CppFunctionBindFacet, CppFunctionCppFacet, CppFunctionPyFacet, CppParameter
from .template_ import (
    CppObservedTemplateInstance,
    CppTemplateArgument,
    CppTemplateBindFacet,
    CppTemplateParameter,
    _synchronize_template_name,
    _template_argument_key,
    _validate_template_arguments,
)


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppFunctionTemplateDeclarationCppFacet(CppFunctionCppFacet):
    """Store parsed C++ details for one generic function template declaration."""

    template_parameters: list[CppTemplateParameter] = dataclass_field(default_factory=list)
    observed_instances: list[CppObservedTemplateInstance] = dataclass_field(default_factory=list)
    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_pure_virtual: bool = False


@dataclass(slots=True)
class CppFunctionTemplateInstanceCppFacet:
    """Store selected template arguments for one function template instance."""

    template_arguments: list[CppTemplateArgument] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppFunctionTemplateDefaults:
    """Store defaults applied to selected function template instances."""

    # Defaults applied to each selected function template instance itself.
    instance: CppFunctionBindFacet = dataclass_field(default_factory=CppFunctionBindFacet)


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppFunctionTemplateDeclaration(CppElement):
    """Represent one generic function template declaration without binding state."""

    # Parsed C++ details for the generic function template declaration.
    cpp: CppFunctionTemplateDeclarationCppFacet = dataclass_field(
        default_factory=CppFunctionTemplateDeclarationCppFacet
    )
    # Parameters declared directly on this generic function template declaration.
    parameters: list[CppParameter] = dataclass_field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self._adopt_children(self.parameters)

    def add_parameter(self, parameter: CppParameter) -> CppParameter:
        """Attach one parameter to this generic function template declaration."""

        return self._append_child(self.parameters, parameter)


@dataclass(slots=True)
class CppFunctionTemplateInstance(CppElement):
    """Represent one selected function template instantiation as a binding target."""

    # Selected template arguments for this concrete function template instance.
    cpp: CppFunctionTemplateInstanceCppFacet = dataclass_field(default_factory=CppFunctionTemplateInstanceCppFacet)
    # Binding settings attached directly to this selected instance.
    bind: CppFunctionBindFacet = dataclass_field(default_factory=CppFunctionBindFacet)
    # Python-facing choices attached directly to this selected instance.
    py: CppFunctionPyFacet = dataclass_field(default_factory=CppFunctionPyFacet)


@dataclass(slots=True)
class CppFunctionTemplate(CppElement):
    """Group one generic function template declaration with its selected instances."""

    # Binding policy attached to this template family wrapper itself.
    bind: CppTemplateBindFacet = dataclass_field(default_factory=CppTemplateBindFacet)
    # Parsed generic function template declaration, including observed instances.
    declaration: CppFunctionTemplateDeclaration | None = None
    # Selected concrete instantiations to bind for this template family.
    instances: list[CppFunctionTemplateInstance] = dataclass_field(default_factory=list)
    # Defaults applied to selected instances of this template family.
    defaults: CppFunctionTemplateDefaults = dataclass_field(default_factory=CppFunctionTemplateDefaults)

    @property
    def scope_name(self) -> str | None:
        """Keep the template-family wrapper out of C++ qualified names."""

        return None

    @property
    def qualified_name(self) -> str:
        """Return the semantic qualified name of this template family wrapper."""

        declaration = self.declaration
        if declaration is not None:
            return declaration.qualified_name
        return super().qualified_name

    def __post_init__(self) -> None:
        """Create and adopt the generic declaration plus any selected instances."""

        declaration = self.declaration
        if declaration is None:
            declaration = CppFunctionTemplateDeclaration(name=self.name)
        _synchronize_template_name(self, declaration)
        self.declaration = declaration

        self._adopt_children([self.declaration])
        self._adopt_children(self.instances)

    def add_instance(self, instance: CppFunctionTemplateInstance) -> CppFunctionTemplateInstance:
        """Attach one selected function template instance to this family."""

        return self._append_child(self.instances, instance)

    def add_observed_instances(self) -> list[CppFunctionTemplateInstance]:
        """Materialize all parser-observed instances attached to this template family."""

        return [
            add_function_template_instance(self, observed_instance.arguments)
            for observed_instance in self.declaration.cpp.observed_instances
        ]


# ==================================================================================================
#     Helpers
# ==================================================================================================


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
            template_arguments=list(arguments),
        ),
    )
    return template.add_instance(instance)


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
