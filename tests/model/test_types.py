from __future__ import annotations

from pathlib import Path
import unittest

from oroboros.model import *
from tests.support.model_builders import make_class, make_class_template_declaration, make_module, make_namespace


class ModelTypeTest(unittest.TestCase):
    def test_build_py_doc_from_parsed_doc_copies_nested_data(self) -> None:
        parsed_doc = CppParsedDoc(
            brief="Create a widget.",
            description="Build a widget from one integer seed.\n\n```cpp\nWidget widget;\n```",
            parameters={"seed": "Seed value used by the constructor."},
            template_parameters={"Factory": "Factory type used by the builder."},
            returns="A new widget instance.",
            return_values={"true": "A widget was created successfully."},
            deprecated="Prefer create_widget_v2().",
            notes=["This is only an example."],
            warnings=["Do not pass negative values."],
            see_also=["demo::Widget"],
        )

        py_doc = build_py_doc_from_parsed_doc(parsed_doc)

        self.assertIsNotNone(py_doc)
        self.assertEqual(py_doc.summary, "Create a widget.")
        self.assertEqual(
            py_doc.description,
            "Build a widget from one integer seed.\n\n```cpp\nWidget widget;\n```",
        )
        self.assertEqual(py_doc.parameters["seed"], "Seed value used by the constructor.")
        self.assertEqual(
            py_doc.template_parameters["Factory"],
            "Factory type used by the builder.",
        )
        self.assertEqual(
            py_doc.return_values["true"],
            "A widget was created successfully.",
        )
        self.assertEqual(py_doc.deprecated, "Prefer create_widget_v2().")

        parsed_doc.parameters["seed"] = "Changed"
        parsed_doc.template_parameters["Factory"] = "Changed"
        parsed_doc.return_values["true"] = "Changed"
        parsed_doc.notes.append("Changed")
        self.assertEqual(py_doc.parameters["seed"], "Seed value used by the constructor.")
        self.assertEqual(
            py_doc.template_parameters["Factory"],
            "Factory type used by the builder.",
        )
        self.assertEqual(
            py_doc.return_values["true"],
            "A widget was created successfully.",
        )
        self.assertEqual(py_doc.notes, ["This is only an example."])

    def test_named_cpp_type_renders_const_qualified_names(self) -> None:
        cls = make_class(name="Widget")
        cpp_type = NamedCppType(name="std::string", is_const=True, declaration=cls)

        self.assertEqual(cpp_type.render(), "const std::string")
        self.assertIs(cpp_type.declaration, cls)

    def test_named_cpp_type_preserves_original_name_when_canonical_is_present(self) -> None:
        cpp_type = NamedCppType(
            name="uint64_t",
            canonical=BuiltinCppType(kind="unsigned_long"),
        )

        self.assertEqual(cpp_type.render(), "uint64_t")
        self.assertEqual(cpp_type.canonical.render(), "unsigned long")

    def test_builtin_cpp_type_renders_language_builtin_names(self) -> None:
        cpp_type = BuiltinCppType(kind="int", is_const=True)

        self.assertEqual(cpp_type.render(), "const int")

    def test_builtin_cpp_type_renders_nullptr_type(self) -> None:
        cpp_type = BuiltinCppType(kind="nullptr_t")

        self.assertEqual(cpp_type.render(), "std::nullptr_t")

    def test_array_cpp_type_renders_fixed_extent_arrays(self) -> None:
        cpp_type = ArrayCppType(
            element_type=BuiltinCppType(kind="int"),
            extent="4",
        )

        self.assertEqual(cpp_type.render(), "int[4]")

    def test_array_cpp_type_renders_nested_arrays_recursively(self) -> None:
        cpp_type = ArrayCppType(
            element_type=ArrayCppType(
                element_type=NamedCppType(name="Widget"),
                extent="4",
            ),
            extent="3",
        )

        self.assertEqual(cpp_type.render(), "Widget[4][3]")

    def test_function_cpp_type_renders_plain_function_types(self) -> None:
        cpp_type = FunctionCppType(
            return_type=BuiltinCppType(kind="void"),
            parameters=[
                BuiltinCppType(kind="int"),
                NamedCppType(name="Widget"),
            ],
        )

        self.assertEqual(cpp_type.render(), "void (int, Widget)")

    def test_pointer_cpp_type_can_wrap_function_cpp_type(self) -> None:
        cpp_type = PointerCppType(
            pointee=FunctionCppType(
                return_type=BuiltinCppType(kind="void"),
                parameters=[BuiltinCppType(kind="int")],
            )
        )

        self.assertEqual(cpp_type.render(), "void (*)(int)")

    def test_alias_linked_named_cpp_types_still_compare_equivalent_to_their_target(self) -> None:
        widget = make_class(name="Widget")
        alias = CppAlias(name="WidgetAlias")
        alias.cpp.target = NamedCppType(name="Widget", declaration=widget)
        alias_type = NamedCppType(
            name="WidgetAlias",
            declaration=alias,
            canonical=NamedCppType(name="Widget", declaration=widget),
        )
        widget_type = NamedCppType(name="Widget", declaration=widget)

        self.assertTrue(cpp_types_equivalent(alias_type, widget_type))

    def test_named_and_builtin_cpp_types_cover_different_use_cases(self) -> None:
        builtin_type = BuiltinCppType(kind="int")
        named_type = NamedCppType(name="demo::Widget")

        self.assertEqual(builtin_type.render(), "int")
        self.assertEqual(named_type.render(), "demo::Widget")
