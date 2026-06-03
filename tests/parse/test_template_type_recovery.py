from __future__ import annotations

import unittest
from types import SimpleNamespace

from clang.cindex import TypeKind

from oroboros.model import (
    BuiltinCppType,
    CppNonTypeTemplateArgument,
    CppTypeTemplateArgument,
    NamedCppType,
    PointerCppType,
    TemplateInstanceCppType,
)
from oroboros.parse.template_type_recovery import (
    build_cpp_type_from_spelling,
    build_template_argument_from_spelling,
)
from oroboros.parse.types import build_cpp_type


class TemplateTypeRecoveryTest(unittest.TestCase):
    def test_build_cpp_type_from_spelling_parses_pointer_constness_correctly_in_template_argument_spellings(self) -> None:
        cpp_type = build_cpp_type_from_spelling("Pair<Widget const* const, const Widget* const>")

        self.assertIsInstance(cpp_type, TemplateInstanceCppType)
        self.assertEqual(cpp_type.template_name, "Pair")
        self.assertEqual(len(cpp_type.arguments), 2)

        self.assertIsInstance(cpp_type.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(cpp_type.arguments[1], CppTypeTemplateArgument)
        first_argument = cpp_type.arguments[0].type
        second_argument = cpp_type.arguments[1].type

        self.assertIsInstance(first_argument, PointerCppType)
        self.assertTrue(first_argument.is_const)
        self.assertIsInstance(first_argument.pointee, NamedCppType)
        self.assertEqual(first_argument.pointee.name, "Widget")
        self.assertTrue(first_argument.pointee.is_const)

        self.assertIsInstance(second_argument, PointerCppType)
        self.assertTrue(second_argument.is_const)
        self.assertIsInstance(second_argument.pointee, NamedCppType)
        self.assertEqual(second_argument.pointee.name, "Widget")
        self.assertTrue(second_argument.pointee.is_const)

    def test_build_cpp_type_from_spelling_recovers_nested_template_argument_types(self) -> None:
        cpp_type = build_cpp_type_from_spelling("Box<Pair<int, Widget>>")

        self.assertIsInstance(cpp_type, TemplateInstanceCppType)
        self.assertEqual(cpp_type.template_name, "Box")
        self.assertEqual(len(cpp_type.arguments), 1)
        self.assertIsInstance(cpp_type.arguments[0], CppTypeTemplateArgument)
        nested_type = cpp_type.arguments[0].type
        self.assertIsInstance(nested_type, TemplateInstanceCppType)
        self.assertEqual(nested_type.template_name, "Pair")
        self.assertEqual(len(nested_type.arguments), 2)
        self.assertIsInstance(nested_type.arguments[0].type, BuiltinCppType)
        self.assertIsInstance(nested_type.arguments[1].type, NamedCppType)
        self.assertEqual(nested_type.arguments[1].type.name, "Widget")

    def test_build_cpp_type_uses_recovery_module_for_non_type_template_arguments(self) -> None:
        clang_type = _fake_type(
            "ELABORATED",
            "std::array<int, 4>",
            template_argument_types=[
                _fake_type("INT", "int"),
                _fake_type("INT", "int"),
            ],
        )

        cpp_type = build_cpp_type(clang_type)

        self.assertIsInstance(cpp_type, TemplateInstanceCppType)
        self.assertEqual(cpp_type.template_name, "std::array")
        self.assertEqual(len(cpp_type.arguments), 2)
        self.assertIsInstance(cpp_type.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(cpp_type.arguments[0].type, BuiltinCppType)
        self.assertEqual(cpp_type.arguments[0].type.kind, "int")
        self.assertIsInstance(cpp_type.arguments[1], CppNonTypeTemplateArgument)
        self.assertEqual(cpp_type.arguments[1].value, "4")
        self.assertIsInstance(cpp_type.arguments[1].type, BuiltinCppType)
        self.assertEqual(cpp_type.arguments[1].type.kind, "int")

    def test_build_cpp_type_from_spelling_bails_out_for_expression_like_template_arguments(self) -> None:
        cpp_type = build_cpp_type_from_spelling("Mask<make_flag(1, 2)>")

        self.assertIsInstance(cpp_type, NamedCppType)
        self.assertEqual(cpp_type.name, "Mask<make_flag(1, 2)>")

    def test_build_cpp_type_preserves_canonical_structure_when_source_recovery_bails_out(self) -> None:
        canonical = _fake_type(
            "ELABORATED",
            "std::array<int, 4>",
            template_argument_types=[
                _fake_type("INT", "int"),
                _fake_type("INT", "int"),
            ],
        )
        clang_type = _fake_type(
            "ELABORATED",
            "Mask<make_flag(1, 2)>",
            canonical=canonical,
        )

        cpp_type = build_cpp_type(clang_type)

        self.assertIsInstance(cpp_type, NamedCppType)
        self.assertEqual(cpp_type.name, "Mask<make_flag(1, 2)>")
        self.assertIsInstance(cpp_type.canonical, TemplateInstanceCppType)
        self.assertEqual(cpp_type.canonical.template_name, "std::array")

    def test_build_cpp_type_from_spelling_bails_out_for_braced_template_arguments(self) -> None:
        cpp_type = build_cpp_type_from_spelling("Mask<Point{1, 2}>")

        self.assertIsInstance(cpp_type, NamedCppType)
        self.assertEqual(cpp_type.name, "Mask<Point{1, 2}>")

    def test_build_cpp_type_from_spelling_bails_out_for_quoted_template_arguments(self) -> None:
        cpp_type = build_cpp_type_from_spelling('Mask<"a,b">')

        self.assertIsInstance(cpp_type, NamedCppType)
        self.assertEqual(cpp_type.name, 'Mask<"a,b">')

    def test_build_template_argument_from_spelling_builds_type_argument_for_nested_template(self) -> None:
        argument = build_template_argument_from_spelling("Pair<int, Widget>")

        self.assertIsInstance(argument, CppTypeTemplateArgument)
        self.assertIsInstance(argument.type, TemplateInstanceCppType)
        self.assertEqual(argument.type.template_name, "Pair")


def _fake_type(
    kind_name: str,
    spelling: str,
    *,
    is_const: bool = False,
    pointee: SimpleNamespace | None = None,
    element_type: SimpleNamespace | None = None,
    array_size: int | None = None,
    result_type: SimpleNamespace | None = None,
    argument_types: list[SimpleNamespace] | None = None,
    template_argument_types: list[SimpleNamespace] | None = None,
    declaration_cursor: SimpleNamespace | None = None,
    canonical: SimpleNamespace | None = None,
    is_variadic: bool = False,
) -> SimpleNamespace:
    fake_type = SimpleNamespace(
        kind=getattr(TypeKind, kind_name),
        spelling=spelling,
        is_const_qualified=lambda: is_const,
        get_pointee=lambda: pointee,
        get_array_element_type=lambda: element_type,
        get_array_size=lambda: -1 if array_size is None else array_size,
        get_result=lambda: result_type,
        argument_types=lambda: list(argument_types or []),
        get_num_template_arguments=lambda: len(template_argument_types or []),
        get_template_argument_type=lambda index: list(template_argument_types or [])[index],
        is_function_variadic=lambda: is_variadic,
        get_declaration=lambda: declaration_cursor,
    )
    fake_type.get_canonical = lambda: canonical if canonical is not None else fake_type
    return fake_type
