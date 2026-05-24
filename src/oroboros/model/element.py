from __future__ import annotations

"""Backbone objects shared by semantic declaration elements."""

from dataclasses import dataclass, field
import json
from typing import Iterable, TypeVar


ElementT = TypeVar("ElementT", bound="CppElement")


# ==================================================================================================
#     Element
# ==================================================================================================


class ModelValidationError(ValueError):
    """Report one or more structural problems in the semantic model tree."""


@dataclass(slots=True)
class CppElement:
    """Provide shared identity and ownership behavior for semantic elements."""

    name: str
    owner: CppElement | None = field(default=None, repr=False, compare=False)

    @property
    def scope_name(self) -> str | None:
        """Return the scope name contributed by this element."""

        return self.name

    @property
    def scope_parent(self) -> CppElement | None:
        """Return the semantic scope parent used for qualified names."""

        return self.owner

    @property
    def qualified_name(self) -> str:
        """Return the semantic qualified name derived from owning scopes."""

        names: list[str] = []
        current: CppElement | None = self

        while current is not None:
            if current.scope_name:
                names.append(current.scope_name)
            current = current.scope_parent

        return "::".join(reversed(names))

    @property
    def owning_path(self) -> tuple[CppElement, ...]:
        """Return the owning chain from the model root to this element."""

        elements: list[CppElement] = []
        current: CppElement | None = self

        while current is not None:
            elements.append(current)
            current = current.owner

        return tuple(reversed(elements))

    def _adopt_children(self, children: Iterable[CppElement]) -> None:
        """Attach a collection of child elements to this element."""

        for child in children:
            child.owner = self

    def _adopt_child(self, child: ElementT) -> ElementT:
        """Attach one child element to this element and return it."""

        child.owner = self
        return child

    def _append_child(self, children: list[ElementT], child: ElementT) -> ElementT:
        """Attach one child element and append it into one owned collection."""

        self._adopt_child(child)
        children.append(child)
        return child

    def find_all_by_qualified_name(
        self,
        qualified_name: str,
        *,
        types: type["CppElement"] | tuple[type["CppElement"], ...] | None = None,
    ) -> list["CppElement"]:
        """Find all elements in this subtree with one semantic qualified name."""

        from .lookup import find_all_by_qualified_name

        return find_all_by_qualified_name(self, qualified_name, types=types)

    def find_one_by_qualified_name(
        self,
        qualified_name: str,
        *,
        types: type["CppElement"] | tuple[type["CppElement"], ...] | None = None,
    ) -> "CppElement":
        """Find exactly one element in this subtree with one semantic qualified name."""

        from .lookup import find_one_by_qualified_name

        return find_one_by_qualified_name(self, qualified_name, types=types)

    def find_all_by_name(
        self,
        name: str,
        *,
        types: type["CppElement"] | tuple[type["CppElement"], ...] | None = None,
    ) -> list["CppElement"]:
        """Find all elements in this subtree with one unqualified semantic name."""

        from .lookup import find_all_by_name

        return find_all_by_name(self, name, types=types)

    def find_one_by_name(
        self,
        name: str,
        *,
        types: type["CppElement"] | tuple[type["CppElement"], ...] | None = None,
    ) -> "CppElement":
        """Find exactly one element in this subtree with one unqualified semantic name."""

        from .lookup import find_one_by_name

        return find_one_by_name(self, name, types=types)

    def find(
        self,
        query: str,
        *,
        types: type["CppElement"] | tuple[type["CppElement"], ...] | None = None,
    ) -> "CppElement":
        """Find exactly one descendant by qualified or unqualified semantic name."""

        from .lookup import find

        return find(self, query, types=types)

    def find_all(
        self,
        query: str,
        *,
        types: type["CppElement"] | tuple[type["CppElement"], ...] | None = None,
    ) -> list["CppElement"]:
        """Find all descendants by qualified or unqualified semantic name."""

        from .lookup import find_all

        return find_all(self, query, types=types)

    def __getitem__(self, name: str) -> "CppElement" | list["CppElement"]:
        """Resolve one direct child by name, returning overload groups as lists."""

        from .lookup import find_direct_child

        return find_direct_child(self, name)

    @property
    def element_names(self) -> list[str]:
        """Return the unique names of all direct child elements for discovery."""

        from .lookup import direct_child_names

        return direct_child_names(self)

    def validate_tree(self) -> None:
        """Validate owner links and direct-child containment across this subtree."""

        from .validation import validate_tree

        validate_tree(self)

    def validate_semantics(self) -> None:
        """Validate semantic cross-links and type usage across this subtree."""

        from .validation import validate_semantics

        validate_semantics(self)

    def _describe_element(self) -> str:
        """Return a short user-facing label for this semantic element."""

        label = _element_label(type(self).__name__)
        if not self.name:
            return label
        return f"{label}[{json.dumps(self.name)}]"

    def _describe_owner(self) -> str:
        """Return a short user-facing label for the current owner."""

        if self.owner is None:
            return "None"
        return self.owner._describe_element()


def _element_label(type_name: str) -> str:
    """Map one semantic element class name to a short user-facing label."""

    labels = {
        "CppAlias": "alias",
        "CppAliasTemplate": "alias_template",
        "CppAliasTemplateDeclaration": "alias_template_declaration",
        "CppAliasTemplateInstance": "alias_template_instance",
        "CppClass": "class",
        "CppClassTemplate": "class_template",
        "CppClassTemplateDeclaration": "class_template_declaration",
        "CppClassTemplateInstance": "class_template_instance",
        "CppConstructor": "constructor",
        "CppDestructor": "destructor",
        "CppEnum": "enum",
        "CppEnumerator": "enumerator",
        "CppVariable": "variable",
        "CppFunction": "function",
        "CppFunctionTemplate": "function_template",
        "CppFunctionTemplateDeclaration": "function_template_declaration",
        "CppFunctionTemplateInstance": "function_template_instance",
        "CppMethod": "method",
        "CppModule": "module",
        "CppNamespace": "namespace",
        "CppParameter": "parameter",
    }
    return labels.get(type_name, type_name)
