from __future__ import annotations

from pathlib import Path
import unittest

from oroboros.model import *
from tests.support.model_builders import make_class, make_class_template_declaration, make_module, make_namespace


class ModelLookupTest(unittest.TestCase):
    def test_model_nodes_adopt_children_and_compute_qualified_names(self) -> None:
        parameter = CppParameter(name="value")
        constructor = CppConstructor(name="Widget", parameters=[CppParameter(name="seed")])
        method = CppMethod(name="size", parameters=[parameter])
        enum_ = CppEnum(name="Kind", enumerators=[CppEnumerator(name="primary")])
        cls = make_class(
            name="Widget",
            constructors=[constructor],
            methods=[method],
            enums=[enum_],
        )
        cls.add_alias(CppAlias(name="SizeType")).cpp.target = NamedCppType(name="std::size_t")
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

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
        self.assertEqual(cls.declarations.aliases[0].qualified_name, "demo::Widget::SizeType")

    def test_aliases_preserve_target_type_and_can_be_found_in_scope_tree(self) -> None:
        namespace = make_namespace(name="demo")
        namespace.add_alias(CppAlias(name="Index")).cpp.target = NamedCppType(name="std::size_t")
        namespace.declarations.aliases[0].cpp.kind = "using"

        self.assertEqual(namespace.declarations.aliases[0].qualified_name, "demo::Index")
        self.assertEqual(namespace.declarations.aliases[0].cpp.target.render(), "std::size_t")
        self.assertEqual(namespace.declarations.aliases[0].cpp.kind, "using")

    def test_find_aliases_discovers_class_aliases_across_subtrees(self) -> None:
        cls = make_class(name="Widget")
        namespace = make_namespace(name="demo", classes=[cls])
        namespace.add_alias(CppAlias(name="WidgetAlias")).cpp.target = NamedCppType(name="demo::Widget")
        namespace.add_alias(CppAlias(name="SizeType")).cpp.target = NamedCppType(name="std::size_t")
        nested = make_namespace(name="detail")
        nested.add_alias(CppAlias(name="WidgetHandle")).cpp.target = NamedCppType(name="demo::Widget")
        namespace.add_namespace(nested)

        aliases = find_aliases(namespace, cls)

        self.assertCountEqual(
            [alias.name for alias in aliases],
            ["WidgetAlias", "WidgetHandle"],
        )

    def test_find_aliases_matches_class_targets_via_declaration_links_with_qualifiers(self) -> None:
        cls = make_class(name="Widget")
        namespace = make_namespace(name="demo", classes=[cls])
        namespace.add_alias(CppAlias(name="WidgetAlias")).cpp.target = NamedCppType(
            name="Widget",
            declaration=cls,
            is_const=True,
        )

        aliases = find_aliases(namespace, cls)

        self.assertEqual([alias.name for alias in aliases], ["WidgetAlias"])

    def test_find_aliases_matches_type_targets_via_canonical_structure(self) -> None:
        namespace = make_namespace(name="demo")
        namespace.add_alias(CppAlias(name="Index")).cpp.target = NamedCppType(
            name="uint64_t",
            canonical=BuiltinCppType(kind="unsigned_long"),
        )

        aliases = find_aliases(namespace, BuiltinCppType(kind="unsigned_long"))

        self.assertEqual([alias.name for alias in aliases], ["Index"])

    def test_find_aliases_follows_alias_chains_to_the_underlying_class(self) -> None:
        widget = make_class(name="Widget")
        namespace = make_namespace(name="demo", classes=[widget])
        first = namespace.add_alias(CppAlias(name="A"))
        first.cpp.target = NamedCppType(name="Widget", declaration=widget)
        second = namespace.add_alias(CppAlias(name="B"))
        second.cpp.target = NamedCppType(
            name="A",
            declaration=first,
            canonical=NamedCppType(name="Widget", declaration=widget),
        )

        aliases = find_aliases(namespace, widget)

        self.assertCountEqual(
            [alias.name for alias in aliases],
            ["A", "B"],
        )

    def test_lookup_helpers_find_elements_by_name_and_qualified_name(self) -> None:
        method = CppMethod(name="foo")
        cls = make_class(name="Widget", methods=[method])
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        self.assertIs(
            module.find_one_by_qualified_name("::demo::Widget", types=CppClass),
            cls,
        )
        self.assertEqual(
            module.find_all_by_name("foo", types=(CppMethod,)),
            [method],
        )
        self.assertIs(
            namespace.find_one_by_name("Widget", types=CppClass),
            cls,
        )

    def test_named_child_views_navigate_unique_and_overloadable_collections(self) -> None:
        method_a = CppMethod(name="foo")
        method_b = CppMethod(name="foo")
        variable = CppVariable(name="size")
        static_variable = CppVariable(name="instance_count")
        enum_ = CppEnum(name="Kind", enumerators=[CppEnumerator(name="primary")])
        cls = make_class(
            name="Widget",
            methods=[method_a, method_b],
            variables=[variable],
            static_variables=[static_variable],
            enums=[enum_],
        )
        function_a = CppFunction(name="make_widget")
        function_b = CppFunction(name="make_widget")
        namespace_variable = CppVariable(name="global_count")
        namespace = make_namespace(
            name="demo",
            classes=[cls],
            functions=[function_a, function_b],
            variables=[namespace_variable],
        )
        module = make_module(name="bindings", namespaces=[namespace])

        self.assertIs(module.namespace["demo"], namespace)
        self.assertIs(namespace.class_["Widget"], cls)
        self.assertIs(namespace.variable["global_count"], namespace_variable)
        self.assertIs(cls.variable["size"], variable)
        self.assertIs(cls.static_variable["instance_count"], static_variable)
        self.assertIs(cls.enum["Kind"], enum_)
        self.assertIs(enum_.enumerator["primary"], enum_.enumerators[0])
        self.assertEqual(namespace.function["make_widget"], [function_a, function_b])
        self.assertEqual(cls.method["foo"], [method_a, method_b])

    def test_named_child_views_raise_on_missing_or_ambiguous_unique_names(self) -> None:
        namespace_a = make_namespace(name="demo")
        namespace_b = make_namespace(name="demo")
        module = make_module(name="bindings", namespaces=[namespace_a, namespace_b])

        with self.assertRaises(ModelLookupError):
            _ = module.namespace["demo"]

        with self.assertRaises(ModelLookupError):
            _ = module.function["missing"]

    def test_generic_navigation_supports_chained_direct_child_lookup(self) -> None:
        method = CppMethod(name="size")
        cls = make_class(name="Widget", methods=[method])
        inner = make_namespace(name="inner", classes=[cls])
        outer = make_namespace(name="outer", namespaces=[inner])
        module = make_module(name="bindings", namespaces=[outer])

        self.assertIs(module["outer"], outer)
        self.assertIs(module["outer"]["inner"], inner)
        self.assertIs(module["outer"]["inner"]["Widget"], cls)
        self.assertIs(module["outer"]["inner"]["Widget"]["size"], method)

    def test_generic_navigation_returns_lists_for_overloadable_direct_children(self) -> None:
        method_a = CppMethod(name="size")
        method_b = CppMethod(name="size")
        cls = make_class(name="Widget", methods=[method_a, method_b])

        self.assertEqual(cls["size"], [method_a, method_b])

    def test_generic_navigation_returns_mixed_callable_groups_for_functions_and_templates(self) -> None:
        function = CppFunction(name="make_widget")
        function_template = CppFunctionTemplate(name="make_widget")
        namespace = make_namespace(
            name="demo",
            functions=[function],
            function_templates=[function_template],
        )

        self.assertEqual(namespace["make_widget"], [function, function_template])

    def test_element_names_and_generic_find_helpers_improve_discovery(self) -> None:
        method = CppMethod(name="size")
        cls = make_class(name="Widget", methods=[method])
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        self.assertEqual(module.element_names, ["demo"])
        self.assertEqual(namespace.element_names, ["Widget"])
        self.assertEqual(cls.element_names, ["size"])
        self.assertIs(module.find("demo::Widget"), cls)
        self.assertEqual(module.find_all("size"), [method])

    def test_lookup_helpers_raise_on_missing_or_ambiguous_matches(self) -> None:
        cls = make_class(
            name="Widget",
            methods=[CppMethod(name="foo"), CppMethod(name="foo")],
        )
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        self.assertEqual(
            len(module.find_all_by_qualified_name("demo::Widget::foo", types=CppMethod)),
            2,
        )

        with self.assertRaises(ModelLookupError):
            module.find_one_by_qualified_name("demo::Widget::foo", types=CppMethod)

        with self.assertRaises(ModelLookupError):
            module.find_one_by_name("foo", types=CppMethod)

        with self.assertRaises(ModelLookupError):
            module.find_one_by_qualified_name("demo::MissingNamespace")

