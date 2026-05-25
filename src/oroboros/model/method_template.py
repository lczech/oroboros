from __future__ import annotations

"""Method-template model objects and helpers."""

from dataclasses import dataclass, field as dataclass_field

from .element import CppElement
from .function import CppParameter
from .member import CppMethodBindFacet, CppMethodCppFacet, CppMethodPyFacet
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
class CppMethodTemplateDeclarationCppFacet(CppMethodCppFacet):
    """Store parsed C++ details for one generic method template declaration."""

    template_parameters: list[CppTemplateParameter] = dataclass_field(default_factory=list)
    observed_instances: list[CppObservedTemplateInstance] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppMethodTemplateInstanceCppFacet:
    """Store selected template arguments for one method template instance."""

    template_arguments: list[CppTemplateArgument] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppMethodTemplateDefaults:
    """Store defaults applied to selected method template instances."""

    # Defaults applied to each selected method template instance itself.
    instance: CppMethodBindFacet = dataclass_field(default_factory=CppMethodBindFacet)


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppMethodTemplateDeclaration(CppElement):
    """Represent one generic method template declaration without binding state."""

    # Parsed C++ details for the generic method template declaration.
    cpp: CppMethodTemplateDeclarationCppFacet = dataclass_field(
        default_factory=CppMethodTemplateDeclarationCppFacet
    )
    # Parameters declared directly on this generic method template declaration.
    parameters: list[CppParameter] = dataclass_field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self._adopt_children(self.parameters)

    def add_parameter(self, parameter: CppParameter) -> CppParameter:
        """Attach one parameter to this generic method template declaration."""

        return self._append_child(self.parameters, parameter)


@dataclass(slots=True)
class CppMethodTemplateInstance(CppElement):
    """Represent one selected method template instantiation as a binding target."""

    # Selected template arguments for this concrete method template instance.
    cpp: CppMethodTemplateInstanceCppFacet = dataclass_field(
        default_factory=CppMethodTemplateInstanceCppFacet
    )
    # Binding settings attached directly to this selected instance.
    bind: CppMethodBindFacet = dataclass_field(
        default_factory=CppMethodBindFacet
    )
    # Python-facing choices attached directly to this selected instance.
    py: CppMethodPyFacet = dataclass_field(
        default_factory=CppMethodPyFacet
    )


@dataclass(slots=True)
class CppMethodTemplate(CppElement):
    """Group one generic method template declaration with its selected instances."""

    # Parsed generic method template declaration, including observed instances.
    declaration: CppMethodTemplateDeclaration | None = None
    # Selected concrete instantiations to bind for this template family.
    instances: list[CppMethodTemplateInstance] = dataclass_field(default_factory=list)
    # Binding policy attached to this template family wrapper itself.
    bind: CppTemplateBindFacet = dataclass_field(default_factory=CppTemplateBindFacet)
    # Defaults applied to selected instances of this template family.
    defaults: CppMethodTemplateDefaults = dataclass_field(default_factory=CppMethodTemplateDefaults)

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
            declaration = CppMethodTemplateDeclaration(name=self.name)
        _synchronize_template_name(self, declaration)
        self.declaration = declaration

        self._adopt_children([self.declaration])
        self._adopt_children(self.instances)

    def add_instance(self, instance: CppMethodTemplateInstance) -> CppMethodTemplateInstance:
        """Attach one selected method template instance to this family."""

        return self._append_child(self.instances, instance)

    def add_observed_instances(self) -> list[CppMethodTemplateInstance]:
        """Materialize all parser-observed instances attached to this template family."""

        return [
            add_method_template_instance(self, observed_instance.arguments)
            for observed_instance in self.declaration.cpp.observed_instances
        ]


# ==================================================================================================
#     Helpers
# ==================================================================================================


def add_method_template_instance(
    template: CppMethodTemplate,
    arguments: list[CppTemplateArgument],
) -> CppMethodTemplateInstance:
    """Create or return one concrete method template instance under a template family."""

    existing_instance = _find_existing_method_template_instance(template, arguments)
    if existing_instance is not None:
        return existing_instance

    declaration = template.declaration
    if declaration is None:
        raise ValueError("Method template family does not contain a generic declaration.")

    _validate_template_arguments(
        declaration.cpp.template_parameters,
        arguments,
        context=f"method template '{template.name}'",
    )

    instance = CppMethodTemplateInstance(
        name=template.name,
        cpp=CppMethodTemplateInstanceCppFacet(
            template_arguments=list(arguments),
        ),
    )
    return template.add_instance(instance)


def _find_existing_method_template_instance(
    template: CppMethodTemplate,
    arguments: list[CppTemplateArgument],
) -> CppMethodTemplateInstance | None:
    """Return an existing method-template instance with the same arguments, if any."""

    argument_key = _template_argument_key(arguments)
    for instance in template.instances:
        if _template_argument_key(instance.cpp.template_arguments) == argument_key:
            return instance
    return None
