from __future__ import annotations

"""Class-template model objects and helpers."""

from copy import deepcopy
from dataclasses import dataclass, field as dataclass_field
from typing import TYPE_CHECKING

from .class_ import (
    CppClass,
    CppClassBindFacet,
    CppClassCppFacet,
    CppClassMembers,
    CppFieldBindFacet,
)
from .element import CppElement
from .member import CppConstructorBindFacet, CppMethodBindFacet
from .template_ import (
    CppObservedTemplateInstance,
    CppTemplateArgument,
    CppTemplateParameter,
    _copy_children,
    _synchronize_template_name,
    _template_argument_key,
    _validate_template_arguments,
)

if TYPE_CHECKING:
    from .enum import CppEnumBindFacet


# ==================================================================================================
#     Facets
# ==================================================================================================


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
    method: CppMethodBindFacet = dataclass_field(default_factory=CppMethodBindFacet)
    # Defaults applied to constructors inside selected instances.
    constructor: CppConstructorBindFacet = dataclass_field(default_factory=CppConstructorBindFacet)
    # Defaults applied to fields inside selected instances.
    field: CppFieldBindFacet = dataclass_field(default_factory=CppFieldBindFacet)
    # Defaults applied to enums inside selected instances.
    enum: "CppEnumBindFacet" = dataclass_field(default_factory=lambda: _make_enum_bind_facet())


def _make_enum_bind_facet() -> "CppEnumBindFacet":
    """Create one enum-bind facet without import cycles at module import time."""

    from .enum import CppEnumBindFacet

    return CppEnumBindFacet()


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppClassTemplateDecl(CppClassMembers):
    """Represent one generic class template declaration without binding state."""

    # Parsed C++ details for the generic class template declaration.
    cpp: CppClassTemplateDeclCppFacet = dataclass_field(default_factory=CppClassTemplateDeclCppFacet)


@dataclass(slots=True)
class CppClassTemplateInstance(CppClass):
    """Represent one selected class template instantiation to be bound."""

    # Parsed C++ details for this concrete class template instance.
    cpp: CppClassTemplateInstanceCppFacet = dataclass_field(default_factory=CppClassTemplateInstanceCppFacet)


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
            declaration = CppClassTemplateDecl(name=self.name)
        _synchronize_template_name(self, declaration)
        self.declaration = declaration

        self._adopt_children([self.declaration])
        self._adopt_children(self.instances)

    def add_instance(self, instance: CppClassTemplateInstance) -> CppClassTemplateInstance:
        """Attach one selected class template instance to this family."""

        return self._append_child(self.instances, instance)


# ==================================================================================================
#     Helpers
# ==================================================================================================


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
            location=deepcopy(declaration.cpp.location),
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
        aliases=_copy_children(declaration.aliases),
        enums=_copy_children(declaration.enums),
        class_templates=_copy_children(declaration.class_templates),
        function_templates=_copy_children(declaration.function_templates),
    )
    return template.add_instance(instance)


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
