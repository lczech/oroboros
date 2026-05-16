from __future__ import annotations

import unittest

from oroboros.model import (
    CppClass,
    CppClassBase,
    CppClassBindFacet,
    CppClassDefaults,
    CppConstructor,
    CppDoc,
    CppEnum,
    CppEnumBindFacet,
    CppEnumerator,
    CppField,
    CppFieldBindFacet,
    CppFunction,
    CppFunctionBindFacet,
    CppMethod,
    CppModule,
    CppModuleDefaults,
    CppNamespace,
    CppNamespaceBindFacet,
    CppNamespaceDefaults,
    CppOperator,
    CppOperatorBind,
    CppParameter,
    NamedCppType,
    build_py_doc_from_cpp_doc,
)


class ModelScaffoldTest(unittest.TestCase):
    def test_model_nodes_adopt_children_and_compute_qualified_names(self) -> None:
        parameter = CppParameter(name="value")
        constructor = CppConstructor(name="Widget", parameters=[CppParameter(name="seed")])
        method = CppMethod(name="size", parameters=[parameter])
        enum_ = CppEnum(name="Kind", enumerators=[CppEnumerator(name="primary")])
        cls = CppClass(
            name="Widget",
            constructors=[constructor],
            methods=[method],
            enums=[enum_],
        )
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        self.assertIs(namespace.owner, module)
        self.assertIs(cls.owner, namespace)
        self.assertIs(constructor.owner, cls)
        self.assertIs(method.owner, cls)
        self.assertIs(parameter.owner, method)
        self.assertIs(enum_.owner, cls)
        self.assertIs(enum_.enumerators[0].owner, enum_)
        self.assertEqual(namespace.qualified_name, "demo")
        self.assertEqual(cls.qualified_name, "demo::Widget")
        self.assertEqual(method.qualified_name, "demo::Widget::size")
        self.assertEqual(parameter.qualified_name, "demo::Widget::size::value")

    def test_parse_stage_starts_with_default_bind_and_default_py_facets(self) -> None:
        parameter = CppParameter(name="value")
        constructor = CppConstructor(name="Widget")
        method = CppMethod(name="size", parameters=[parameter])
        function = CppFunction(name="make_widget", parameters=[CppParameter(name="seed")])
        enum_ = CppEnum(name="Kind", enumerators=[CppEnumerator(name="primary")])
        field = CppField(name="size")
        cls = CppClass(
            name="Widget",
            constructors=[constructor],
            methods=[method],
            fields=[field],
            enums=[enum_],
        )
        namespace = CppNamespace(name="demo", classes=[cls], functions=[function])
        module = CppModule(name="bindings", namespaces=[namespace])

        self.assertIsNotNone(module.py)
        self.assertIsNotNone(namespace.py)
        self.assertIsNotNone(cls.py)
        self.assertIsNotNone(function.py)
        self.assertIsNotNone(method.py)
        self.assertIsNotNone(constructor.py)
        self.assertIsNotNone(parameter.py)
        self.assertIsNotNone(enum_.py)
        self.assertIsNotNone(enum_.enumerators[0].py)
        self.assertIsNotNone(field.py)
        self.assertIsNone(module.py.module_name)
        self.assertIsNone(namespace.py.name)
        self.assertIsNone(cls.py.name)
        self.assertIsNone(function.py.name)
        self.assertIsNone(method.py.name)
        self.assertIsNone(parameter.py.name)
        self.assertIsNone(enum_.py.name)
        self.assertIsNone(enum_.enumerators[0].py.name)
        self.assertIsNone(field.py.name)
        self.assertIsNone(namespace.bind.active)
        self.assertIsNone(cls.bind.active)
        self.assertIsNone(function.bind.active)
        self.assertIsNone(method.bind.active)
        self.assertIsNone(constructor.bind.active)
        self.assertIsNone(field.bind.active)
        self.assertIsNone(enum_.bind.active)
        self.assertIsNone(enum_.enumerators[0].bind.active)

    def test_operator_metadata_lives_in_cpp_and_bind_facets(self) -> None:
        free_operator = CppFunction(name="operator+")
        free_operator.cpp.operator = CppOperator(kind="punctuation", symbol="+")
        free_operator.bind.operator = CppOperatorBind(mode="named")

        method_operator = CppMethod(name="operator[]")
        method_operator.cpp.operator = CppOperator(kind="punctuation", symbol="[]")
        method_operator.bind.operator = CppOperatorBind(mode="dunder")

        conversion_operator = CppMethod(name="operator bool")
        conversion_operator.cpp.operator = CppOperator(
            kind="conversion",
            conversion_type=NamedCppType(name="bool"),
        )

        self.assertEqual(free_operator.cpp.operator.symbol, "+")
        self.assertEqual(free_operator.bind.operator.mode, "named")
        self.assertEqual(method_operator.cpp.operator.symbol, "[]")
        self.assertEqual(method_operator.bind.operator.mode, "dunder")
        self.assertEqual(conversion_operator.cpp.operator.kind, "conversion")
        self.assertEqual(
            conversion_operator.cpp.operator.conversion_type.render(),
            "bool",
        )

    def test_defaults_reuse_bind_facet_types(self) -> None:
        module_defaults = CppModuleDefaults()
        namespace_defaults = CppNamespaceDefaults()
        class_defaults = CppClassDefaults()

        self.assertIsInstance(module_defaults.namespace, CppNamespaceBindFacet)
        self.assertIsInstance(module_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(module_defaults.function, CppFunctionBindFacet)
        self.assertIsInstance(module_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(namespace_defaults.namespace, CppNamespaceBindFacet)
        self.assertIsInstance(namespace_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(namespace_defaults.function, CppFunctionBindFacet)
        self.assertIsInstance(namespace_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(class_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(class_defaults.method, CppFunctionBindFacet)
        self.assertIsInstance(class_defaults.constructor, CppFunctionBindFacet)
        self.assertIsInstance(class_defaults.field, CppFieldBindFacet)
        self.assertIsInstance(class_defaults.enum, CppEnumBindFacet)

    def test_class_cpp_facet_uses_cpp_class_base_objects(self) -> None:
        base = CppClassBase(type=NamedCppType(name="Base"))
        cls = CppClass(name="Derived")
        cls.cpp.bases.append(base)

        self.assertIs(cls.cpp.bases[0], base)

    def test_active_flag_lives_in_bind_facets(self) -> None:
        namespace = CppNamespace(name="demo")
        cls = CppClass(name="Widget")
        function = CppFunction(name="make_widget")
        method = CppMethod(name="size")
        field = CppField(name="size")
        enum_ = CppEnum(name="Kind")
        enumerator = CppEnumerator(name="primary")

        namespace.bind.active = False
        cls.bind.active = True
        function.bind.active = False
        method.bind.active = True
        field.bind.active = False
        enum_.bind.active = True
        enumerator.bind.active = False

        self.assertFalse(namespace.bind.active)
        self.assertTrue(cls.bind.active)
        self.assertFalse(function.bind.active)
        self.assertTrue(method.bind.active)
        self.assertFalse(field.bind.active)
        self.assertTrue(enum_.bind.active)
        self.assertFalse(enumerator.bind.active)

    def test_build_py_doc_from_cpp_doc_copies_nested_data(self) -> None:
        cpp_doc = CppDoc(
            brief="Create a widget.",
            description="Build a widget from one integer seed.",
            parameters={"seed": "Seed value used by the constructor."},
            returns="A new widget instance.",
            notes=["This is only an example."],
            warnings=["Do not pass negative values."],
            see_also=["demo::Widget"],
        )

        py_doc = build_py_doc_from_cpp_doc(cpp_doc)

        self.assertIsNotNone(py_doc)
        self.assertEqual(py_doc.summary, "Create a widget.")
        self.assertEqual(py_doc.parameters["seed"], "Seed value used by the constructor.")

        cpp_doc.parameters["seed"] = "Changed"
        cpp_doc.notes.append("Changed")
        self.assertEqual(py_doc.parameters["seed"], "Seed value used by the constructor.")
        self.assertEqual(py_doc.notes, ["This is only an example."])

    def test_named_cpp_type_renders_const_qualified_names(self) -> None:
        cpp_type = NamedCppType(name="std::string", is_const=True)

        self.assertEqual(cpp_type.render(), "const std::string")


if __name__ == "__main__":
    unittest.main()
