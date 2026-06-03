from __future__ import annotations

"""Function-template model objects and helpers."""

from dataclasses import dataclass, field as dataclass_field

from .element import CppElement
from .function import CppFunctionBindFacet, CppFunctionCppFacet, CppFunctionPyFacet, CppParameter
from .template_ import (
    CppTemplateObservationHint,
    CppTemplateArgument,
    CppTemplateBindFacet,
    CppTemplateParameter,
    _add_manual_template_instance,
    _synchronize_template_name,
)


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppFunctionTemplateDeclarationCppFacet(CppFunctionCppFacet):
    """Store parsed C++ details for one generic function template declaration."""

    # Parsed template parameters declared by this generic template.
    template_parameters: list[CppTemplateParameter] = dataclass_field(default_factory=list)
    # Raw concrete template spellings observed at use sites during parsing.
    template_observation_hints: list[CppTemplateObservationHint] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppFunctionTemplateInstanceCppFacet:
    """Store selected template arguments for one function template instance."""

    # Concrete template arguments selected for this binding target.
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
    cpp: CppFunctionTemplateInstanceCppFacet = dataclass_field(
        default_factory=CppFunctionTemplateInstanceCppFacet
    )
    # Binding settings attached directly to this selected instance.
    bind: CppFunctionBindFacet = dataclass_field(
        default_factory=CppFunctionBindFacet
    )
    # Python-facing choices attached directly to this selected instance.
    py: CppFunctionPyFacet = dataclass_field(
        default_factory=CppFunctionPyFacet
    )


@dataclass(slots=True)
class CppFunctionTemplate(CppElement):
    """Group one generic function template declaration with its selected instances."""

    # Parsed generic function template declaration.
    declaration: CppFunctionTemplateDeclaration | None = None
    # Selected concrete instantiations to bind for this template family.
    instances: list[CppFunctionTemplateInstance] = dataclass_field(
        default_factory=list
    )
    # Binding policy attached to this template family wrapper itself.
    bind: CppTemplateBindFacet = dataclass_field(
        default_factory=CppTemplateBindFacet
    )
    # Defaults applied to selected instances of this template family.
    defaults: CppFunctionTemplateDefaults = dataclass_field(
        default_factory=CppFunctionTemplateDefaults
    )

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

def add_function_template_instance(
    template: CppFunctionTemplate,
    arguments: list[CppTemplateArgument],
) -> CppFunctionTemplateInstance:
    """Create or return one concrete function template instance under a template family."""

    return _add_manual_template_instance(
        template,
        arguments,
        context=f"function template '{template.name}'",
        instance_type=CppFunctionTemplateInstance,
        instance_cpp_type=CppFunctionTemplateInstanceCppFacet,
    )
