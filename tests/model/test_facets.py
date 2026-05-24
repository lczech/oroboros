from __future__ import annotations

from pathlib import Path
import unittest

from oroboros.model import *
from tests.support.model_builders import make_class, make_class_template_declaration, make_module, make_namespace


class ModelFacetTest(unittest.TestCase):
    def test_parse_stage_starts_with_default_bind_and_default_py_facets(self) -> None:
        parameter = CppParameter(name="value")
        constructor = CppConstructor(name="Widget")
        method = CppMethod(name="size", parameters=[parameter])
        function = CppFunction(name="make_widget", parameters=[CppParameter(name="seed")])
        enum_ = CppEnum(name="Kind", enumerators=[CppEnumerator(name="primary")])
        variable = CppVariable(name="size")
        cls = make_class(
            name="Widget",
            constructors=[constructor],
            methods=[method],
            variables=[variable],
            enums=[enum_],
        )
        namespace = make_namespace(name="demo", classes=[cls], functions=[function])
        module = make_module(name="bindings", namespaces=[namespace])

        self.assertIsNotNone(module.py)
        self.assertIsNotNone(namespace.py)
        self.assertIsNotNone(cls.py)
        self.assertIsNotNone(function.py)
        self.assertIsNotNone(method.py)
        self.assertIsNotNone(constructor.py)
        self.assertIsNotNone(parameter.py)
        self.assertIsNotNone(enum_.py)
        self.assertIsNotNone(enum_.enumerators[0].py)
        self.assertIsNotNone(variable.py)
        self.assertIsNone(module.py.module_name)
        self.assertIsNone(namespace.py.name)
        self.assertIsNone(cls.py.name)
        self.assertIsNone(function.py.name)
        self.assertIsNone(function.py.sig)
        self.assertIsNone(method.py.name)
        self.assertIsNone(method.py.sig)
        self.assertIsNone(constructor.py.sig)
        self.assertIsNone(parameter.py.name)
        self.assertIsNone(parameter.py.sig)
        self.assertIsNone(enum_.py.name)
        self.assertIsNone(enum_.enumerators[0].py.name)
        self.assertIsNone(variable.py.name)
        self.assertIsNone(namespace.bind.active)
        self.assertIsNone(cls.bind.active)
        self.assertIsNone(function.bind.active)
        self.assertIsNone(method.bind.active)
        self.assertIsNone(constructor.bind.active)
        self.assertIsNone(variable.bind.active)
        self.assertIsNone(enum_.bind.active)
        self.assertIsNone(enum_.enumerators[0].bind.active)

    def test_operator_metadata_lives_in_cpp_and_bind_facets(self) -> None:
        free_operator = CppFunction(name="operator+")
        free_operator.cpp.operator = CppOperator(kind="symbolic", symbol="+")
        free_operator.bind.operator = CppOperatorBind(mode="named")

        method_operator = CppMethod(name="operator[]")
        method_operator.cpp.operator = CppOperator(kind="symbolic", symbol="[]")
        method_operator.bind.operator = CppOperatorBind(mode="dunder")

        conversion_operator = CppMethod(name="operator bool")
        conversion_operator.cpp.operator = CppOperator(
            kind="conversion",
            conversion_type=NamedCppType(name="bool"),
            is_explicit=True,
        )

        self.assertEqual(free_operator.cpp.operator.symbol, "+")
        self.assertEqual(free_operator.bind.operator.mode, "named")
        self.assertEqual(method_operator.cpp.operator.symbol, "[]")
        self.assertEqual(method_operator.bind.operator.mode, "dunder")
        self.assertEqual(conversion_operator.cpp.operator.kind, "conversion")
        self.assertTrue(conversion_operator.cpp.operator.is_explicit)
        self.assertEqual(
            conversion_operator.cpp.operator.conversion_type.render(),
            "bool",
        )

    def test_operator_helpers_classify_cxx_operator_families(self) -> None:
        comparison = CppOperator(kind="symbolic", symbol="==")
        arithmetic = CppOperator(kind="symbolic", symbol="+")
        bitwise = CppOperator(kind="symbolic", symbol="<<")
        logical = CppOperator(kind="symbolic", symbol="&&")
        assignment = CppOperator(kind="symbolic", symbol="=")
        call = CppOperator(kind="symbolic", symbol="()")
        index = CppOperator(kind="symbolic", symbol="[]")
        increment = CppOperator(kind="symbolic", symbol="++", is_postfix=True)
        conversion = CppOperator(kind="conversion", conversion_type=BuiltinCppType(kind="int"))
        allocation = CppOperator(kind="allocation", symbol="new[]")
        deallocation = CppOperator(kind="deallocation", symbol="delete")

        self.assertTrue(is_symbolic_operator(comparison))
        self.assertTrue(is_comparison_operator(comparison))
        self.assertFalse(is_arithmetic_operator(comparison))

        self.assertTrue(is_arithmetic_operator(arithmetic))
        self.assertFalse(is_assignment_operator(arithmetic))

        self.assertTrue(is_bitwise_operator(bitwise))
        self.assertFalse(is_logical_operator(bitwise))

        self.assertTrue(is_logical_operator(logical))
        self.assertFalse(is_bitwise_operator(logical))

        self.assertTrue(is_assignment_operator(assignment))
        self.assertFalse(is_comparison_operator(assignment))

        self.assertTrue(is_call_operator(call))
        self.assertFalse(is_index_operator(call))

        self.assertTrue(is_index_operator(index))
        self.assertFalse(is_call_operator(index))

        self.assertTrue(is_increment_decrement_operator(increment))

        self.assertTrue(is_conversion_operator(conversion))
        self.assertFalse(is_symbolic_operator(conversion))

        self.assertTrue(is_allocation_operator(allocation))
        self.assertTrue(is_deallocation_operator(deallocation))

        self.assertFalse(is_call_operator(None))
        self.assertFalse(is_conversion_operator(None))

    def test_defaults_reuse_bind_facet_types(self) -> None:
        module_defaults = CppModuleDefaults()
        namespace_defaults = CppNamespaceDefaults()
        class_defaults = CppClassDefaults()
        class_template_defaults = CppClassTemplateDefaults()
        function_template_defaults = CppFunctionTemplateDefaults()

        self.assertIsInstance(module_defaults.namespace, CppNamespaceBindFacet)
        self.assertIsInstance(module_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(module_defaults.class_template, CppTemplateBindFacet)
        self.assertIsInstance(module_defaults.function, CppFunctionBindFacet)
        self.assertIsInstance(module_defaults.function_template, CppTemplateBindFacet)
        self.assertIsInstance(module_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(namespace_defaults.namespace, CppNamespaceBindFacet)
        self.assertIsInstance(namespace_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(namespace_defaults.class_template, CppTemplateBindFacet)
        self.assertIsInstance(namespace_defaults.function, CppFunctionBindFacet)
        self.assertIsInstance(namespace_defaults.function_template, CppTemplateBindFacet)
        self.assertIsInstance(namespace_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(class_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(class_defaults.class_template, CppTemplateBindFacet)
        self.assertIsInstance(class_defaults.method, CppMethodBindFacet)
        self.assertIsInstance(class_defaults.constructor, CppConstructorBindFacet)
        self.assertIsInstance(class_defaults.variable, CppVariableBindFacet)
        self.assertIsInstance(class_defaults.static_variable, CppVariableBindFacet)
        self.assertIsInstance(class_defaults.function_template, CppTemplateBindFacet)
        self.assertIsInstance(class_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(class_template_defaults.instance, CppClassBindFacet)
        self.assertIsInstance(class_template_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(class_template_defaults.method, CppMethodBindFacet)
        self.assertIsInstance(class_template_defaults.constructor, CppConstructorBindFacet)
        self.assertIsInstance(class_template_defaults.variable, CppVariableBindFacet)
        self.assertIsInstance(class_template_defaults.static_variable, CppVariableBindFacet)
        self.assertIsInstance(class_template_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(function_template_defaults.instance, CppFunctionBindFacet)

    def test_method_and_constructor_bind_facets_keep_semantic_distinction(self) -> None:
        method = CppMethod(name="size")
        constructor = CppConstructor(name="Widget")

        self.assertIsInstance(method.bind, CppMethodBindFacet)
        self.assertIsInstance(method.bind, CppFunctionBindFacet)
        self.assertIsInstance(constructor.bind, CppConstructorBindFacet)
        self.assertIsInstance(constructor.bind, CppFunctionBindFacet)

    def test_add_helpers_attach_children_and_return_them(self) -> None:
        module = make_module(name="bindings")
        namespace = module.add_namespace(make_namespace(name="demo"))
        cls = namespace.add_class(make_class(name="Widget"))
        constructor = cls.add_constructor(CppConstructor(name="Widget"))
        method = cls.add_method(CppMethod(name="size"))
        parameter = method.add_parameter(CppParameter(name="value"))
        enum_ = cls.add_enum(CppEnum(name="Kind"))
        enumerator = enum_.add_enumerator(CppEnumerator(name="primary"))

        self.assertIs(module.declarations.namespaces[0], namespace)
        self.assertIs(namespace.owner, module)
        self.assertIs(namespace.declarations.classes[0], cls)
        self.assertIs(cls.owner, namespace)
        self.assertIs(cls.declarations.constructors[0], constructor)
        self.assertIs(constructor.owner, cls)
        self.assertIs(cls.declarations.methods[0], method)
        self.assertIs(method.owner, cls)
        self.assertIs(method.parameters[0], parameter)
        self.assertIs(parameter.owner, method)
        self.assertIs(cls.declarations.enums[0], enum_)
        self.assertIs(enum_.owner, cls)
        self.assertIs(enum_.enumerators[0], enumerator)
        self.assertIs(enumerator.owner, enum_)

    def test_class_cpp_facet_uses_cpp_class_base_objects(self) -> None:
        base = CppClassBase(type=NamedCppType(name="Base"), visibility=CppVisibility.PUBLIC)
        cls = make_class(name="Derived")
        cls.cpp.bases.append(base)
        cls.cpp.visibility = CppVisibility.PRIVATE

        self.assertIs(cls.cpp.bases[0], base)
        self.assertEqual(cls.cpp.bases[0].visibility, CppVisibility.PUBLIC)
        self.assertEqual(cls.cpp.visibility, CppVisibility.PRIVATE)

    def test_active_flag_lives_in_bind_facets(self) -> None:
        namespace = make_namespace(name="demo")
        cls = make_class(name="Widget")
        function = CppFunction(name="make_widget")
        method = CppMethod(name="size")
        variable = CppVariable(name="size")
        enum_ = CppEnum(name="Kind")
        enumerator = CppEnumerator(name="primary")

        namespace.bind.active = False
        cls.bind.active = True
        function.bind.active = False
        method.bind.active = True
        variable.bind.active = False
        enum_.bind.active = True
        enumerator.bind.active = False

        self.assertFalse(namespace.bind.active)
        self.assertTrue(cls.bind.active)
        self.assertFalse(function.bind.active)
        self.assertTrue(method.bind.active)
        self.assertFalse(variable.bind.active)
        self.assertTrue(enum_.bind.active)
        self.assertFalse(enumerator.bind.active)

