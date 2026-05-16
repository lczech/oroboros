from __future__ import annotations

"""Backbone objects shared by semantic declaration nodes."""

from dataclasses import dataclass, field
from typing import Iterable


# ==================================================================================================
#     Element
# ==================================================================================================


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

    def adopt_children(self, children: Iterable[CppElement]) -> None:
        """Attach a collection of child nodes to this element."""

        for child in children:
            child.owner = self
