from __future__ import annotations

"""Backbone objects shared by semantic declaration nodes."""

from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Iterable, TypeVar


ElementT = TypeVar("ElementT", bound="CppElement")


# ==================================================================================================
#     Element
# ==================================================================================================


class ModelValidationError(ValueError):
    """Report one or more structural problems in the semantic model tree."""


@dataclass(slots=True)
class CppElement:
    """Provide shared identity and ownership behavior for semantic nodes."""

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
        """Attach a collection of child nodes to this element."""

        for child in children:
            child.owner = self

    def _adopt_child(self, child: ElementT) -> ElementT:
        """Attach one child node to this element and return it."""

        child.owner = self
        return child

    def _append_child(self, children: list[ElementT], child: ElementT) -> ElementT:
        """Attach one child node and append it into one owned collection."""

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

    def validate_tree(self) -> None:
        """Validate owner links and direct-child containment across this subtree."""

        root_path = self._describe_node()
        errors: list[str] = []
        visited: dict[int, str] = {id(self): root_path}

        self._validate_tree(root_path, visited, errors)

        if errors:
            raise ModelValidationError(
                "Invalid semantic model tree:\n- " + "\n- ".join(errors)
            )

    def _validate_tree(
        self,
        path: str,
        visited: dict[int, str],
        errors: list[str],
    ) -> None:
        """Collect validation errors for this subtree into one shared list."""

        self._validate_owner_chain(path, errors)

        for child_path, child in self._iter_direct_children(path, errors):
            if child.owner is not self:
                errors.append(
                    f"{child_path} has owner {child._describe_owner()}, "
                    f"expected {self._describe_node()}."
                )

            child_id = id(child)
            if child_id in visited:
                errors.append(
                    f"{child_path} references the same node already seen at "
                    f"{visited[child_id]}."
                )
                continue

            visited[child_id] = child_path
            child._validate_tree(child_path, visited, errors)

    def _iter_direct_children(
        self,
        path: str,
        errors: list[str],
    ) -> list[tuple[str, "CppElement"]]:
        """Collect direct child references declared on this model node."""

        children: list[tuple[str, CppElement]] = []

        for dataclass_field in dataclass_fields(self):
            field_name = dataclass_field.name
            if field_name == "owner":
                continue

            value = getattr(self, field_name)
            if isinstance(value, CppElement):
                children.append((f"{path}.{field_name}", value))
                continue

            if isinstance(value, list):
                for index, item in enumerate(value):
                    item_path = f"{path}.{field_name}[{index}]"
                    if not isinstance(item, CppElement):
                        errors.append(
                            f"{item_path} contains {type(item).__name__}, expected a CppElement."
                        )
                        continue
                    children.append((item_path, item))

        return children

    def _validate_owner_chain(self, path: str, errors: list[str]) -> None:
        """Detect cyclic owner links starting from this node."""

        seen_owner_ids = {id(self)}
        current = self.owner

        while current is not None:
            current_id = id(current)
            if current_id in seen_owner_ids:
                errors.append(
                    f"{path} participates in an owner cycle involving "
                    f"{current._describe_node()}."
                )
                return
            seen_owner_ids.add(current_id)
            current = current.owner

    def _describe_node(self) -> str:
        """Return a short user-facing label for this semantic node."""

        return f"{type(self).__name__}({self.name!r})"

    def _describe_owner(self) -> str:
        """Return a short user-facing label for the current owner."""

        if self.owner is None:
            return "None"
        return self.owner._describe_node()
