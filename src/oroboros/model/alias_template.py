from __future__ import annotations

"""Alias-template model objects and helpers."""

from dataclasses import dataclass, field as dataclass_field

from .alias import CppAliasBindFacet, CppAliasCppFacet, CppAliasPyFacet
from .element import CppElement
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
class CppAliasTemplateDeclarationCppFacet(CppAliasCppFacet):
    """Store parsed C++ details for one generic alias-template declaration."""

    template_parameters: list[CppTemplateParameter] = dataclass_field(default_factory=list)
    observed_instances: list[CppObservedTemplateInstance] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppAliasTemplateInstanceCppFacet:
    """Store selected template arguments for one alias-template instance."""

    template_arguments: list[CppTemplateArgument] = dataclass_field(default_factory=list)


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppAliasTemplateDeclaration(CppElement):
    """Represent one generic alias-template declaration without binding state."""

    cpp: CppAliasTemplateDeclarationCppFacet = dataclass_field(
        default_factory=CppAliasTemplateDeclarationCppFacet
    )


@dataclass(slots=True)
class CppAliasTemplateInstance(CppElement):
    """Represent one selected alias-template instantiation as a binding target."""

    cpp: CppAliasTemplateInstanceCppFacet = dataclass_field(
        default_factory=CppAliasTemplateInstanceCppFacet
    )
    bind: CppAliasBindFacet = dataclass_field(
        default_factory=CppAliasBindFacet
    )
    py: CppAliasPyFacet = dataclass_field(
        default_factory=CppAliasPyFacet
    )


@dataclass(slots=True)
class CppAliasTemplate(CppElement):
    """Group one generic alias-template declaration with its selected instances."""

    declaration: CppAliasTemplateDeclaration | None = None
    instances: list[CppAliasTemplateInstance] = dataclass_field(default_factory=list)
    bind: CppTemplateBindFacet = dataclass_field(default_factory=CppTemplateBindFacet)
    defaults: CppAliasBindFacet = dataclass_field(default_factory=CppAliasBindFacet)

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
            declaration = CppAliasTemplateDeclaration(name=self.name)
        _synchronize_template_name(self, declaration)
        self.declaration = declaration

        self._adopt_children([self.declaration])
        self._adopt_children(self.instances)

    def add_instance(self, instance: CppAliasTemplateInstance) -> CppAliasTemplateInstance:
        """Attach one selected alias-template instance to this family."""

        return self._append_child(self.instances, instance)

    def add_observed_instances(self) -> list[CppAliasTemplateInstance]:
        """Materialize all parser-observed instances attached to this template family."""

        return [
            add_alias_template_instance(self, observed_instance.arguments)
            for observed_instance in self.declaration.cpp.observed_instances
        ]


# ==================================================================================================
#     Helpers
# ==================================================================================================


def add_alias_template_instance(
    template: CppAliasTemplate,
    arguments: list[CppTemplateArgument],
) -> CppAliasTemplateInstance:
    """Create or return one concrete alias-template instance under a template family."""

    existing_instance = _find_existing_alias_template_instance(template, arguments)
    if existing_instance is not None:
        return existing_instance

    declaration = template.declaration
    if declaration is None:
        raise ValueError("Alias template family does not contain a generic declaration.")

    _validate_template_arguments(
        declaration.cpp.template_parameters,
        arguments,
        context=f"alias template '{template.name}'",
    )

    instance = CppAliasTemplateInstance(
        name=template.name,
        cpp=CppAliasTemplateInstanceCppFacet(
            template_arguments=list(arguments),
        ),
    )
    return template.add_instance(instance)


def _find_existing_alias_template_instance(
    template: CppAliasTemplate,
    arguments: list[CppTemplateArgument],
) -> CppAliasTemplateInstance | None:
    """Return an existing alias instance with the same template arguments, if any."""

    argument_key = _template_argument_key(arguments)
    for instance in template.instances:
        if _template_argument_key(instance.cpp.template_arguments) == argument_key:
            return instance
    return None
