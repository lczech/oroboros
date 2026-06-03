from __future__ import annotations

"""Class-template model objects and helpers."""

from dataclasses import dataclass, field as dataclass_field
from typing import TYPE_CHECKING

from .class_ import (
    CppClassBindFacet,
    CppClassCppFacet,
    CppClassDefaults,
    CppClassMembers,
    CppClassPyFacet,
)
from .element import CppElement
from .member import CppConstructorBindFacet, CppMethodBindFacet
from .template_ import (
    CppTemplateObservationHint,
    CppTemplateArgument,
    CppTemplateBindFacet,
    CppTemplateParameter,
    _add_manual_template_instance,
    _synchronize_template_name,
)
from .variable import CppVariableBindFacet

if TYPE_CHECKING:
    from .enum import CppEnumBindFacet


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppClassTemplateDeclarationCppFacet(CppClassCppFacet):
    """Store parsed C++ details for one generic class template declaration."""

    # Parsed template parameters declared by this generic template.
    template_parameters: list[CppTemplateParameter] = dataclass_field(default_factory=list)
    # Raw concrete template spellings observed at use sites during parsing.
    template_observation_hints: list[CppTemplateObservationHint] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppClassTemplateInstanceCppFacet:
    """Store selected template arguments for one class template instance."""

    # Concrete template arguments selected for this binding target.
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
    # Defaults applied to instance variables inside selected instances.
    variable: CppVariableBindFacet = dataclass_field(default_factory=CppVariableBindFacet)
    # Defaults applied to static variables inside selected instances.
    static_variable: CppVariableBindFacet = dataclass_field(default_factory=CppVariableBindFacet)
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
class CppClassTemplateDeclaration(CppClassMembers):
    """Represent one generic class template declaration without binding state."""

    # Parsed C++ details for the generic class template declaration.
    cpp: CppClassTemplateDeclarationCppFacet = dataclass_field(
        default_factory=CppClassTemplateDeclarationCppFacet
    )


@dataclass(slots=True)
class CppClassTemplateInstance(CppElement):
    """Represent one selected class template instantiation as a binding target."""

    # Selected template arguments for this concrete class template instance.
    cpp: CppClassTemplateInstanceCppFacet = dataclass_field(
        default_factory=CppClassTemplateInstanceCppFacet
    )
    # Binding settings attached directly to this selected instance.
    bind: CppClassBindFacet = dataclass_field(default_factory=CppClassBindFacet)
    # Python-facing choices attached directly to this selected instance.
    py: CppClassPyFacet = dataclass_field(default_factory=CppClassPyFacet)
    # Descendant defaults for future instance-local emitted customization.
    defaults: CppClassDefaults = dataclass_field(default_factory=CppClassDefaults)


@dataclass(slots=True)
class CppClassTemplate(CppElement):
    """Group one generic class template declaration with its selected instances."""

    # Parsed generic class template declaration.
    declaration: CppClassTemplateDeclaration | None = None
    # Selected concrete instantiations to bind for this template family.
    instances: list[CppClassTemplateInstance] = dataclass_field(default_factory=list)
    # Binding policy attached to this template family wrapper itself.
    bind: CppTemplateBindFacet = dataclass_field(default_factory=CppTemplateBindFacet)
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
            declaration = CppClassTemplateDeclaration(name=self.name)
        _synchronize_template_name(self, declaration)
        self.declaration = declaration

        self._adopt_children([self.declaration])
        self._adopt_children(self.instances)

    def add_instance(self, instance: CppClassTemplateInstance) -> CppClassTemplateInstance:
        """Attach one selected class template instance to this family."""

        return self._append_child(self.instances, instance)

def add_class_template_instance(
    template: CppClassTemplate,
    arguments: list[CppTemplateArgument],
) -> CppClassTemplateInstance:
    """Create or return one concrete class template instance under a template family."""

    return _add_manual_template_instance(
        template,
        arguments,
        context=f"class template '{template.name}'",
        instance_type=CppClassTemplateInstance,
        instance_cpp_type=CppClassTemplateInstanceCppFacet,
    )
