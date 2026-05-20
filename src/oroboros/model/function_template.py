from __future__ import annotations

"""Function-template model objects and helpers."""

from copy import deepcopy
from dataclasses import dataclass, field as dataclass_field

from .element import CppElement
from .function import CppFunction, CppFunctionBindFacet, CppFunctionCppFacet, CppParameter
from .template_ import (
    CppObservedTemplateInstance,
    CppTemplateArgument,
    CppTemplateParameter,
    _copy_children,
    _synchronize_template_name,
    _template_argument_key,
    _validate_template_arguments,
)


# ==================================================================================================
#     Facets
# ==================================================================================================


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


@dataclass(slots=True)
class CppFunctionTemplateDecl(CppElement):
    """Represent one generic function template declaration without binding state."""

    # Parsed C++ details for the generic function template declaration.
    cpp: CppFunctionTemplateDeclCppFacet = dataclass_field(default_factory=CppFunctionTemplateDeclCppFacet)
    # Parameters declared directly on this generic function template declaration.
    parameters: list[CppParameter] = dataclass_field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self._adopt_children(self.parameters)

    def add_parameter(self, parameter: CppParameter) -> CppParameter:
        """Attach one parameter to this generic function template declaration."""

        return self._append_child(self.parameters, parameter)


@dataclass(slots=True)
class CppFunctionTemplateInstance(CppFunction):
    """Represent one selected function template instantiation to be bound."""

    # Parsed C++ details for this concrete function template instance.
    cpp: CppFunctionTemplateInstanceCppFacet = dataclass_field(default_factory=CppFunctionTemplateInstanceCppFacet)


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
            declaration = CppFunctionTemplateDecl(name=self.name)
        _synchronize_template_name(self, declaration)
        self.declaration = declaration

        self._adopt_children([self.declaration])
        self._adopt_children(self.instances)

    def add_instance(self, instance: CppFunctionTemplateInstance) -> CppFunctionTemplateInstance:
        """Attach one selected function template instance to this family."""

        return self._append_child(self.instances, instance)


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
            original_name=declaration.cpp.original_name,
            operator=deepcopy(declaration.cpp.operator),
            return_type=deepcopy(declaration.cpp.return_type),
            location=deepcopy(declaration.cpp.location),
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
