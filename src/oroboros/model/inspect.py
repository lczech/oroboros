from __future__ import annotations

"""Human-readable inspection helpers for semantic model trees."""

from collections import Counter
import sys
from typing import Iterable, TextIO

from .element import CppElement
from .lookup import _iter_direct_child_elements


def iter_child_elements(element: CppElement) -> Iterable[CppElement]:
    """Yield the direct semantic children of one model element."""

    for _, child in _iter_direct_child_elements(element, element._describe_element()):
        yield child


def iter_subtree_elements(
    root: CppElement,
    *,
    include_root: bool = True,
) -> Iterable[CppElement]:
    """Yield one semantic subtree in preorder."""

    if include_root:
        yield root

    for child in iter_child_elements(root):
        yield child
        yield from iter_subtree_elements(child, include_root=False)


def format_element(element: CppElement) -> str:
    """Format one semantic element as a short human-readable label."""

    type_name = type(element).__name__
    name = element.name or "<anonymous>"

    if type_name == "CppNamespace":
        return f"namespace {name}"
    if type_name == "CppAlias":
        return f"alias {name}"
    if type_name == "CppAliasTemplate":
        return f"alias template {name}"
    if type_name == "CppAliasTemplateDeclaration":
        return f"alias template declaration {name}"
    if type_name == "CppAliasTemplateInstance":
        return f"alias template instance {name}"
    if type_name == "CppClass":
        kind = getattr(getattr(element, "cpp", None), "kind", "class")
        return f"{kind} {name}"
    if type_name == "CppEnum":
        return f"enum {name}"
    if type_name == "CppEnumerator":
        return f"enumerator {name}"
    if type_name == "CppFunction":
        return f"function {name}"
    if type_name == "CppFunctionTemplate":
        return f"function template {name}"
    if type_name == "CppMethod":
        return f"method {name}"
    if type_name == "CppMethodTemplate":
        return f"method template {name}"
    if type_name == "CppConstructor":
        return f"constructor {name}"
    if type_name == "CppDestructor":
        return f"destructor {name}"
    if type_name == "CppVariable":
        kind = getattr(getattr(element, "cpp", None), "kind", "variable")
        if kind == "member_variable":
            return f"member variable {name}"
        if kind == "static_member_variable":
            return f"static member variable {name}"
        return f"variable {name}"
    if type_name == "CppParameter":
        return f"parameter {name}"
    if type_name == "CppModule":
        return "module"

    return f"{type_name} {name}"


def format_tree(
    root: CppElement,
    *,
    include_root: bool = False,
    indent: int = 0,
) -> str:
    """Render one semantic subtree as an indented tree."""

    lines: list[str] = []

    if include_root:
        _append_tree_lines(lines, root, indent)
    else:
        for child in iter_child_elements(root):
            _append_tree_lines(lines, child, indent)

    return "\n".join(lines)


def summarize_tree(root: CppElement) -> str:
    """Return a compact summary of one semantic subtree."""

    elements = list(iter_subtree_elements(root))
    counts = Counter(type(element).__name__ for element in elements)
    total_elements = sum(counts.values())
    variable_kinds = Counter(
        getattr(element.cpp, "kind", "variable")
        for element in elements
        if type(element).__name__ == "CppVariable"
    )

    lines = [
        "Model summary:",
        f"  total elements: {total_elements}",
    ]

    summary_order = (
        ("CppNamespace", "namespaces"),
        ("CppClass", "classes"),
        ("CppClassTemplate", "class templates"),
        ("CppMethod", "methods"),
        ("CppMethodTemplate", "method templates"),
        ("CppConstructor", "constructors"),
        ("CppDestructor", "destructors"),
        ("CppVariable", "variables"),
        ("CppFunction", "functions"),
        ("CppFunctionTemplate", "function templates"),
        ("CppParameter", "parameters"),
        ("CppEnum", "enums"),
        ("CppEnumerator", "enumerators"),
        ("CppAlias", "aliases"),
        ("CppAliasTemplate", "alias templates"),
    )

    for type_name, label in summary_order:
        lines.append(f"  {label}: {counts.get(type_name, 0)}")

    if counts.get("CppVariable", 0):
        lines.append(f"  scope variables: {variable_kinds.get('variable', 0)}")
        lines.append(f"  member variables: {variable_kinds.get('member_variable', 0)}")
        lines.append(
            f"  static member variables: {variable_kinds.get('static_member_variable', 0)}"
        )

    return "\n".join(lines)


def print_tree(
    root: CppElement,
    *,
    stream: TextIO | None = None,
    include_root: bool = False,
    indent: int = 0,
) -> None:
    """Print one formatted semantic subtree."""

    output_stream = stream if stream is not None else sys.stdout
    text = format_tree(root, include_root=include_root, indent=indent)
    print(text, file=output_stream)


def print_summary(
    root: CppElement,
    *,
    stream: TextIO | None = None,
) -> None:
    """Print one compact semantic-tree summary."""

    output_stream = stream if stream is not None else sys.stdout
    print(summarize_tree(root), file=output_stream)


def _append_tree_lines(lines: list[str], element: CppElement, indent: int) -> None:
    """Append one subtree to the accumulating line list."""

    prefix = "  " * indent
    lines.append(f"{prefix}- {format_element(element)}")
    for child in iter_child_elements(element):
        _append_tree_lines(lines, child, indent + 1)
